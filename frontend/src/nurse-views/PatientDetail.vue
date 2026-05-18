<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Btn, Chip, Field, GlassPanel, Dialog } from '../components'
import { useToast } from '../composables/useToast'
import { api } from '../api'

/**
 * PatientDetail — 护工端患者详情 + 任务卡 + AI 问诊
 *
 * 整合旧版 nurse.html 的:
 *   - 档案信息折叠面板
 *   - 症状输入 + 快速标签
 *   - 生成护理任务卡(调 /api/nursing/taskcard)
 *   - 快速问 AI(调 /api/nursing/decision)
 *   - 任务执行打卡(完成/异常/跳过 + 进度条)
 *
 * 流式 API 在 Phase 5 先用非流式 fallback;Phase 6 再加 SSE reader。
 */

const props = defineProps<{ id: string }>()
const router = useRouter()
const { push: toast } = useToast()

// ── Patient data ──
interface PatientFull {
  patient_id: string
  name: string
  age?: number
  gender?: string
  bed_number?: string
  care_level?: string
  medical_history?: string
  allergy?: string
  diet_restriction?: string
  emergency_contact?: string
  emergency_phone?: string
  admission_date?: string
  primary_nurse?: string
  notes?: string
}

const patient = ref<PatientFull | null>(null)
const loading = ref(true)

// ── Symptom + AI ──
const symptomText = ref('')
const aiAdvice = ref('')
const aiLoading = ref(false)

// ── Task Card ──
interface TaskItem {
  text: string
  status: 'pending' | 'done' | 'abnormal' | 'skipped'
  priority?: string
  /** 后端 decision_id —— 任务卡的 outcome 回填要靠它 */
  decisionId?: string | null
  /** 标记是否正在保存，避免连点 */
  saving?: boolean
}
const taskItems = ref<TaskItem[]>([])
const taskLoading = ref(false)
const taskRiskLevel = ref('')
const taskTitle = ref('')
// 整张任务卡背后的 decision_id —— 后端 task-card 接口会在 response 里返回
const taskDecisionId = ref<string | null>(null)

const quickSymptoms = ['发热', '咳嗽', '头晕', '胸闷', '腹痛', '血压偏高', '血糖异常', '跌倒', '意识异常']

// ── Progress ──
function progress() {
  if (taskItems.value.length === 0) return 0
  const done = taskItems.value.filter((t) => t.status !== 'pending').length
  return Math.round((done / taskItems.value.length) * 100)
}

// ── Fetch patient ──
async function fetchPatient() {
  loading.value = true
  try {
    // Try /api/ehr/patients first, then filter by ID
    const res = await api.get<PatientFull[] | { records: PatientFull[] }>('/ehr/patients')
    const list = Array.isArray(res) ? res : (res as any).records ?? []
    patient.value = list.find((p: PatientFull) => p.patient_id === props.id) ?? null
    if (!patient.value) {
      toast({ tone: 'error', text: '未找到该老人档案' })
    }
  } catch (e: any) {
    toast({ tone: 'error', text: e.message ?? '加载档案失败' })
  } finally {
    loading.value = false
  }
}

// ── Add quick symptom ──
function addSymptom(s: string) {
  symptomText.value = symptomText.value ? `${symptomText.value}\n${s}` : s
}

// ── Generate Task Card ──
async function generateTaskCard() {
  if (!symptomText.value.trim()) {
    toast({ tone: 'warning', text: '请先描述老人的情况' })
    return
  }
  taskLoading.value = true
  try {
    const res = await api.post<any>('/nursing/taskcard', {
      patient_id: props.id,
      symptom: symptomText.value.trim(),
    })
    // Parse task card response
    const card = res
    taskRiskLevel.value = card.risk_level ?? ''
    taskTitle.value = card.event_title ?? '护理任务卡'
    taskDecisionId.value = card.decision_id ?? null
    taskItems.value = (card.care_tasks ?? []).map((t: any) => ({
      text: typeof t === 'string' ? t : t.description ?? t.text ?? '',
      status: 'pending' as const,
      priority: t.priority,
      decisionId: card.decision_id ?? null,
      saving: false,
    }))
    toast({ tone: 'success', text: '任务卡已生成' })
  } catch (e: any) {
    toast({ tone: 'error', text: e.message ?? '生成任务卡失败' })
  } finally {
    taskLoading.value = false
  }
}

