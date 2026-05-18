<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Btn, Chip, Field, GlassPanel } from '../components'
import { useToast } from '../composables/useToast'
import { api } from '../api'

/**
 * NursingDecision — AI 护理决策（管理端核心功能）
 *
 * 对应旧版 index.html 的 tab-dec：
 *   - 选择老人 + 症状输入
 *   - 快速标签
 *   - 调用 /api/nursing/decision/stream 或 fallback /api/nursing/decision
 *   - 展示 AI 建议 + 决策记忆
 *   - 结果回填 /api/nursing/decisions/{id}/outcome
 */

interface Patient {
  patient_id: string
  name: string
  bed_number?: string
  care_level?: string
}

interface DecisionMemory {
  decision_id: string
  symptom: string
  created_at: string
  outcome_status?: string
}

const { push: toast } = useToast()

const patients = ref<Patient[]>([])
const patientSearch = ref('')
const selectedPid = ref('')
const symptomText = ref('')
const adviceText = ref('')
const aiLoading = ref(false)
const currentDecisionId = ref<string | null>(null)
const memories = ref<DecisionMemory[]>([])
const evidence = ref<any[]>([])

const quickSymptoms = ['发热', '咳嗽', '头晕', '胸闷', '腹痛', '血压偏高', '血糖异常', '跌倒', '意识异常']

// ── 加载老人列表 ──
async function loadPatients() {
  try {
    const res = await api.get<Patient[] | { records: Patient[] }>('/ehr/patients')
    patients.value = Array.isArray(res) ? res : (res as any).records ?? []
  } catch (e: any) {
    toast({ tone: 'error', text: e.message ?? '加载老人列表失败' })
  }
}

// ── 筛选后的列表 ──
function filteredPatients() {
  const q = patientSearch.value.trim().toLowerCase()
  if (!q) return patients.value
  return patients.value.filter(
    (p) =>
      p.name?.toLowerCase().includes(q) ||
      p.patient_id?.toLowerCase().includes(q) ||
      p.bed_number?.toLowerCase().includes(q),
  )
}

// ── 选中老人后加载决策记忆 ──
async function onPatientChange() {
  if (!selectedPid.value) {
    memories.value = []
    return
  }
  try {
    const res = await api.get<any>(
      `/nursing/decisions?patient_id=${encodeURIComponent(selectedPid.value)}&limit=5&days=30`,
    )
    memories.value = res.decisions ?? []
  } catch {
    memories.value = []
  }
}

function addSymptom(s: string) {
  symptomText.value = symptomText.value ? `${symptomText.value}\n${s}` : s
}

// ── 提交 AI 决策（先尝试流式，失败走 fallback） ──
async function submitDecision() {
  if (!selectedPid.value || !symptomText.value.trim()) {
    toast({ tone: 'warning', text: '请选择老人并填写症状' })
    return
  }
  aiLoading.value = true
  adviceText.value = ''
  evidence.value = []
  currentDecisionId.value = null

  try {
    await streamDecision()
  } catch {
    try {
      await fallbackDecision()
    } catch (e: any) {
      toast({ tone: 'error', text: 'AI 暂时不可用，请确认本地模型服务已启动' })
    }
  } finally {
    aiLoading.value = false
    // 刷新决策记忆
    onPatientChange()
  }
}

async function streamDecision() {
  const token = localStorage.getItem('auth_token') || ''
  const res = await fetch('/api/nursing/decision/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'X-Auth-Token': token } : {}),
    },
    body: JSON.stringify({
      patient_id: selectedPid.value,
      symptom: symptomText.value.trim(),
      n_results: 5,
    }),
  })
  if (!res.ok) throw new Error('stream failed')

  const reader = res.body!.getReader()
  const dec = new TextDecoder()
  let buf = ''
  let curEv = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    const lines = buf.split('\n')
    buf = lines.pop()!
    for (const line of lines) {
      if (line.startsWith('event:')) {
        curEv = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        const raw = line.slice(5).trim()
        if (raw === '[DONE]') continue
        try {
          const d = JSON.parse(raw)
          if (curEv === 'evidence') {
            evidence.value = d.evidence ?? []
          } else if (curEv === 'token') {
            adviceText.value += typeof d === 'string' ? d : JSON.stringify(d)
          } else if (curEv === 'done') {
            if (d?.decision_id) currentDecisionId.value = d.decision_id
          }
        } catch {
          // skip parse errors on partial tokens
          if (curEv === 'token') {
            adviceText.value += raw
          }
        }
      }
    }
  }
}

async function fallbackDecision() {
  const res = await api.post<any>('/nursing/decision', {
    patient_id: selectedPid.value,
    symptom: symptomText.value.trim(),
    n_results: 5,
  })
  adviceText.value = res.llm_advice ?? JSON.stringify(res)
  if (res.decision_id) currentDecisionId.value = res.decision_id
  evidence.value = res.evidence ?? []
}

// ── 结果回填 ──
async function recordOutcome(status: string) {
  if (!currentDecisionId.value) return
  try {
    await api.patch(`/nursing/decisions/${encodeURIComponent(currentDecisionId.value)}/outcome`, {
      outcome_status: status,
      note: `管理端标记: ${status}`,
      recorded_by: '管理端',
    })
    toast({ tone: 'success', text: '结果已记录' })
    onPatientChange()
  } catch (e: any) {
    toast({ tone: 'error', text: e.message ?? '记录失败' })
  }
}

