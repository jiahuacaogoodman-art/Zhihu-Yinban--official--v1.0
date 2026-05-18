<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Chip, GlassPanel } from '../components'
import { useToast } from '../composables/useToast'
import { api } from '../api'

/**
 * CareRecords — 护理记录列表(Phase 4)
 *
 * 消费 GET /api/care-records 接口。
 */

interface CareRecord {
  record_id: string
  patient_name: string | null
  record_type: string
  content: string
  recorded_by: string | null
  recorded_at: string
  shift: string | null
}

const { push: toast } = useToast()
const records = ref<CareRecord[]>([])
const loading = ref(false)

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

onMounted(fetchRecords)
</script>

<template>
  <div class="care-record-view">
    <div class="care-record-header">
      <h1 class="title-l">护理记录</h1>
      <Chip>共 {{ records.length }} 条</Chip>
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
          <span v-if="r.patient_name" class="title-s" style="margin-left: var(--sp-2);">
            {{ r.patient_name }}
          </span>
        </template>
        <p class="body-s">{{ r.content }}</p>
        <template #footer>
          <span class="meta">{{ r.recorded_at }}</span>
          <span v-if="r.recorded_by" class="meta">记录人: {{ r.recorded_by }}</span>
          <Chip v-if="r.shift" tone="info">{{ r.shift }}</Chip>
        </template>
      </GlassPanel>

      <div v-if="records.length === 0" class="empty">
        <p class="empty-title">暂无护理记录</p>
        <p class="empty-sub">
          可在<a href="/nurse" style="color: var(--accent-ink, #0f766e);">护工端</a>录入。
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.care-record-view { display: grid; gap: var(--sp-4, 16px); }
.care-record-header { display: flex; align-items: center; gap: var(--sp-3); }

@media (max-width: 640px) {
  .care-record-view { gap: 12px; }
  .care-record-header { flex-wrap: wrap; }
  .care-record-header .title-l { font-size: 20px; width: 100%; }
  .care-record-view :deep(.vp-glass__body) .body-s {
    font-size: 13px;
    line-height: 1.7;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .care-record-view :deep(.vp-glass__header) {
    gap: 6px;
    flex-wrap: wrap;
  }
  .care-record-view :deep(.vp-glass__footer) {
    flex-wrap: wrap;
    gap: 4px;
  }
}

@media (max-width: 480px) {
  .care-record-header .title-l { font-size: 18px; }
}
</style>
