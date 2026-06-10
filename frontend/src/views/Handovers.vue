<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Btn, Chip, Dialog, Field, GlassPanel } from '../components'
import { useToast } from '../composables/useToast'
import { api } from '../api'

interface Handover {
  handover_id: string
  shift_from: string
  shift_to: string
  shift_type: string
  patient_id?: string | null
  patient_name?: string | null
  situation: string
  background: string
  assessment: string
  recommendation: string
  pending_tasks?: string | null
  notes?: string | null
  status: string
  acknowledged_at?: string | null
  created_at: string
}

const { push: toast } = useToast()
const handovers = ref<Handover[]>([])
const loading = ref(false)
const createOpen = ref(false)
const saving = ref(false)
const acknowledgingId = ref<string | null>(null)

const form = reactive({
  shift_from: '',
  shift_to: '',
  shift_type: 'day_to_night',
  patient_id: '',
  situation: '',
  background: '',
  assessment: '',
  recommendation: '',
  pending_tasks: '',
  notes: '',
})

const statusMap: Record<string, { label: string; tone: 'success' | 'warning' | 'info' }> = {
  pending: { label: '待确认', tone: 'warning' },
  acknowledged: { label: '已确认', tone: 'info' },
  completed: { label: '已完成', tone: 'success' },
}

const shiftLabels: Record<string, string> = {
  day_to_night: '白班 → 夜班',
  night_to_day: '夜班 → 白班',
  special: '临时交接',
}

function resetForm() {
  Object.assign(form, {
    shift_from: '',
    shift_to: '',
    shift_type: 'day_to_night',
    patient_id: '',
    situation: '',
    background: '',
    assessment: '',
    recommendation: '',
    pending_tasks: '',
    notes: '',
  })
}

async function fetchHandovers() {
  loading.value = true
  try {
    const res = await api.get<{ handovers: Handover[]; total: number }>('/handovers')
    handovers.value = res.handovers ?? []
  } catch (e: any) {
    toast({ tone: 'error', text: e.message ?? '加载交接班失败' })
  } finally {
    loading.value = false
  }
}

function openCreate() {
  resetForm()
  createOpen.value = true
}

async function submitHandover() {
  if (!form.shift_from.trim() || !form.shift_to.trim()) {
    toast({ tone: 'warning', text: '请填写交班人和接班人' })
    return
  }
  if (!form.situation.trim() || !form.background.trim() || !form.assessment.trim() || !form.recommendation.trim()) {
    toast({ tone: 'warning', text: '请完整填写 SBAR 四项内容' })
    return
  }
  saving.value = true
  try {
    await api.post('/handovers', {
      shift_from: form.shift_from.trim(),
      shift_to: form.shift_to.trim(),
      shift_type: form.shift_type,
      patient_id: form.patient_id.trim() || null,
      situation: form.situation.trim(),
      background: form.background.trim(),
      assessment: form.assessment.trim(),
      recommendation: form.recommendation.trim(),
      pending_tasks: form.pending_tasks.trim() || null,
      notes: form.notes.trim() || null,
    })
    toast({ tone: 'success', text: '交接班记录已创建' })
    createOpen.value = false
    await fetchHandovers()
  } catch (e: any) {
    toast({ tone: 'error', text: e.message ?? '创建失败' })
  } finally {
    saving.value = false
  }
}

async function acknowledge(h: Handover) {
  acknowledgingId.value = h.handover_id
  try {
    await api.patch(`/handovers/${h.handover_id}/acknowledge`, {
      acknowledged_by: h.shift_to,
      note: '新版管理端确认接班',
    })
    toast({ tone: 'success', text: '已确认接班' })
    await fetchHandovers()
  } catch (e: any) {
    toast({ tone: 'error', text: e.message ?? '确认失败' })
  } finally {
    acknowledgingId.value = null
  }
}

onMounted(fetchHandovers)
</script>