// ── Ask AI ──
async function askAI() {
  if (!symptomText.value.trim()) {
    toast({ tone: 'warning', text: '请先描述老人的情况' })
    return
  }
  aiLoading.value = true
  aiAdvice.value = ''
  try {
    const res = await api.post<any>('/nursing/decision', {
      patient_id: props.id,
      symptom: symptomText.value.trim(),
      n_results: 5,
    })
    aiAdvice.value = res.llm_advice ?? '暂无建议'
  } catch (e: any) {
    toast({ tone: 'error', text: e.message ?? 'AI 暂时不可用' })
  } finally {
    aiLoading.value = false
  }
}

// ── Task execution ──
//
// Phase 7 起调用后端 PATCH /api/nursing/decisions/{decision_id}/outcome 持久化:
//   1) UI 立即更新（optimistic）—— 护工"打卡"必须秒响应,不允许等网络
//   2) 异步上报失败时回滚 + toast 提示,但不会阻塞下一个打卡操作
//   3) 整张任务卡共享一个 decision_id（生成任务卡时由后端给）。当前后端按
//      "整张卡 = 一条决策记录"建模,所以任意一项打卡都聚合上报为最近一次
//      outcome —— 状态选取规则:任意 abnormal → 'ineffective';全 done →
//      'effective';有 skipped 但没 abnormal → 'partial';否则 'pending'。
function aggregateOutcome(): 'pending' | 'effective' | 'ineffective' | 'partial' {
  const list = taskItems.value
  if (list.length === 0) return 'pending'
  if (list.some((t) => t.status === 'abnormal')) return 'ineffective'
  const remaining = list.filter((t) => t.status === 'pending').length
  if (remaining > 0) return 'pending'
  if (list.some((t) => t.status === 'skipped')) return 'partial'
  return 'effective'
}

async function persistOutcome() {
  if (!taskDecisionId.value) return // 任务卡可能离线 mock,后端没给 id 就不上报
  const status = aggregateOutcome()
  // 拼一个简短的 note,把每项当前状态记录下来
  const note = taskItems.value
    .map((t, i) => `${i + 1}. ${t.text} → ${t.status}`)
    .join('\n')
  try {
    await api.patch(`/nursing/decisions/${encodeURIComponent(taskDecisionId.value)}/outcome`, {
      outcome_status: status,
      note,
    })
  } catch (e: any) {
    // 这里不弹 error toast 防止刷屏 —— 打卡操作本质是"快速勾选",
    // 单条上报失败不影响后续操作。仅在 console 提示。
    console.warn('[outcome] 上报失败', e)
  }
}

let outcomeDebounce: number | null = null
function scheduleOutcomePersist() {
  if (typeof window === 'undefined') return
  if (outcomeDebounce !== null) {
    window.clearTimeout(outcomeDebounce)
  }
  outcomeDebounce = window.setTimeout(() => {
    persistOutcome()
    outcomeDebounce = null
  }, 600)
}

function markTask(index: number, status: TaskItem['status']) {
  taskItems.value[index].status = status
  scheduleOutcomePersist()
}

onMounted(fetchPatient)
</script>

