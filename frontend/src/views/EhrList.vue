<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { Btn, Chip, Dialog, Field, GlassPanel } from '../components'
import { useToast } from '../composables/useToast'
import { api } from '../api'
import { ApiError } from '../api/types'

/**
 * EhrList — 患者档案管理(增删改查 + PDF 导出)
 *
 * 此前(Phase 4 first cut)只是只读卡片列表,5 个字段封顶,卡片不可点击。
 * 后端早就实现了完整 CRUD + 4 个 PDF 导出端点,但前端没接,导致用户
 * "看不到全部档案,更提不上如何导出"。本次重写把这些都接上。
 *
 * 后端契约:
 *   GET    /api/ehr/list                       —— 列表(EHRListResponse)
 *   GET    /api/ehr/patients/{id}              —— 单个详情(全字段)
 *   POST   /api/ehr/patients                   —— 新增
 *   PUT    /api/ehr/patients/{id}              —— 修改
 *   DELETE /api/ehr/patients/{id}              —— 删除全部
 *   GET    /api/export/patient/{id}/pdf        —— 档案卡 PDF
 *   GET    /api/export/care-records/{id}/pdf   —— 护理记录 PDF(按日期)
 *
 * 不做的事:
 *   - 病历照片上传 + OCR(/ehr/records/upload):MVP 不阻塞主线;
 *     该流程涉及多文件上传,UI 复杂度更高,留到下一个 PR。
 */

interface EHRRecord {
  doc_id: string
  patient_id: string
  name: string
  age?: number | null
  gender?: string | null
  birth_date?: string | null
  id_card?: string | null
  admission_date?: string | null
  emergency_contact?: string | null
  emergency_phone?: string | null
  emergency_relation?: string | null
  height_cm?: number | null
  weight_kg?: number | null
  blood_type?: string | null
  care_level?: string | null
  bed_number?: string | null
  primary_nurse?: string | null
  medical_history?: string | null
  allergy?: string | null
  diet_restriction?: string | null
  notes?: string | null
}

const { push: toast } = useToast()
const records = ref<EHRRecord[]>([])
const loading = ref(false)
const searchQuery = ref('')

// ── 详情对话框 ──────────────────────────────────────
const detailOpen = ref(false)
const detailRecord = ref<EHRRecord | null>(null)
const detailLoading = ref(false)
const exportingProfile = ref(false)
const exportingCare = ref(false)
const careStartDate = ref('')
const careEndDate = ref('')

// ── 编辑对话框(新增 / 修改 共用) ────────────────────
//
// 注意:Field 组件的 v-model 只接受 string | number | string[],不接受 null。
// 而后端 EHRRecord 里 age / height / weight 是 number | null。所以表单内部
// 一律用 string 存(原生 <input type=number> 也是这样),提交时由
// buildPayload() 统一做空串过滤 + 数值转换。
type FormState = {
  patient_id: string
  name: string
  age: string
  gender: string
  birth_date: string
  id_card: string
  admission_date: string
  emergency_contact: string
  emergency_phone: string
  emergency_relation: string
  height_cm: string
  weight_kg: string
  blood_type: string
  care_level: string
  bed_number: string
  primary_nurse: string
  medical_history: string
  allergy: string
  diet_restriction: string
  notes: string
}

const formOpen = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const formSaving = ref(false)
const form = reactive<FormState>(emptyForm())

function emptyForm(): FormState {
  return {
    patient_id: '',
    name: '',
    age: '',
    gender: '',
    birth_date: '',
    id_card: '',
    admission_date: '',
    emergency_contact: '',
    emergency_phone: '',
    emergency_relation: '',
    height_cm: '',
    weight_kg: '',
    blood_type: '',
    care_level: '',
    bed_number: '',
    primary_nurse: '',
    medical_history: '',
    allergy: '',
    diet_restriction: '',
    notes: '',
  }
}

function recordToForm(r: EHRRecord): FormState {
  const f = emptyForm()
  const src = r as unknown as Record<string, unknown>
  ;(Object.keys(f) as (keyof FormState)[]).forEach((k) => {
    const v = src[k as string]
    if (v === null || v === undefined) return
    f[k] = String(v)
  })
  return f
}

