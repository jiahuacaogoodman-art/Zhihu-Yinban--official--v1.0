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
}
const taskItems = ref<TaskItem[]>([])
const taskLoading = ref(false)
const taskRiskLevel = ref('')
const taskTitle = ref('')

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
    taskItems.value = (card.care_tasks ?? []).map((t: any) => ({
      text: typeof t === 'string' ? t : t.description ?? t.text ?? '',
      status: 'pending' as const,
      priority: t.priority,
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
function markTask(index: number, status: TaskItem['status']) {
  taskItems.value[index].status = status
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
}
</style>