<template>
  <div class="pd-view">
    <!-- Back button -->
    <Btn variant="ghost" size="sm" @click="router.back()" style="margin-bottom: var(--sp-3);">
      ← 返回列表
    </Btn>

    <!-- Loading -->
    <div v-if="loading" class="empty">
      <div class="skel" style="height: 120px; width: 100%;"></div>
    </div>

    <template v-else-if="patient">
      <!-- Patient header -->
      <GlassPanel variant="card" class="pd-header">
        <template #header>
          <div class="pd-avatar">{{ (patient.name || '?').slice(0, 1) }}</div>
          <div>
            <h2 class="title-l">{{ patient.name }}</h2>
            <p class="meta">
              {{ patient.patient_id }} · {{ patient.age ?? '?' }}岁 · {{ patient.gender ?? '—' }} ·
              {{ patient.bed_number ?? '—' }}床
            </p>
          </div>
        </template>
        <div class="pd-tags">
          <Chip v-if="patient.care_level" tone="accent">{{ patient.care_level }}护理</Chip>
          <Chip v-if="patient.allergy" tone="danger">过敏: {{ patient.allergy }}</Chip>
          <Chip v-if="patient.diet_restriction" tone="warning">{{ patient.diet_restriction }}</Chip>
        </div>

        <!-- Collapsible info -->
        <details class="pd-details">
          <summary class="title-s">档案信息（完整）</summary>
          <dl class="pd-info-grid">
            <div v-if="patient.admission_date"><dt>入院</dt><dd>{{ patient.admission_date }}</dd></div>
            <div v-if="patient.primary_nurse"><dt>主管</dt><dd>{{ patient.primary_nurse }}</dd></div>
            <div v-if="patient.emergency_contact"><dt>紧急联系</dt><dd>{{ patient.emergency_contact }} {{ patient.emergency_phone }}</dd></div>
            <div v-if="patient.medical_history" class="full"><dt>病史</dt><dd>{{ patient.medical_history }}</dd></div>
            <div v-if="patient.notes" class="full"><dt>备注</dt><dd>{{ patient.notes }}</dd></div>
          </dl>
        </details>
      </GlassPanel>

      <!-- Symptom input -->
      <GlassPanel class="pd-symptom">
        <template #header>
          <span class="title-s">描述情况</span>
        </template>
        <div class="pd-quick-tags">
          <button
            v-for="s in quickSymptoms"
            :key="s"
            class="tap-chip"
            @click="addSymptom(s)"
          >
            {{ s }}
          </button>
        </div>
        <Field
          v-model="symptomText"
          type="textarea"
          :rows="3"
          placeholder="描述老人目前的症状或护理需求…"
        />
        <div class="pd-actions">
          <Btn variant="primary" :loading="taskLoading" @click="generateTaskCard">
            生成护理任务卡
          </Btn>
          <Btn variant="outline" :loading="aiLoading" @click="askAI">
            快速问 AI
          </Btn>
        </div>
      </GlassPanel>

      <!-- Task Card -->
      <GlassPanel v-if="taskItems.length > 0" class="pd-task-card">
        <template #header>
          <Chip v-if="taskRiskLevel" :tone="taskRiskLevel === 'high' ? 'danger' : taskRiskLevel === 'medium' ? 'warning' : 'success'">
            {{ taskRiskLevel }}
          </Chip>
          <span class="title-s">{{ taskTitle }}</span>
        </template>

        <!-- Progress bar -->
        <div class="progress">
          <div class="progress-bar" :style="{ width: progress() + '%' }"></div>
        </div>
        <span class="meta">{{ progress() }}% 完成</span>

        <!-- Task items -->
        <div class="pd-tasks">
          <div
            v-for="(t, i) in taskItems"
            :key="i"
            class="pd-task-item"
          >
            <div
              class="task-check"
              :class="t.status"
              @click="markTask(i, t.status === 'done' ? 'pending' : 'done')"
            >
              <span v-if="t.status === 'done'">✓</span>
              <span v-else-if="t.status === 'abnormal'">!</span>
              <span v-else-if="t.status === 'skipped'">—</span>
            </div>
            <div class="pd-task-content">
              <span class="task-text" :class="t.status">{{ t.text }}</span>
              <div v-if="t.status === 'pending'" class="task-exec-actions">
                <button class="btn btn-ghost btn-sm" @click="markTask(i, 'done')">完成</button>
                <button class="btn btn-ghost btn-sm" @click="markTask(i, 'abnormal')">异常</button>
                <button class="btn btn-ghost btn-sm" @click="markTask(i, 'skipped')">跳过</button>
              </div>
            </div>
          </div>
        </div>
      </GlassPanel>

      <!-- AI Advice -->
      <GlassPanel v-if="aiAdvice" class="pd-ai-card">
        <template #header>
          <span class="title-s">AI 护理建议</span>
        </template>
        <p class="body-m" style="white-space: pre-wrap;">{{ aiAdvice }}</p>
        <div class="pd-disclaimer">
          ⚠️ AI 生成内容仅供参考。遇到严重症状请立即联系医生。
        </div>
      </GlassPanel>
    </template>

    <div v-else class="empty">
      <p class="empty-title">未找到老人档案</p>
    </div>
  </div>
</template>