// ── 删除二次确认 ────────────────────────────────────
const confirmDeleteOpen = ref(false)
const deleting = ref(false)

// ── 筛选 ────────────────────────────────────────────
const filteredRecords = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return records.value
  return records.value.filter(
    (r) =>
      r.name?.toLowerCase().includes(q) ||
      r.patient_id?.toLowerCase().includes(q) ||
      r.bed_number?.toLowerCase().includes(q),
  )
})

// ── 列表加载 ────────────────────────────────────────
async function fetchRecords() {
  loading.value = true
  try {
    const res = await api.get<{ records: EHRRecord[]; total: number }>('/ehr/list')
    records.value = res.records ?? []
  } catch (e: unknown) {
    toast({ tone: 'error', text: errMsg(e, '加载档案失败') })
  } finally {
    loading.value = false
  }
}

function errMsg(e: unknown, fallback: string): string {
  if (e instanceof ApiError) return e.message
  if (e instanceof Error) return e.message
  return fallback
}

// ── 卡片点击 → 详情 ────────────────────────────────
async function openDetail(pid: string) {
  detailOpen.value = true
  detailRecord.value = null
  detailLoading.value = true
  // 重置导出表单
  careStartDate.value = ''
  careEndDate.value = ''
  try {
    const res = await api.get<EHRRecord>(`/ehr/patients/${encodeURIComponent(pid)}`)
    detailRecord.value = res
  } catch (e: unknown) {
    toast({ tone: 'error', text: errMsg(e, '加载档案详情失败') })
    detailOpen.value = false
  } finally {
    detailLoading.value = false
  }
}

// ── PDF 导出 ────────────────────────────────────────
async function exportProfilePdf() {
  if (!detailRecord.value) return
  const pid = detailRecord.value.patient_id
  exportingProfile.value = true
  try {
    await api.download(
      `/export/patient/${encodeURIComponent(pid)}/pdf`,
      `档案卡_${detailRecord.value.name || pid}.pdf`,
    )
    toast({ tone: 'success', text: '档案卡 PDF 已开始下载' })
  } catch (e: unknown) {
    toast({ tone: 'error', text: errMsg(e, '导出档案 PDF 失败') })
  } finally {
    exportingProfile.value = false
  }
}

async function exportCareRecordsPdf() {
  if (!detailRecord.value) return
  const pid = detailRecord.value.patient_id
  // 简单本地校验:start <= end
  if (
    careStartDate.value &&
    careEndDate.value &&
    careStartDate.value > careEndDate.value
  ) {
    toast({ tone: 'error', text: '起始日期不能晚于结束日期' })
    return
  }
  exportingCare.value = true
  try {
    const params = new URLSearchParams()
    if (careStartDate.value) params.set('start_date', careStartDate.value)
    if (careEndDate.value) params.set('end_date', careEndDate.value)
    const qs = params.toString()
    const url = `/export/care-records/${encodeURIComponent(pid)}/pdf${qs ? `?${qs}` : ''}`
    await api.download(url, `护理记录_${detailRecord.value.name || pid}.pdf`)
    toast({ tone: 'success', text: '护理记录 PDF 已开始下载' })
  } catch (e: unknown) {
    toast({ tone: 'error', text: errMsg(e, '导出护理记录 PDF 失败') })
  } finally {
    exportingCare.value = false
  }
}

// ── 新增 / 编辑 ─────────────────────────────────────
function startCreate() {
  Object.assign(form, emptyForm())
  formMode.value = 'create'
  formOpen.value = true
}

function startEdit() {
  if (!detailRecord.value) return
  Object.assign(form, recordToForm(detailRecord.value))
  formMode.value = 'edit'
  detailOpen.value = false
  formOpen.value = true
}

/**
 * 把表单值清洗成后端 schema 接受的形状:
 *   - 空字符串 → 省略(否则后端 PII 字段会拿到 "" 当真值)
 *   - 数字字段从 string 转 number
 */
