<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Btn, Chip, Dialog, Field, GlassPanel } from '../components'
import { useToast } from '../composables/useToast'
import { api } from '../api'

interface Incident {
  incident_id: string
  patient_id: string
  patient_name: string | null
  incident_type: string
  severity: string
  status: string
  description: string
  location?: string | null
  occurred_at?: string | null
  reporter: string | null
  immediate_action?: string | null
  created_at: string
}

const { push: toast } = useToast()
const incidents = ref<Incident[]>([])
const loading = ref(false)
const createOpen = ref(false)
const saving = ref(false)
const updatingId = ref<string | null>(null)

const form = reactive({
  patient_id: '',
  incident_type: '',
  severity: 'minor',
  description: '',
  location: '',
  occurred_at: '',
  reporter: '',
  witnesses: '',
  immediate_action: '',
})

const severityMap: Record<string, { label: string; tone: 'danger' | 'warning' | 'info' | 'neutral' }> = {
  critical: { label: '严重', tone: 'danger' },
  major: { label: '较重', tone: 'warning' },
  minor: { label: '轻微', tone: 'info' },
  observation: { label: '观察', tone: 'neutral' },
}

const statusMap: Record<string, { label: string; tone: 'danger' | 'warning' | 'info' | 'success' }> = {
  reported: { label: '已上报', tone: 'warning' },
  processing: { label: '处理中', tone: 'info' },
  resolved: { label: '已处理', tone: 'success' },
  closed: { label: '已关闭', tone: 'success' },
}

function resetForm() {
  Object.assign(form, {
    patient_id: '',
    incident_type: '',
    severity: 'minor',
    description: '',
    location: '',
    occurred_at: '',
    reporter: '',
    witnesses: '',
    immediate_action: '',
  })
}

async function fetchIncidents() {
  loading.value = true
  try {
    const res = await api.get<{ incidents: Incident[]; total: number }>('/incidents')
    incidents.value = res.incidents ?? []
  } catch (e: any) {
    toast({ tone: 'error', text: e.message ?? '加载异常事件失败' })
  } finally {
    loading.value = false
  }
}

function openCreate() {
  resetForm()
  createOpen.value = true
}

async function submitIncident() {
  if (!form.patient_id.trim()) {
    toast({ tone: 'warning', text: '请填写老人 ID' })
    return
  }
  if (!form.incident_type.trim() || !form.description.trim()) {
    toast({ tone: 'warning', text: '请填写事件类型和详细描述' })
    return
  }
  saving.value = true
  try {
    await api.post('/incidents', {
      patient_id: form.patient_id.trim(),
      incident_type: form.incident_type.trim(),
      severity: form.severity,
      description: form.description.trim(),
      location: form.location.trim() || null,
      occurred_at: form.occurred_at.trim() || null,
      reporter: form.reporter.trim() || null,
      witnesses: form.witnesses.trim() || null,
      immediate_action: form.immediate_action.trim() || null,
    })
    toast({ tone: 'success', text: '异常事件已上报' })
    createOpen.value = false
    await fetchIncidents()
  } catch (e: any) {
    toast({ tone: 'error', text: e.message ?? '上报失败' })
  } finally {
    saving.value = false
  }
}

async function setStatus(incident: Incident, status: 'processing' | 'resolved' | 'closed') {
  updatingId.value = incident.incident_id
  try {
    await api.patch(`/incidents/${incident.incident_id}`, { status })
    toast({ tone: 'success', text: '事件状态已更新' })
    await fetchIncidents()
  } catch (e: any) {
    toast({ tone: 'error', text: e.message ?? '更新失败' })
  } finally {
    updatingId.value = null
  }
}

onMounted(fetchIncidents)
</script>

