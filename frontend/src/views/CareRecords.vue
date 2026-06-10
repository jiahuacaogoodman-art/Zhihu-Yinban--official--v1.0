<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Btn, Chip, Dialog, Field, GlassPanel } from '../components'
import { useToast } from '../composables/useToast'
import { api } from '../api'

interface CareRecord {
  record_id: string
  patient_id: string
  patient_name: string | null
  record_type: string
  content: string
  vital_data?: string | null
  recorded_by: string | null
  recorded_at: string
  shift: string | null
  notes?: string | null
}

const { push: toast } = useToast()
const records = ref<CareRecord[]>([])
const loading = ref(false)
const createOpen = ref(false)
const saving = ref(false)

const form = reactive({
  patient_id: '',
  record_type: 'observation',
  content: '',
  vital_data: '',
  recorded_by: '',
  recorded_at: '',
  shift: 'day',
  notes: '',
})

const typeLabels: Record<string, string> = {
  vital_signs: '生命体征',
  daily_care: '日常护理',
  medication: '用药',
  diet: '饮食',
  activity: '活动',
  observation: '观察',
  special_care: '特殊护理',
  other: '其他',
}

const shiftLabels: Record<string, string> = {
  day: '白班',
  night: '夜班',
  swing: '中班',
}

function resetForm() {
  Object.assign(form, {
    patient_id: '',
    record_type: 'observation',
    content: '',
    vital_data: '',
    recorded_by: '',
    recorded_at: '',
    shift: 'day',
    notes: '',
  })
}

async function fetchRecords() {
  loading.value = true
  try {
    const res = await api.get<{ records: CareRecord[]; total: number }>('/care-records')
    records.value = res.records ?? []
  } catch (e: any) {
    toast({ tone: 'error', text: e.message ?? '加载护理记录失败' })
  } finally {
    loading.value = false
  }
}

function openCreate() {
  resetForm()
  createOpen.value = true
}

async function submitRecord() {
  if (!form.patient_id.trim()) {
    toast({ tone: 'warning', text: '请填写老人 ID' })
    return
  }
  if (!form.content.trim()) {
    toast({ tone: 'warning', text: '请填写护理记录内容' })
    return
  }
  saving.value = true
  try {
    await api.post('/care-records', {
      patient_id: form.patient_id.trim(),
      record_type: form.record_type,
      content: form.content.trim(),
      vital_data: form.vital_data.trim() || null,
      recorded_by: form.recorded_by.trim() || null,
      recorded_at: form.recorded_at || null,
      shift: form.shift || null,
      notes: form.notes.trim() || null,
    })
    toast({ tone: 'success', text: '护理记录已保存' })
    createOpen.value = false
    await fetchRecords()
  } catch (e: any) {
    toast({ tone: 'error', text: e.message ?? '保存失败' })
  } finally {
    saving.value = false
  }
}

onMounted(fetchRecords)
</script>

<template>
  <div class="care-record-view">
    <div class="care-record-header">
      <div>
        <h1 class="title-l">护理记录</h1>
        <p class="meta">护理留痕、生命体征、班次记录统一在新版录入。</p>
      </div>
      <Chip>共 {{ records.length }} 条</Chip>
      <Btn variant="primary" size="sm" style="margin-left: auto;" @click="openCreate">
        新增记录
      </Btn>
    </div>

    <div v-if="loading" class="empty">
      <div class="skel" style="height: 200px; width: 100%;"></div>
    </div>

    <div v-else class="care-record-list stack">
      <GlassPanel
        v-for="r in records"
        :key="r.record_id"
      >
        <template #header>
          <Chip tone="accent">{{ typeLabels[r.record_type] ?? r.record_type }}</Chip>
          <span v-if="r.patient_name || r.patient_id" class="title-s" style="margin-left: var(--sp-2);">
            {{ r.patient_name || r.patient_id }}
          </span>
        </template>
        <p class="body-s">{{ r.content }}</p>
        <p v-if="r.vital_data" class="record-extra">体征：{{ r.vital_data }}</p>
        <template #footer>
          <span class="meta">{{ r.recorded_at }}</span>
          <span v-if="r.recorded_by" class="meta">记录人: {{ r.recorded_by }}</span>
          <Chip v-if="r.shift" tone="info">{{ shiftLabels[r.shift] ?? r.shift }}</Chip>
        </template>
      </GlassPanel>

      <div v-if="records.length === 0" class="empty">
        <p class="empty-title">暂无护理记录</p>
        <p class="empty-sub">点击“新增记录”，在新版内完成护理留痕。</p>
      </div>
    </div>

    <Dialog v-model="createOpen" title="新增护理记录" panel-class="dialog--workflow-form">
      <div class="care-form">
        <Field v-model="form.patient_id" label="老人 ID *" placeholder="P001" />
        <Field v-model="form.record_type" label="记录类型" type="select">
          <option v-for="(label, key) in typeLabels" :key="key" :value="key">{{ label }}</option>
        </Field>
        <Field v-model="form.recorded_by" label="记录人" placeholder="留空则使用当前账号" />
        <Field v-model="form.recorded_at" label="记录时间" type="text" placeholder="留空=当前时间" />
        <Field v-model="form.shift" label="班次" type="select">
          <option value="day">白班</option>
          <option value="night">夜班</option>
          <option value="swing">中班</option>
        </Field>
        <Field v-model="form.vital_data" label="生命体征" placeholder='如 {"bp":"128/76","temp":36.5}' />
        <Field v-model="form.content" label="护理内容 *" type="textarea" :rows="4" class="full" />
        <Field v-model="form.notes" label="备注" type="textarea" :rows="2" class="full" />
      </div>
      <template #actions>
        <Btn variant="ghost" :disabled="saving" @click="createOpen = false">取消</Btn>
        <Btn variant="primary" :loading="saving" @click="submitRecord">保存记录</Btn>
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.care-record-view { display: grid; gap: var(--sp-4, 16px); }
.care-record-header { display: flex; align-items: center; gap: var(--sp-3); flex-wrap: wrap; }
.record-extra {
  margin: 8px 0 0;
  padding: 8px 10px;
  border-radius: var(--r-s, 10px);
  background: rgba(20, 184, 166, 0.08);
  color: var(--ink-2);
  font: 500 var(--fz-sm, 13px)/1.5 var(--font-ui);
}
.care-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--sp-3, 12px);
  width: 100%;
  min-width: 0;
}
.care-form .full { grid-column: 1 / -1; }

@media (max-width: 640px) {
  .care-record-view { gap: 12px; }
  .care-record-header .title-l { font-size: 20px; }
  .care-record-header .btn { width: 100%; }
  .care-record-view :deep(.vp-glass__body) .body-s {
    font-size: 13px;
    line-height: 1.7;
  }
  .care-record-view :deep(.vp-glass__header) {
    gap: 6px;
    flex-wrap: wrap;
  }
  .care-record-view :deep(.vp-glass__footer) {
    flex-wrap: wrap;
    gap: 4px;
  }
  .care-form {
    grid-template-columns: 1fr;
    min-width: 0;
  }
}
</style>