function buildPayload(): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  const numericKeys = new Set(['age', 'height_cm', 'weight_kg'])
  for (const [k, v] of Object.entries(form)) {
    if (typeof v !== 'string') continue
    const trimmed = v.trim()
    if (!trimmed) continue
    if (numericKeys.has(k)) {
      const n = Number(trimmed)
      if (!Number.isNaN(n)) out[k] = n
      continue
    }
    out[k] = trimmed
  }
  return out
}

async function submitForm() {
  if (!form.patient_id?.trim()) {
    toast({ tone: 'error', text: '请填写 patient_id' })
    return
  }
  if (!form.name?.trim()) {
    toast({ tone: 'error', text: '请填写姓名' })
    return
  }
  formSaving.value = true
  try {
    const payload = buildPayload()
    if (formMode.value === 'create') {
      await api.post('/ehr/patients', payload)
      toast({ tone: 'success', text: `已创建 ${form.name} 的档案` })
    } else {
      // 后端 PUT 接受部分字段;patient_id 由 URL 决定,body 里也带着以兼容旧 schema
      const pid = form.patient_id
      await api.put(`/ehr/patients/${encodeURIComponent(pid)}`, payload)
      toast({ tone: 'success', text: `已更新 ${form.name} 的档案` })
    }
    formOpen.value = false
    await fetchRecords()
    // 编辑后自动重开详情,让用户看到最新数据
    if (formMode.value === 'edit' && form.patient_id) {
      await openDetail(form.patient_id)
    }
  } catch (e: unknown) {
    toast({ tone: 'error', text: errMsg(e, '保存档案失败') })
  } finally {
    formSaving.value = false
  }
}

// ── 删除 ────────────────────────────────────────────
function startDelete() {
  if (!detailRecord.value) return
  confirmDeleteOpen.value = true
}

async function confirmDelete() {
  if (!detailRecord.value) return
  deleting.value = true
  try {
    const pid = detailRecord.value.patient_id
    await api.delete(`/ehr/patients/${encodeURIComponent(pid)}`)
    toast({ tone: 'success', text: `已删除 ${detailRecord.value.name || pid} 的全部档案` })
    confirmDeleteOpen.value = false
    detailOpen.value = false
    detailRecord.value = null
    await fetchRecords()
  } catch (e: unknown) {
    toast({ tone: 'error', text: errMsg(e, '删除失败') })
  } finally {
    deleting.value = false
  }
}

// ── 字段元信息(详情对话框按这个顺序渲染) ──────────
const detailFieldGroups: { title: string; fields: { key: keyof EHRRecord; label: string }[] }[] = [
  {
    title: '基本信息',
    fields: [
      { key: 'patient_id', label: '患者 ID' },
      { key: 'name', label: '姓名' },
      { key: 'age', label: '年龄' },
      { key: 'gender', label: '性别' },
      { key: 'birth_date', label: '出生日期' },
      { key: 'id_card', label: '身份证号' },
      { key: 'blood_type', label: '血型' },
      { key: 'height_cm', label: '身高(cm)' },
      { key: 'weight_kg', label: '体重(kg)' },
    ],
  },
  {
    title: '入住与护理',
    fields: [
      { key: 'admission_date', label: '入院日期' },
      { key: 'bed_number', label: '床位号' },
      { key: 'care_level', label: '护理等级' },
      { key: 'primary_nurse', label: '主管护工' },
    ],
  },
  {
    title: '紧急联系人',
    fields: [
      { key: 'emergency_contact', label: '联系人姓名' },
      { key: 'emergency_phone', label: '联系电话' },
      { key: 'emergency_relation', label: '关系' },
    ],
  },
  {
    title: '健康信息',
    fields: [
      { key: 'allergy', label: '过敏史' },
      { key: 'diet_restriction', label: '饮食禁忌' },
      { key: 'medical_history', label: '既往病史 / 用药' },
      { key: 'notes', label: '备注' },
    ],
  },
]

function display(v: unknown): string {
  if (v === null || v === undefined || v === '') return '—'
  return String(v)
}

