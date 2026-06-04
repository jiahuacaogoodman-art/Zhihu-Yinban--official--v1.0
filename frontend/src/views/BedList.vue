<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useBedStore } from '../stores'
import { Btn, Chip, GlassPanel, Field, Dialog, PullToRefresh, Skeleton } from '../components'
import { useToast } from '../composables/useToast'
import type { Bed, BedFormPayload, BedStatus } from '../api/types'

/**
 * BedList — 床位管理视图
 *
 * 功能覆盖:
 *   - 查看所有床位(按状态筛选)
 *   - 按楼栋筛选
 *   - 新增 / 编辑 / 删除床位
 *   - 释放已占用床位
 *   - 分配空闲床位
 *   - 批量操作
 *   - 分页(当前场景 < 100 张床,全量拉取够用)
 */

const bedStore = useBedStore()
const { push } = useToast()

interface BedFormState {
  bed_number: string
  floor: string
  building: string
  room: string
  bed_type: string
  status: BedStatus
  notes: string
}

const statusFilter = ref<BedStatus | ''>('')
const buildingFilter = ref('')

// Dialog
const assignDialogOpen = ref(false)
const assignTargetBed = ref<Bed | null>(null)
const assignPatientId = ref('')
const bedDialogOpen = ref(false)
const bedDialogMode = ref<'create' | 'edit'>('create')
const editTargetBed = ref<Bed | null>(null)
const savingBed = ref(false)
const bedForm = ref<BedFormState>({
  bed_number: '',
  floor: '',
  building: '',
  room: '',
  bed_type: 'standard',
  status: 'available',
  notes: '',
})

const filteredBeds = computed(() => {
  let result = bedStore.beds
  if (statusFilter.value) {
    result = result.filter((b) => b.status === statusFilter.value)
  }
  if (buildingFilter.value) {
    result = result.filter((b) => b.building === buildingFilter.value)
  }
  return result
})

const buildings = computed(() => {
  const set = new Set(bedStore.beds.map((b) => b.building).filter(Boolean) as string[])
  return [...set].sort()
})

// 已有患者(用作分配 dialog 的 datalist 选项,避免新人不知道 patient_id 是啥)
const occupiedPatients = computed(() => {
  return bedStore.beds
    .map((b) => ({ id: b.patient_id, name: b.patient_name }))
    .filter((x): x is { id: string; name: string } => !!x.id)
})

const statusMap: Record<BedStatus, { label: string; tone: 'success' | 'danger' | 'warning' | 'info' }> = {
  available: { label: '空闲', tone: 'success' },
  occupied: { label: '已入住', tone: 'danger' },
  maintenance: { label: '维护', tone: 'warning' },
  reserved: { label: '预留', tone: 'info' },
}

onMounted(() => {
  bedStore.fetchBeds()
})

function openAssign(bed: Bed) {
  assignTargetBed.value = bed
  assignPatientId.value = ''
  assignDialogOpen.value = true
}

function resetBedForm() {
  bedForm.value = {
    bed_number: '',
    floor: '',
    building: '',
    room: '',
    bed_type: 'standard',
    status: 'available',
    notes: '',
  }
}

function openCreateBed() {
  bedDialogMode.value = 'create'
  editTargetBed.value = null
  resetBedForm()
  bedDialogOpen.value = true
}

function openEditBed(bed: Bed) {
  bedDialogMode.value = 'edit'
  editTargetBed.value = bed
  bedForm.value = {
    bed_number: bed.bed_number,
    floor: bed.floor ?? '',
    building: bed.building ?? '',
    room: bed.room ?? '',
    bed_type: bed.bed_type ?? 'standard',
    status: bed.status,
    notes: bed.notes ?? '',
  }
  bedDialogOpen.value = true
}

function normalizeBedPayload(payload: BedFormState): BedFormPayload {
  return {
    bed_number: payload.bed_number.trim(),
    floor: payload.floor?.trim() || null,
    building: payload.building?.trim() || null,
    room: payload.room?.trim() || null,
    bed_type: payload.bed_type?.trim() || 'standard',
    status: payload.status,
    notes: payload.notes?.trim() || null,
  }
}

async function saveBed() {
  const payload = normalizeBedPayload(bedForm.value)
  if (!payload.bed_number) {
    push({ tone: 'warning', text: '请填写床位编号' })
    return
  }
  savingBed.value = true
  try {
    if (bedDialogMode.value === 'create') {
      await bedStore.createBed(payload)
      push({ tone: 'success', text: `已新增 ${payload.bed_number}` })
    } else if (editTargetBed.value) {
      await bedStore.updateBed(editTargetBed.value.bed_id, payload)
      push({ tone: 'success', text: `已保存 ${payload.bed_number}` })
    }
    bedDialogOpen.value = false
  } catch (e: any) {
    push({ tone: 'error', text: e.message ?? '保存床位失败' })
  } finally {
    savingBed.value = false
  }
}