<style scoped>
.pd-view {
  display: grid;
  gap: var(--sp-4, 16px);
  max-width: 720px;
  margin: 0 auto;
  /* 给底部 tab + 安全区留出空间，避免最后一行被遮挡 */
  padding-bottom: 16px;
}
.pd-header :deep(.vp-glass__header) {
  display: flex;
  align-items: center;
  gap: var(--sp-3, 12px);
}
.pd-avatar {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: rgba(20, 184, 166, 0.12);
  color: var(--accent-ink, #0f766e);
  display: flex;
  align-items: center;
  justify-content: center;
  font: 600 22px / 1 var(--font-display, serif);
  flex-shrink: 0;
}
.pd-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: var(--sp-2, 8px);
}
.pd-details {
  margin-top: var(--sp-3, 12px);
  border-top: 1px solid rgba(15, 23, 42, 0.06);
  padding-top: var(--sp-2, 8px);
}
.pd-details summary {
  cursor: pointer;
  padding: var(--sp-2, 8px) 0;
}
.pd-info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px;
  margin-top: var(--sp-2, 8px);
  font: 400 var(--fz-xs, 11px) / 1.5 var(--font-ui);
}
.pd-info-grid .full { grid-column: 1 / -1; }
.pd-info-grid dt { color: var(--ink-4); }
.pd-info-grid dd { margin: 0; color: var(--ink-1); }
.pd-quick-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: var(--sp-3, 12px);
}
.pd-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-2, 8px);
  margin-top: var(--sp-3, 12px);
}
.pd-tasks {
  display: grid;
  gap: 6px;
  margin-top: var(--sp-3, 12px);
}
.pd-task-item {
  display: flex;
  gap: var(--sp-2, 8px);
  align-items: flex-start;
  padding: var(--sp-2, 8px) 0;
  border-bottom: 1px dashed rgba(15, 23, 42, 0.06);
}
.pd-task-item:last-child { border-bottom: none; }
.pd-task-content { flex: 1; }
.pd-ai-card {
  border: 1px solid rgba(20, 184, 166, 0.2);
}
.pd-disclaimer {
  margin-top: var(--sp-3, 12px);
  padding: var(--sp-2, 8px) var(--sp-3, 12px);
  border-radius: var(--r-s, 10px);
  background: rgba(217, 119, 6, 0.08);
  color: var(--amber, #d97706);
  font: 400 var(--fz-xs, 11px) / 1.5 var(--font-ui);
}

@media (max-width: 640px) {
  .pd-info-grid { grid-template-columns: 1fr; }
  .pd-actions { grid-template-columns: 1fr; }
  .pd-actions .btn { height: 46px; font-size: 15px; }
  .pd-avatar { width: 44px; height: 44px; font-size: 18px; }
  .pd-tags .chip { font-size: 11px; height: 22px; }
  .pd-quick-tags .tap-chip { font-size: 13px; height: 36px; }
  /* 任务执行三个按钮平铺 */
  .task-exec-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 6px;
  }
  .task-exec-actions .btn {
    flex: 1 1 calc(33% - 4px);
    min-height: 38px;
    padding: 0 8px;
    font-size: 13px;
  }
  .task-check { width: 32px; height: 32px; }
  .task-text { font-size: 14px; }
  .progress { height: 8px; }
  .pd-disclaimer { font-size: 12px; }
}

@media (max-width: 480px) {
  .pd-actions .btn { height: 48px; font-size: 15px; }
  .task-exec-actions .btn { flex: 1 1 100%; min-height: 40px; }
  .pd-info-grid { font-size: 12px; }
}

/* 通用任务执行按钮布局(桌面+移动) */
.task-exec-actions {
  display: flex;
  gap: 6px;
  margin-top: 4px;
  flex-wrap: wrap;
}

/* ─── progress + task-check styling ─── */
.progress {
  height: 6px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.06);
  overflow: hidden;
  margin-top: 8px;
}
.progress-bar {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--accent), var(--accent-2));
  transition: width 320ms var(--ease);
}

.task-check {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  border-radius: 50%;
  border: 1.5px solid rgba(15, 23, 42, 0.15);
  background: rgba(255, 255, 255, 0.85);
  color: transparent;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font: 700 14px/1 var(--font-mono);
  transition: all 160ms var(--ease);
}
.task-check.done {
  background: var(--green, #10b981);
  border-color: var(--green, #10b981);
  color: #fff;
}
.task-check.abnormal {
  background: var(--red, #ef4444);
  border-color: var(--red, #ef4444);
  color: #fff;
}
.task-check.skipped {
  background: rgba(15, 23, 42, 0.08);
  border-color: rgba(15, 23, 42, 0.18);
  color: var(--ink-3);
}
.task-text {
  display: block;
  font: 500 14px/1.5 var(--font-ui);
  color: var(--ink-1);
}
.task-text.done {
  text-decoration: line-through;
  color: var(--ink-4);
}
.task-text.skipped {
  color: var(--ink-4);
}
</style>