onMounted(fetchRecords)
</script>

<template>
  <div class="ehr-view">
    <div class="ehr-header">
      <h1 class="title-l">患者档案</h1>
      <Chip>共 {{ records.length }} 人</Chip>
      <Btn variant="primary" size="sm" style="margin-left: auto;" @click="startCreate">
        + 新增档案
      </Btn>
    </div>

    <GlassPanel class="ehr-filters">
      <Field
        v-model="searchQuery"
        placeholder="搜索姓名 / ID / 床位号"
        style="max-width: 320px;"
      />
    </GlassPanel>

    <div v-if="loading" class="empty">
      <div class="skel" style="height: 200px; width: 100%;"></div>
    </div>

    <div v-else class="ehr-grid">
      <GlassPanel
        v-for="r in filteredRecords"
        :key="r.doc_id"
        variant="card"
        class="ehr-card"
        role="button"
        tabindex="0"
        @click="openDetail(r.patient_id)"
        @keydown.enter="openDetail(r.patient_id)"
        @keydown.space.prevent="openDetail(r.patient_id)"
      >
        <template #header>
          <span class="title-s">{{ r.name || '未知' }}</span>
          <Chip v-if="r.care_level" tone="accent" style="margin-left: auto;">
            {{ r.care_level }}
          </Chip>
        </template>
        <dl class="ehr-meta">
          <div><dt>ID</dt><dd>{{ r.patient_id }}</dd></div>
          <div v-if="r.age != null"><dt>年龄</dt><dd>{{ r.age }}</dd></div>
          <div v-if="r.gender"><dt>性别</dt><dd>{{ r.gender }}</dd></div>
          <div v-if="r.bed_number"><dt>床位</dt><dd>{{ r.bed_number }}</dd></div>
          <div v-if="r.admission_date"><dt>入院</dt><dd>{{ r.admission_date }}</dd></div>
        </dl>
        <p class="ehr-card-hint meta">点击查看完整档案 →</p>
      </GlassPanel>

      <div v-if="filteredRecords.length === 0" class="empty" style="grid-column: 1/-1;">
        <p class="empty-title">暂无匹配档案</p>
      </div>
    </div>

    <!-- ────────────── 档案详情 ────────────── -->
    <Dialog
      v-model="detailOpen"
      :title="detailRecord?.name ? `档案 · ${detailRecord.name}` : '档案详情'"
      full-sheet
    >
      <div v-if="detailLoading" class="empty">
        <div class="skel" style="height: 240px; width: 100%;"></div>
      </div>

      <div v-else-if="detailRecord" class="ehr-detail">
        <div class="ehr-detail-tags">
          <Chip>ID: {{ detailRecord.patient_id }}</Chip>
          <Chip v-if="detailRecord.care_level" tone="accent">护理等级: {{ detailRecord.care_level }}</Chip>
          <Chip v-if="detailRecord.bed_number" tone="info">床位: {{ detailRecord.bed_number }}</Chip>
          <Chip v-if="detailRecord.allergy" tone="danger">过敏: {{ detailRecord.allergy }}</Chip>
        </div>

        <section v-for="g in detailFieldGroups" :key="g.title" class="ehr-detail-section">
          <h3 class="title-s">{{ g.title }}</h3>
          <dl class="ehr-detail-grid">
            <div v-for="f in g.fields" :key="f.key">
              <dt>{{ f.label }}</dt>
              <dd>{{ display(detailRecord[f.key]) }}</dd>
            </div>
          </dl>
        </section>

        <!-- ─── 导出工具栏 ─── -->
        <section class="ehr-detail-section ehr-export">
          <h3 class="title-s">导出 PDF</h3>
          <p class="meta">
            档案卡用于卫生局检查留底；护理记录可按日期范围导出最近班次。
          </p>
          <div class="ehr-export-actions">
            <Btn variant="primary" size="sm" :loading="exportingProfile" @click="exportProfilePdf">
              下载档案卡 PDF
            </Btn>
          </div>

          <div class="ehr-export-care">
            <Field v-model="careStartDate" type="date" label="起始日期" />
            <Field v-model="careEndDate" type="date" label="结束日期" />
            <Btn variant="outline" size="sm" :loading="exportingCare" @click="exportCareRecordsPdf">
              下载护理记录 PDF
            </Btn>
          </div>
          <p class="meta">日期可留空——留空导出最近 200 条护理记录。</p>
        </section>
      </div>

      <template #actions>
        <Btn variant="ghost" @click="detailOpen = false">关闭</Btn>
        <Btn v-if="detailRecord" variant="danger" @click="startDelete">删除档案</Btn>
        <Btn v-if="detailRecord" variant="primary" @click="startEdit">编辑</Btn>
      </template>
    </Dialog>

    <!-- ────────────── 新增 / 编辑 表单 ────────────── -->
    <Dialog
      v-model="formOpen"
      :title="formMode === 'create' ? '新增患者档案' : `编辑档案 · ${form.name || form.patient_id}`"
      full-sheet
    >
      <form class="ehr-form" @submit.prevent="submitForm">
        <div class="ehr-form-grid">
          <Field
            v-model="form.patient_id"
            label="患者 ID"
            required
            :disabled="formMode === 'edit'"
            placeholder="例如:P001"
          />
          <Field v-model="form.name" label="姓名" required />
          <Field v-model="form.age" label="年龄" type="number" />
          <Field v-model="form.gender" label="性别" placeholder="男 / 女" />
          <Field v-model="form.birth_date" label="出生日期" type="date" />
          <Field v-model="form.id_card" label="身份证号" />
          <Field v-model="form.blood_type" label="血型" placeholder="A / B / AB / O" />
          <Field v-model="form.height_cm" label="身高(cm)" type="number" />
          <Field v-model="form.weight_kg" label="体重(kg)" type="number" />
          <Field v-model="form.admission_date" label="入院日期" type="date" />
          <Field v-model="form.bed_number" label="床位号" />
          <Field v-model="form.care_level" label="护理等级" placeholder="一级 / 二级 / 特护" />
          <Field v-model="form.primary_nurse" label="主管护工" />
          <Field v-model="form.emergency_contact" label="紧急联系人" />
          <Field v-model="form.emergency_phone" label="联系电话" />
          <Field v-model="form.emergency_relation" label="关系" placeholder="子女 / 配偶 …" />
          <Field v-model="form.allergy" label="过敏史" />
          <Field v-model="form.diet_restriction" label="饮食禁忌" />
        </div>
        <Field
          v-model="form.medical_history"
          label="既往病史 / 用药"
          type="textarea"
          :rows="3"
        />
        <Field v-model="form.notes" label="备注" type="textarea" :rows="2" />
      </form>

      <template #actions>
        <Btn variant="ghost" :disabled="formSaving" @click="formOpen = false">取消</Btn>
        <Btn variant="primary" :loading="formSaving" @click="submitForm">
          {{ formMode === 'create' ? '创建' : '保存' }}
        </Btn>
      </template>
    </Dialog>

    <!-- ────────────── 删除确认 ────────────── -->
    <Dialog v-model="confirmDeleteOpen" title="确认删除档案?">
      <p class="body-m">
        将删除患者
        <strong>{{ detailRecord?.name }}</strong>
        ({{ detailRecord?.patient_id }})的<strong>全部</strong>档案、病历照片与 OCR 文本,
        此操作不可撤销。
      </p>
      <template #actions>
        <Btn variant="ghost" :disabled="deleting" @click="confirmDeleteOpen = false">
          取消
        </Btn>
        <Btn variant="danger" :loading="deleting" @click="confirmDelete">
          确认删除
        </Btn>
      </template>
    </Dialog>

    <!-- ─── 移动端 FAB:新增档案 ─── -->
    <button
      type="button"
      class="app-fab"
      aria-label="新增档案"
      @click="startCreate"
    >
      +
    </button>
  </div>