async function doDelete(bed: Bed) {
  if (bed.status === 'occupied') {
    push({ tone: 'warning', text: '正在入住的床位不能删除，请先释放床位' })
    return
  }
  if (typeof window !== 'undefined' && !window.confirm(`确定删除床位 ${bed.bed_number} 吗？`)) {
    return
  }
  try {
    await bedStore.deleteBed(bed.bed_id)
    push({ tone: 'success', text: `${bed.bed_number} 已删除` })
  } catch (e: any) {
    push({ tone: 'error', text: e.message ?? '删除失败' })
  }
}

async function confirmAssign() {
  if (!assignTargetBed.value || !assignPatientId.value.trim()) return
  try {
    await bedStore.assignBed(assignTargetBed.value.bed_id, assignPatientId.value.trim())
    push({ tone: 'success', text: `已分配 ${assignTargetBed.value.bed_number}` })
    assignDialogOpen.value = false
  } catch (e: any) {
    push({ tone: 'error', text: e.message ?? '分配失败' })
  }
}

async function doRelease(bed: Bed) {
  try {
    await bedStore.releaseBed(bed.bed_id)
    push({ tone: 'success', text: `${bed.bed_number} 已释放` })
  } catch (e: any) {
    push({ tone: 'error', text: e.message ?? '释放失败' })
  }
}

async function handleRefresh(done: () => void) {
  try {
    await bedStore.fetchBeds()
  } finally {
    done()
  }
}
</script>

<template>
  <PullToRefresh @refresh="handleRefresh">
    <div class="bed-list-view">
      <!-- Header -->
    <div class="bed-list-header">
      <h1 class="title-l">床位管理</h1>
      <div class="row-s" style="margin-left: auto;">
        <Chip tone="success">空闲 {{ bedStore.available.length }}</Chip>
        <Chip tone="danger">占用 {{ bedStore.occupied.length }}</Chip>
        <Chip>总计 {{ bedStore.total }}</Chip>
        <Btn size="sm" variant="primary" @click="openCreateBed">新增床位</Btn>
      </div>
    </div>

    <!-- Filters -->
    <GlassPanel class="bed-filters">
      <div class="row" style="flex-wrap: wrap; gap: var(--sp-2);">
        <Field
          v-model="statusFilter"
          label="状态"
          type="select"
          style="max-width: 160px;"
        >
          <option value="">全部</option>
          <option value="available">空闲</option>
          <option value="occupied">已入住</option>
          <option value="maintenance">维护</option>
          <option value="reserved">预留</option>
        </Field>
        <Field
          v-model="buildingFilter"
          label="楼栋"
          type="select"
          style="max-width: 160px;"
        >
          <option value="">全部</option>
          <option v-for="b in buildings" :key="b" :value="b">{{ b }}</option>
        </Field>
      </div>
    </GlassPanel>

    <!-- Loading / Error -->
    <div v-if="bedStore.loading" class="bed-grid bed-grid--skeleton">
      <Skeleton v-for="i in 6" :key="i" shape="card" height="180px" />
    </div>
    <div v-else-if="bedStore.error" class="empty">
      <p class="empty-title">加载失败</p>
      <p class="empty-sub">{{ bedStore.error }}</p>
      <Btn variant="outline" size="sm" style="margin-top: var(--sp-3);" @click="bedStore.fetchBeds()">
        重试
      </Btn>
    </div>

    <!-- Grid -->
    <div v-else class="bed-grid">
      <GlassPanel
        v-for="bed in filteredBeds"
        :key="bed.bed_id"
        variant="card"
        class="bed-card"
      >
        <template #header>
          <span class="title-s">{{ bed.bed_number }}</span>
          <Chip :tone="statusMap[bed.status].tone" style="margin-left: auto;">
            {{ statusMap[bed.status].label }}
          </Chip>
        </template>

        <dl class="bed-meta">
          <div v-if="bed.building"><dt>楼栋</dt><dd>{{ bed.building }}</dd></div>
          <div v-if="bed.floor"><dt>楼层</dt><dd>{{ bed.floor }}</dd></div>
          <div v-if="bed.room"><dt>房间</dt><dd>{{ bed.room }}</dd></div>
          <div v-if="bed.bed_type"><dt>类型</dt><dd>{{ bed.bed_type }}</dd></div>
          <div v-if="bed.patient_name"><dt>入住人</dt><dd>{{ bed.patient_name }}</dd></div>
          <div v-if="bed.assigned_at"><dt>入住时间</dt><dd>{{ bed.assigned_at }}</dd></div>
          <div v-if="bed.notes"><dt>备注</dt><dd>{{ bed.notes }}</dd></div>
        </dl>

        <template #footer>
          <Btn
            variant="ghost"
            size="sm"
            @click="openEditBed(bed)"
          >
            编辑
          </Btn>
          <Btn
            v-if="bed.status === 'available'"
            variant="primary"
            size="sm"
            @click="openAssign(bed)"
          >
            分配
          </Btn>
          <Btn
            v-if="bed.status === 'occupied'"
            variant="outline"
            size="sm"
            @click="doRelease(bed)"
          >
            释放
          </Btn>
          <Btn
            v-if="bed.status !== 'occupied'"
            variant="ghost"
            size="sm"
            @click="doDelete(bed)"
          >
            删除
          </Btn>
        </template>
      </GlassPanel>

      <div v-if="filteredBeds.length === 0" class="empty" style="grid-column: 1/-1;">
        <p class="empty-title">暂无床位</p>
        <p class="empty-sub">当前筛选条件下没有匹配的床位</p>
      </div>
    </div>

    <!-- Assign Dialog -->
    <Dialog v-model="assignDialogOpen" :title="`分配床位 ${assignTargetBed?.bed_number ?? ''}`">
      <Field
        v-model="assignPatientId"
        label="老人 ID"
        required
        placeholder="例如 P001 (在'患者档案'页可查到)"
        hint="可输入档案 ID,或在下方建议项中选择已有老人"
        list="bed-patient-options"
      />
      <datalist id="bed-patient-options">
        <option v-for="p in occupiedPatients" :key="p.id" :value="p.id">
          {{ p.name }}
        </option>
      </datalist>
      <template #actions>
        <Btn variant="ghost" @click="assignDialogOpen = false">取消</Btn>
        <Btn variant="primary" :disabled="!assignPatientId.trim()" @click="confirmAssign">确认分配</Btn>
      </template>
    </Dialog>

    <!-- Create/Edit Dialog -->
    <Dialog
      v-model="bedDialogOpen"
      :title="bedDialogMode === 'create' ? '新增床位' : `编辑床位 ${editTargetBed?.bed_number ?? ''}`"
      full-sheet
    >
      <div class="bed-form">
        <Field v-model="bedForm.bed_number" label="床位编号" required placeholder="例如 A-101" />
        <Field v-model="bedForm.building" label="楼栋" placeholder="例如 A栋" />
        <Field v-model="bedForm.floor" label="楼层" placeholder="例如 1F" />
        <Field v-model="bedForm.room" label="房间" placeholder="例如 101" />
        <Field v-model="bedForm.bed_type" label="床位类型" type="select">
          <option value="standard">standard</option>
          <option value="electric">electric</option>
          <option value="icu">icu</option>
        </Field>
        <Field v-model="bedForm.status" label="状态" type="select">
          <option value="available">空闲</option>
          <option value="reserved">预留</option>
          <option value="maintenance">维护</option>
          <option value="occupied" :disabled="bedDialogMode === 'create'">已入住</option>
        </Field>
        <Field v-model="bedForm.notes" label="备注" type="textarea" placeholder="维护原因、特殊设备等" />
      </div>
      <template #actions>
        <Btn variant="ghost" :disabled="savingBed" @click="bedDialogOpen = false">取消</Btn>
        <Btn variant="primary" :loading="savingBed" :disabled="!bedForm.bed_number.trim()" @click="saveBed">
          保存
        </Btn>
      </template>
    </Dialog>
    </div>
  </PullToRefresh>
