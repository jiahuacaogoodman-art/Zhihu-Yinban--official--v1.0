<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Btn, Field, GlassPanel, Chip } from '../components'
import { useToast } from '../composables/useToast'
import { api } from '../api'

interface AuditRecord { action: string; patient_id: string; operator: string; ts: string; detail?: string; diff?: Record<string, any> }

const { push: toast } = useToast()
const records = ref<AuditRecord[]>([])
const loading = ref(false)
const actionFilter = ref('')
const patientFilter = ref('')
const actionOptions = [
  { value: '', label: '全部操作' },
  { value: 'PATIENT_CREATE', label: '新建档案' },
  { value: 'PATIENT_UPDATE', label: '修改档案' },
  { value: 'PATIENT_DELETE', label: '删除档案' },
  { value: 'RECORD_UPLOAD', label: '上传病历' },
  { value: 'RECORD_DELETE', label: '删除病历' },
]

async function loadAudit() {
  loading.value = true
  try {
    let url = '/ehr/audit?limit=100'
    if (actionFilter.value) url += `&action=${encodeURIComponent(actionFilter.value)}`
    if (patientFilter.value.trim()) url += `&patient_id=${encodeURIComponent(patientFilter.value.trim())}`
    const res = await api.get<any>(url)
    records.value = res.records ?? []
  } catch (e: any) {
    if (e.status === 403 || e.status === 401) toast({ tone: 'warning', text: '需要 admin 权限查看审计日志' })
    else toast({ tone: 'error', text: e.message ?? '加载失败' })
  } finally { loading.value = false }
}

function actionTone(action: string) {
  if (action?.includes('DELETE')) return 'danger'
  if (action?.includes('CREATE')) return 'success'
  return 'info'
}

onMounted(loadAudit)
</script>

<template>
  <div class="al-view">
    <GlassPanel variant="card">
      <template #header><span class="title-l">审计日志</span><p class="meta">全部档案写操作留痕（admin 可查）</p></template>
      <div class="al-filters">
        <div class="field-group"><span class="field-label">操作类型</span>
          <select v-model="actionFilter" class="field" @change="loadAudit">
            <option v-for="o in actionOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
          </select>
        </div>
        <Field v-model="patientFilter" label="按 patient_id" placeholder="输入编号筛选" @keyup.enter="loadAudit" />
        <Btn variant="outline" size="sm" @click="loadAudit" style="align-self: end;">刷新</Btn>
      </div>
      <div v-if="loading" class="empty"><p>加载中…</p></div>
      <div v-else-if="records.length === 0" class="empty"><p class="empty-title">暂无审计记录</p></div>
      <div v-else class="al-list">
        <div v-for="(r, i) in records" :key="i" class="al-row">
          <Chip :tone="actionTone(r.action)">{{ r.action }}</Chip>
          <div class="al-content">
            <span class="body-s">{{ r.patient_id }} · 操作者: {{ r.operator }}</span>
            <span v-if="r.detail" class="meta">{{ r.detail }}</span>
            <span v-if="r.diff && Object.keys(r.diff).length" class="meta" style="color: var(--ink-4);">变更: {{ JSON.stringify(r.diff).slice(0, 120) }}</span>
          </div>
          <span class="meta al-time">{{ r.ts }}</span>
        </div>
      </div>
    </GlassPanel>
  </div>
</template>

<style scoped>
.al-view { max-width: 900px; }
.al-filters { display: grid; grid-template-columns: 1fr 1fr auto; gap: var(--sp-2, 8px); margin-bottom: var(--sp-4, 16px); align-items: end; }
.field-group { display: flex; flex-direction: column; gap: 4px; }
.field-label { font: 600 var(--fz-xs, 11px)/1.4 var(--font-ui); color: var(--ink-3); }
.al-list { display: grid; gap: 6px; }
.al-row { display: grid; grid-template-columns: auto 1fr auto; gap: 10px; align-items: start; padding: 10px 12px; border-radius: 8px; background: rgba(15,23,42,0.02); }
.al-content { display: flex; flex-direction: column; gap: 2px; }
.al-time { white-space: nowrap; }
@media (max-width: 640px) { .al-filters { grid-template-columns: 1fr; } .al-row { grid-template-columns: 1fr; } }
</style>