</template>

<style scoped>
.ehr-view { display: grid; gap: var(--sp-4, 16px); }
.ehr-header { display: flex; align-items: center; gap: var(--sp-3); }
.ehr-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: var(--sp-3); }

.ehr-card {
  cursor: pointer;
  transition: transform 120ms ease, box-shadow 120ms ease, border-color 120ms ease;
}
.ehr-card:hover {
  transform: translateY(-2px);
  border-color: rgba(20, 184, 166, 0.3);
  box-shadow: var(--shadow-3, 0 18px 48px rgba(20, 184, 166, 0.10));
}
.ehr-card:focus-visible {
  outline: 2px solid var(--accent-ink, #0f766e);
  outline-offset: 2px;
}
.ehr-card-hint {
  margin-top: var(--sp-2, 8px);
  color: var(--accent-ink, #0f766e);
  font-size: var(--fz-xs, 11px);
}

.ehr-meta { display: grid; gap: 4px; font: 400 var(--fz-sm, 13px)/1.5 var(--font-ui); }
.ehr-meta div { display: grid; grid-template-columns: 60px 1fr; gap: 8px; }
.ehr-meta dt { color: var(--ink-3); }
.ehr-meta dd { margin: 0; }

/* ─── 详情 ─── */
.ehr-detail {
  display: grid;
  gap: var(--sp-4, 16px);
  max-width: 720px;
}
.ehr-detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.ehr-detail-section { display: grid; gap: var(--sp-2, 8px); }
.ehr-detail-section h3 { margin: 0; }
.ehr-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--sp-2, 8px) var(--sp-3, 12px);
  font: 400 var(--fz-sm, 13px)/1.5 var(--font-ui);
  margin: 0;
}
.ehr-detail-grid div {
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: 8px;
  padding: 4px 0;
  border-bottom: 1px dashed rgba(15, 23, 42, 0.06);
}
.ehr-detail-grid dt { color: var(--ink-4); margin: 0; }
.ehr-detail-grid dd { margin: 0; word-break: break-word; }