<template>
  <div class="handover-view">
    <div class="handover-header">
      <div>
        <h1 class="title-l">交接班记录</h1>
        <p class="meta">SBAR 交接、待办事项和接班确认都在新版完成。</p>
      </div>
      <Chip>共 {{ handovers.length }} 条</Chip>
      <Btn variant="primary" size="sm" style="margin-left: auto;" @click="openCreate">
        新增交接
      </Btn>
    </div>

    <div v-if="loading" class="empty">
      <div class="skel" style="height: 200px; width: 100%;"></div>
    </div>

    <div v-else class="handover-list stack">
      <GlassPanel
        v-for="h in handovers"
        :key="h.handover_id"
        class="handover-card"
      >
        <template #header>
          <div>
            <span class="title-s">{{ h.shift_from }} → {{ h.shift_to }}</span>
            <p class="meta">{{ shiftLabels[h.shift_type] ?? h.shift_type }}</p>
          </div>
          <Chip
            :tone="(statusMap[h.status] ?? statusMap.pending).tone"
            style="margin-left: auto;"
          >
            {{ (statusMap[h.status] ?? statusMap.pending).label }}
          </Chip>
        </template>
        <div class="sbar">
          <div><strong>S</strong> {{ h.situation }}</div>
          <div><strong>B</strong> {{ h.background }}</div>
          <div><strong>A</strong> {{ h.assessment }}</div>
          <div><strong>R</strong> {{ h.recommendation }}</div>
        </div>
        <p v-if="h.pending_tasks" class="pending">待办：{{ h.pending_tasks }}</p>
        <template #footer>
          <span class="meta">{{ h.created_at }}</span>
          <Chip v-if="h.patient_name || h.patient_id" tone="accent">
            {{ h.patient_name || h.patient_id }}
          </Chip>
          <Btn
            v-if="h.status === 'pending'"
            size="sm"
            variant="outline"
            :loading="acknowledgingId === h.handover_id"
            @click="acknowledge(h)"
          >
            确认接班
          </Btn>
        </template>
      </GlassPanel>

      <div v-if="handovers.length === 0" class="empty">
        <p class="empty-title">暂无交接记录</p>
        <p class="empty-sub">点击“新增交接”，在新版内完成 SBAR 录入和接班确认。</p>
      </div>
    </div>

    <Dialog v-model="createOpen" title="新增 SBAR 交接" panel-class="dialog--wide-form">
      <div class="handover-form">
        <Field v-model="form.shift_from" label="交班人 *" placeholder="王护士" />
        <Field v-model="form.shift_to" label="接班人 *" placeholder="李护士" />
        <Field v-model="form.shift_type" label="班次类型" type="select">
          <option value="day_to_night">白班 → 夜班</option>
          <option value="night_to_day">夜班 → 白班</option>
          <option value="special">临时交接</option>
        </Field>
        <Field v-model="form.patient_id" label="关联老人 ID" placeholder="可空，表示全区交接" />
        <Field v-model="form.situation" label="S 现状 *" type="textarea" :rows="2" class="full" />
        <Field v-model="form.background" label="B 背景 *" type="textarea" :rows="2" class="full" />
        <Field v-model="form.assessment" label="A 评估 *" type="textarea" :rows="2" class="full" />
        <Field v-model="form.recommendation" label="R 建议 *" type="textarea" :rows="2" class="full" />
        <Field v-model="form.pending_tasks" label="未完成事项" type="textarea" :rows="2" class="full" />
        <Field v-model="form.notes" label="备注" type="textarea" :rows="2" class="full" />
      </div>
      <template #actions>
        <Btn variant="ghost" :disabled="saving" @click="createOpen = false">取消</Btn>
        <Btn variant="primary" :loading="saving" @click="submitHandover">保存交接</Btn>
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.handover-view { display: grid; gap: var(--sp-4, 16px); }
.handover-header { display: flex; align-items: center; gap: var(--sp-3); flex-wrap: wrap; }
.sbar { display: grid; gap: 6px; font: 400 var(--fz-sm, 13px)/1.6 var(--font-ui); }
.sbar strong { color: var(--accent-ink, #0f766e); margin-right: 6px; font-weight: 700; }
.pending {
  margin: 10px 0 0;
  padding: 8px 10px;
  border-radius: var(--r-s, 10px);
  background: rgba(245, 158, 11, 0.08);
  color: var(--ink-2);
  font: 500 var(--fz-sm, 13px)/1.5 var(--font-ui);
}
.handover-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--sp-3, 12px);
  width: 100%;
  min-width: 0;
}
.handover-form .full { grid-column: 1 / -1; }

@media (max-width: 640px) {
  .handover-view { gap: 12px; }
  .handover-header .title-l { font-size: 20px; }
  .handover-header .btn { width: 100%; }
  .sbar {
    font-size: 13px;
    line-height: 1.7;
    padding-left: 10px;
    border-left: 3px solid rgba(20, 184, 166, 0.3);
    gap: 8px;
  }
  .sbar strong { display: inline-block; width: 20px; text-align: center; }
  .handover-card :deep(.vp-glass__footer) {
    flex-direction: column;
    align-items: flex-start;
    gap: 6px;
  }
  .handover-form {
    grid-template-columns: 1fr;
    min-width: 0;
  }
}
</style>