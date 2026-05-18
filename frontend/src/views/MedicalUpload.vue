<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Btn, Field, GlassPanel, Chip } from '../components'
import { useToast } from '../composables/useToast'
import { api } from '../api'

interface Patient { patient_id: string; name: string }
interface MedicalRecord { doc_id: string; file_url: string; record_type: string; ocr_text?: string; manual_text?: string; ocr_status?: string; ocr_engine?: string; uploaded_at?: string; notes?: string }

const { push: toast } = useToast()
const patients = ref<Patient[]>([])
const selectedPid = ref('')
const selectedName = ref('')
const recordType = ref('门诊病历')
const recordNotes = ref('')
const manualText = ref('')
const uploading = ref(false)
const records = ref<MedicalRecord[]>([])
const fileInput = ref<HTMLInputElement | null>(null)
const recordTypes = ['门诊病历', '住院记录', '出院小结', '检查报告', '检验报告', '用药清单', '其他病历']

async function loadPatients() {
  try {
    const res = await api.get<Patient[] | { records: Patient[] }>('/ehr/patients')
    patients.value = Array.isArray(res) ? res : (res as any).records ?? []
  } catch {}
}

function onPatientSelect() {
  const p = patients.value.find((x) => x.patient_id === selectedPid.value)
  selectedName.value = p?.name ?? ''
  if (selectedPid.value) loadRecords()
}

async function loadRecords() {
  if (!selectedPid.value) return
  try {
    const res = await api.get<any>(`/ehr/records/${encodeURIComponent(selectedPid.value)}`)
    records.value = res.records ?? []
  } catch { records.value = [] }
}

async function upload() {
  if (!selectedPid.value) { toast({ tone: 'warning', text: '请先选择老人' }); return }
  const files = fileInput.value?.files
  if (!files || files.length === 0) { toast({ tone: 'warning', text: '请选择病历照片' }); return }
  uploading.value = true
  try {
    const token = localStorage.getItem('auth_token') || ''
    const fd = new FormData()
    fd.append('patient_id', selectedPid.value)
    if (selectedName.value) fd.append('name', selectedName.value)
    fd.append('record_type', recordType.value)
    fd.append('notes', recordNotes.value)
    fd.append('manual_text', manualText.value)
    Array.from(files).forEach((f) => fd.append('files', f))
    const res = await fetch('/api/ehr/records/upload', {
      method: 'POST', headers: token ? { 'X-Auth-Token': token } : {}, body: fd,
    })
    const d = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(d.detail || '上传失败')
    const hasWarn = (d.records || []).some((x: any) => x.ocr_status !== 'ocr_success')
    toast({ tone: 'success', text: hasWarn ? '照片已保存；部分文字未识别' : '病历和文字识别结果已保存' })
    if (fileInput.value) fileInput.value.value = ''
    manualText.value = ''; recordNotes.value = ''
    loadRecords()
  } catch (e: any) { toast({ tone: 'error', text: e.message ?? '上传失败' }) }
  finally { uploading.value = false }
}

async function deleteRecord(docId: string) {
  if (!confirm('确定要删除这份病历？')) return
  try { await api.delete(`/ehr/records/${encodeURIComponent(docId)}`); toast({ tone: 'success', text: '已删除' }); loadRecords() }
  catch (e: any) { toast({ tone: 'error', text: e.message ?? '删除失败' }) }
}

onMounted(loadPatients)
</script>