</template>

<style scoped>
.bed-list-view {
  display: grid;
  gap: var(--sp-4, 16px);
}
.bed-list-header {
  display: flex;
  align-items: center;
  gap: var(--sp-3, 12px);
  flex-wrap: wrap;
}
.bed-filters :deep(.vp-glass__body) {
  padding: var(--sp-2, 8px) 0 0;
}
.bed-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: var(--sp-3, 12px);
}
.bed-card :deep(.vp-glass__body) {
  padding: var(--sp-2, 8px) 0;
}
.bed-meta {
  display: grid;
  gap: 4px;
  font: 400 var(--fz-sm, 13px) / 1.5 var(--font-ui, sans-serif);
}
.bed-meta div {
  display: grid;
  grid-template-columns: 70px 1fr;
  gap: 8px;
}
.bed-meta dt {
  color: var(--ink-3, rgba(15, 23, 42, 0.55));
}
.bed-meta dd {
  margin: 0;
  color: var(--ink-1, #0f172a);
}
.bed-form {
  display: grid;
  gap: var(--sp-3, 12px);
  min-width: min(460px, 86vw);
}

@media (max-width: 640px) {
  .bed-list-header {
    align-items: flex-start;
    flex-direction: column;
    gap: 10px;
  }
  .bed-list-header > .row-s {
    margin-left: 0 !important;
    flex-wrap: wrap;
  }
  .bed-grid {
    grid-template-columns: 1fr;
    gap: 10px;
  }
  .bed-grid--skeleton {
    grid-template-columns: 1fr;
  }
  .bed-card {
    padding: 14px !important;
  }
  .bed-meta {
    font-size: 13px;
  }
  .bed-meta div {
    grid-template-columns: 70px 1fr;
  }
  .bed-filters .row {
    flex-direction: column;
    align-items: stretch;
  }
  .bed-filters .row > * {
    max-width: none !important;
  }
}

@media (max-width: 480px) {
  .bed-list-header .title-l { font-size: 18px; }
  .bed-list-header .chip { font-size: 10px; height: 20px; }
}
</style>