.ehr-export {
  padding: var(--sp-3, 12px);
  border-radius: var(--r-m, 12px);
  background: rgba(20, 184, 166, 0.06);
  border: 1px solid rgba(20, 184, 166, 0.2);
}
.ehr-export-actions {
  display: flex;
  gap: var(--sp-2, 8px);
  flex-wrap: wrap;
  margin-top: var(--sp-2, 8px);
}
.ehr-export-care {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  align-items: end;
  gap: var(--sp-2, 8px);
  margin-top: var(--sp-3, 12px);
}

/* ─── 表单 ─── */
.ehr-form { display: grid; gap: var(--sp-3, 12px); max-width: 720px; }
.ehr-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--sp-2, 8px) var(--sp-3, 12px);
}

@media (max-width: 640px) {
  .ehr-header {
    flex-wrap: wrap;
    gap: 8px;
  }
  /* 移动端隐藏 header 里的"新增"按钮(改用右下 FAB,见模板末尾) */
  .ehr-header > .btn { display: none; }
  .ehr-header .title-l { font-size: 20px; width: 100%; }

  .ehr-filters { padding: 10px !important; }
  .ehr-filters :deep(.field) {
    max-width: none !important;
    width: 100%;
  }

  .ehr-grid {
    grid-template-columns: 1fr;
    gap: 10px;
  }
  .ehr-card { padding: 14px !important; }
  .ehr-meta { font-size: 13px; }
  .ehr-meta div { grid-template-columns: 60px 1fr; }

  .ehr-detail-grid,
  .ehr-form-grid { grid-template-columns: 1fr; }
  .ehr-detail-grid div { grid-template-columns: 80px 1fr; }
  .ehr-export-care { grid-template-columns: 1fr; }
  .ehr-export-actions .btn { width: 100%; }
  .ehr-export-care .btn { width: 100%; height: 44px; }
}

@media (max-width: 480px) {
  .ehr-header .title-l { font-size: 18px; }
  .ehr-meta { font-size: 12px; }
  .ehr-detail-grid div { grid-template-columns: 72px 1fr; font-size: 12px; }
}
</style>