onMounted(loadPatients)
</script>

<template>
  <div class="nd-view">
    <GlassPanel variant="card">
      <template #header>
        <span class="title-l">AI 护理建议</span>
        <p class="meta">AI 会结合老人档案、病历和过往护理记录给出建议，并标注每条建议来自哪份材料</p>
      </template>

      <!-- 选择老人 -->
      <div class="nd-patient-row">
        <Field v-model="patientSearch" placeholder="搜索老人…" class="nd-search" />
        <select v-model="selectedPid" class="field nd-select" @change="onPatientChange">
          <option value="">— 请选择老人 —</option>
          <option
            v-for="p in filteredPatients()"
            :key="p.patient_id"
            :value="p.patient_id"
          >
            {{ p.name }}（{{ p.patient_id }}）{{ p.bed_number ? ' · ' + p.bed_number : '' }}
          </option>
        </select>
      </div>

      <!-- 快速标签 -->
      <div class="nd-chips">
        <button
          v-for="s in quickSymptoms"
          :key="s"
          class="tap-chip"
          @click="addSymptom(s)"
        >
          {{ s }}
        </button>
      </div>

      <!-- 症状输入 -->
      <Field
        v-model="symptomText"
        type="textarea"
        :rows="3"
        placeholder="描述老人目前的症状或护理需求…"
      />

      <div class="nd-submit">
        <Btn variant="primary" :loading="aiLoading" @click="submitDecision">
          获取 AI 护理建议
        </Btn>
      </div>
    </GlassPanel>

    <!-- AI 建议结果 -->
    <GlassPanel v-if="adviceText" class="nd-advice">
      <template #header>
        <span class="title-s">AI 护理建议</span>
      </template>
      <p class="body-m" style="white-space: pre-wrap;">{{ adviceText }}</p>

      <!-- 结果回填按钮 -->
      <div v-if="currentDecisionId" class="nd-outcome">
        <span class="meta">执行效果：</span>
        <Btn variant="outline" size="sm" @click="recordOutcome('effective')">有效</Btn>
        <Btn variant="outline" size="sm" @click="recordOutcome('ineffective')">无效</Btn>
        <Btn variant="ghost" size="sm" @click="recordOutcome('partial')">部分有效</Btn>
      </div>

      <div class="nd-disclaimer">
        <span>⚠️ AI 生成内容仅供参考。持续不适或出现严重症状，请立即联系医生或启动急救流程。</span>
      </div>
    </GlassPanel>

    <!-- 检索证据 -->
    <GlassPanel v-if="evidence.length > 0">
      <template #header>
        <span class="title-s">参考来源</span>
      </template>
      <div class="nd-evidence">
        <div v-for="(e, i) in evidence" :key="i" class="nd-ev-item">
          <Chip tone="info">{{ e.source_type ?? '档案' }}</Chip>
          <span class="body-s">{{ e.text?.slice(0, 200) ?? '' }}</span>
        </div>
      </div>
    </GlassPanel>

    <!-- 决策记忆 -->
    <GlassPanel v-if="memories.length > 0">
      <template #header>
        <span class="title-s">近期决策记忆</span>
      </template>
      <div class="nd-memories">
        <div v-for="m in memories" :key="m.decision_id" class="nd-mem-item">
          <div class="body-s"><strong>{{ m.symptom }}</strong></div>
          <div class="meta">
            {{ m.created_at }}
            <Chip v-if="m.outcome_status" :tone="m.outcome_status === 'effective' ? 'success' : m.outcome_status === 'ineffective' ? 'danger' : 'warning'" style="margin-left: 6px;">
              {{ m.outcome_status }}
            </Chip>
          </div>
        </div>
      </div>
    </GlassPanel>
  </div>
</template>

<style scoped>
.nd-view {
  display: grid;
  gap: var(--sp-4, 16px);
  max-width: 900px;
}
.nd-patient-row {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: var(--sp-2, 8px);
  margin-bottom: var(--sp-3, 12px);
}
.nd-select {
  height: 40px;
}
.nd-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: var(--sp-3, 12px);
}
.nd-submit {
  margin-top: var(--sp-3, 12px);
}
.nd-advice {
  border: 1px solid rgba(20, 184, 166, 0.2);
}
.nd-outcome {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: var(--sp-3, 12px);
  padding-top: var(--sp-2, 8px);
  border-top: 1px solid rgba(15, 23, 42, 0.06);
}
.nd-disclaimer {
  margin-top: var(--sp-3, 12px);
  padding: var(--sp-2, 8px) var(--sp-3, 12px);
  border-radius: var(--r-s, 10px);
  background: rgba(217, 119, 6, 0.08);
  color: var(--amber, #d97706);
  font: 400 var(--fz-xs, 11px) / 1.5 var(--font-ui);
}
.nd-evidence {
  display: grid;
  gap: 8px;
}
.nd-ev-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.02);
}
.nd-memories {
  display: grid;
  gap: 8px;
}
.nd-mem-item {
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.02);
  border-left: 3px solid var(--accent, #14b8a6);
}
@media (max-width: 640px) {
  .nd-patient-row {
    grid-template-columns: 1fr;
  }
}
</style>