<template>
  <div class="mu-view">
    <GlassPanel variant="card">
      <template #header><span class="title-l">病历上传</span><p class="meta">上传病历照片，系统自动 OCR 识别文字并归入老人档案</p></template>
      <div class="form-grid cols-3">
        <div class="field-group"><span class="field-label">选择老人 *</span>
          <select v-model="selectedPid" class="field" @change="onPatientSelect">
            <option value="">— 请选择 —</option>
            <option v-for="p in patients" :key="p.patient_id" :value="p.patient_id">{{ p.name }}（{{ p.patient_id }}）</option>
          </select>
        </div>
        <Field v-model="selectedName" label="姓名" placeholder="自动带入" disabled />
        <div class="field-group"><span class="field-label">病历类型</span>
          <select v-model="recordType" class="field"><option v-for="t in recordTypes" :key="t">{{ t }}</option></select>
        </div>
      </div>
      <div class="mu-upload-area">
        <p class="title-s">病历照片 *</p>
        <p class="meta">支持 JPG / PNG / WEBP / BMP / TIFF，可一次上传多张</p>
        <input ref="fileInput" type="file" accept="image/*" multiple />
      </div>
      <Field v-model="manualText" label="手动补充文字（可选）" type="textarea" :rows="3" placeholder="如果照片不清、OCR 不准，可在此补录" />
      <Field v-model="recordNotes" label="备注" type="textarea" :rows="2" placeholder="例如：2026-04-26 门诊" />
      <div class="mu-footer"><Btn variant="primary" :loading="uploading" @click="upload">上传并识别文字</Btn></div>
    </GlassPanel>

    <GlassPanel v-if="records.length > 0">
      <template #header><span class="title-s">已上传病历（{{ records.length }}）</span></template>
      <div class="mu-records">
        <div v-for="r in records" :key="r.doc_id" class="mu-record-card">
          <img v-if="r.file_url" :src="r.file_url" alt="病历照片" class="mu-thumb" loading="lazy" />
          <div class="mu-record-info">
            <div class="body-s"><strong>{{ r.record_type || '病历' }}</strong></div>
            <div class="meta">{{ r.uploaded_at ?? '' }} · 引擎: {{ r.ocr_engine ?? '无' }}</div>
            <Chip :tone="r.ocr_status === 'ocr_success' ? 'success' : 'warning'">{{ r.ocr_status === 'ocr_success' ? '已识别' : '待校对' }}</Chip>
            <p class="mu-ocr-text">{{ (r.ocr_text || r.manual_text || '未识别到文字').slice(0, 200) }}</p>
            <div class="mu-actions">
              <a v-if="r.file_url" :href="r.file_url" target="_blank" class="btn btn-outline btn-sm">查看原图</a>
              <Btn variant="ghost" size="sm" @click="deleteRecord(r.doc_id)">删除</Btn>
            </div>
          </div>
        </div>
      </div>
    </GlassPanel>
    <div v-else-if="selectedPid" class="empty"><p class="empty-title">该老人暂无病历照片</p></div>
  </div>
</template>

<style scoped>
.mu-view { display: grid; gap: var(--sp-4, 16px); max-width: 900px; }
.form-grid { display: grid; gap: var(--sp-2, 8px); margin-bottom: var(--sp-3, 12px); }
.form-grid.cols-3 { grid-template-columns: repeat(3, 1fr); }
.field-group { display: flex; flex-direction: column; gap: 4px; }
.field-label { font: 600 var(--fz-xs, 11px)/1.4 var(--font-ui); color: var(--ink-3); }
.mu-upload-area { margin: var(--sp-3, 12px) 0; padding: var(--sp-4, 16px); border: 2px dashed rgba(15, 23, 42, 0.12); border-radius: var(--r-s, 10px); text-align: center; }
.mu-footer { margin-top: var(--sp-4, 16px); display: flex; justify-content: flex-end; }
.mu-records { display: grid; gap: 12px; }
.mu-record-card { display: grid; grid-template-columns: 100px 1fr; gap: 12px; padding: 12px; border-radius: var(--r-s, 10px); background: rgba(255,255,255,0.75); border: 1px solid rgba(15,23,42,0.06); }
.mu-thumb { width: 100px; height: 80px; object-fit: cover; border-radius: 8px; }
.mu-ocr-text { font: 400 var(--fz-xs, 11px)/1.5 var(--font-ui); color: var(--ink-3); margin-top: 4px; }
.mu-actions { display: flex; gap: 6px; margin-top: 8px; }
@media (max-width: 640px) { .form-grid.cols-3 { grid-template-columns: 1fr; } .mu-record-card { grid-template-columns: 1fr; } .mu-thumb { width: 100%; height: 120px; } }
</style>