<template>
  <div class="incident-view">
    <div class="incident-header">
      <div>
        <h1 class="title-l">异常事件</h1>
        <p class="meta">上报、跟踪和关闭异常事件，统一在新版闭环。</p>
      </div>
      <Chip>共 {{ incidents.length }} 条</Chip>
      <Btn variant="primary" size="sm" style="margin-left: auto;" @click="openCreate">
        上报事件
      </Btn>
    </div>

    <div v-if="loading" class="empty">
      <div class="skel" style="height: 200px; width: 100%;"></div>
    </div>

    <div v-else class="incident-list stack">
      <GlassPanel
        v-for="i in incidents"
        :key="i.incident_id"
        class="incident-card"
      >
        <template #header>
          <div>
            <span class="title-s">{{ i.incident_type }}</span>
            <p class="meta">
              {{ i.patient_name || i.patient_id }}
              <span v-if="i.location"> · {{ i.location }}</span>
            </p>
          </div>
          <Chip
            :tone="(severityMap[i.severity] ?? severityMap.minor).tone"
            style="margin-left: auto;"
          >
            {{ (severityMap[i.severity] ?? severityMap.minor).label }}
          </Chip>
          <Chip :tone="(statusMap[i.status] ?? statusMap.reported).tone">
            {{ (statusMap[i.status] ?? statusMap.reported).label }}
          </Chip>
        </template>
        <p class="body-s">{{ i.description }}</p>
        <p v-if="i.immediate_action" class="incident-action">
          紧急措施：{{ i.immediate_action }}
        </p>
        <template #footer>
          <span class="meta">{{ i.occurred_at || i.created_at }}</span>
          <span v-if="i.reporter" class="meta">上报: {{ i.reporter }}</span>
          <Btn
            v-if="i.status === 'reported'"
            size="sm"
            variant="outline"
            :loading="updatingId === i.incident_id"
            @click="setStatus(i, 'processing')"
          >
            开始处理
          </Btn>
          <Btn
            v-if="i.status === 'reported' || i.status === 'processing'"
            size="sm"
            variant="primary"
            :loading="updatingId === i.incident_id"
            @click="setStatus(i, 'resolved')"
          >
            标记已处理
          </Btn>
        </template>
      </GlassPanel>

      <div v-if="incidents.length === 0" class="empty">
        <p class="empty-title">暂无异常事件</p>
        <p class="empty-sub">没有事件是好事。新发生的异常可直接点击“上报事件”。</p>
      </div>
    </div>

    <Dialog v-model="createOpen" title="上报异常事件" panel-class="dialog--wide-form">
      <div class="incident-form">
        <Field v-model="form.patient_id" label="老人 ID *" placeholder="P001" />
        <Field v-model="form.incident_type" label="事件类型 *" placeholder="跌倒 / 误吸 / 走失 / 用药错误" />
        <Field v-model="form.severity" label="严重程度" type="select">
          <option value="observation">观察</option>
          <option value="minor">轻微</option>
          <option value="major">较重</option>
          <option value="critical">严重</option>
        </Field>
        <Field v-model="form.location" label="发生地点" placeholder="三楼走廊" />
        <Field v-model="form.occurred_at" label="发生时间" placeholder="留空=上报时间" />
        <Field v-model="form.reporter" label="上报人" placeholder="留空则使用当前账号" />
        <Field v-model="form.witnesses" label="目击者" placeholder="可选" />
        <Field v-model="form.description" label="详细描述 *" type="textarea" :rows="4" class="full" />
        <Field v-model="form.immediate_action" label="已采取紧急措施" type="textarea" :rows="2" class="full" />
      </div>
      <template #actions>
        <Btn variant="ghost" :disabled="saving" @click="createOpen = false">取消</Btn>
        <Btn variant="primary" :loading="saving" @click="submitIncident">提交上报</Btn>
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.incident-view { display: grid; gap: var(--sp-4, 16px); }
.incident-header { display: flex; align-items: center; gap: var(--sp-3); flex-wrap: wrap; }
.incident-action {
  margin: 8px 0 0;
  padding: 8px 10px;
  border-radius: var(--r-s, 10px);
  background: rgba(239, 68, 68, 0.07);
  color: var(--ink-2);
  font: 500 var(--fz-sm, 13px)/1.5 var(--font-ui);
}
.incident-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--sp-3, 12px);
  width: 100%;
  min-width: 0;
}
.incident-form .full { grid-column: 1 / -1; }

@media (max-width: 640px) {
  .incident-view { gap: 12px; }
  .incident-header .title-l { font-size: 20px; }
  .incident-header .btn { width: 100%; }
  .incident-card :deep(.vp-glass__body) .body-s {
    font-size: 13px;
    line-height: 1.65;
  }
  .incident-card :deep(.vp-glass__footer) {
    flex-wrap: wrap;
    gap: 6px;
  }
  .incident-form {
    grid-template-columns: 1fr;
    min-width: 0;
  }
}
</style>