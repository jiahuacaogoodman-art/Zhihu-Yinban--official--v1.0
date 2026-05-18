<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Chip, GlassPanel } from '../components'
import { useToast } from '../composables/useToast'
import { api } from '../api'

/**
 * Incidents — 异常事件列表(Phase 4)
 *
 * 消费 GET /api/incidents 接口。
 */

interface Incident {
  incident_id: string
  patient_name: string | null
  incident_type: string
  severity: string
  status: string
  description: string
  reporter: string | null
  created_at: string
}

const { push: toast } = useToast()
const incidents = ref<Incident[]>([])
const loading = ref(false)

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

const severityMap: Record<string, { label: string; tone: 'danger' | 'warning' | 'info' | 'neutral' }> = {
  critical: { label: '严重', tone: 'danger' },
  major: { label: '较重', tone: 'warning' },
  minor: { label: '轻微', tone: 'info' },
  observation: { label: '观察', tone: 'neutral' },
}

onMounted(fetchIncidents)
</script>

<template>
  <div class="incident-view">
    <div class="incident-header">
      <h1 class="title-l">异常事件</h1>
      <Chip>共 {{ incidents.length }} 条</Chip>
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
          <span class="title-s">{{ i.incident_type }}</span>
          <Chip
            :tone="(severityMap[i.severity] ?? severityMap.minor).tone"
            style="margin-left: auto;"
          >
            {{ (severityMap[i.severity] ?? severityMap.minor).label }}
          </Chip>
        </template>
        <p class="body-s">{{ i.description }}</p>
        <template #footer>
          <span class="meta">{{ i.created_at }}</span>
          <Chip v-if="i.patient_name" tone="accent">{{ i.patient_name }}</Chip>
          <span v-if="i.reporter" class="meta">上报: {{ i.reporter }}</span>
        </template>
      </GlassPanel>

      <div v-if="incidents.length === 0" class="empty">
        <p class="empty-title">暂无异常事件</p>
        <p class="empty-sub">没有事件是好事 ✨。事件上报功能开发中。</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.incident-view { display: grid; gap: var(--sp-4, 16px); }
.incident-header { display: flex; align-items: center; gap: var(--sp-3); }

@media (max-width: 640px) {
  .incident-view { gap: 12px; }
  .incident-header { flex-wrap: wrap; }
  .incident-header .title-l { font-size: 20px; width: 100%; }
  .incident-card :deep(.vp-glass__body) .body-s {
    font-size: 13px;
    line-height: 1.65;
    display: -webkit-box;
    -webkit-line-clamp: 4;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .incident-card :deep(.vp-glass__footer) {
    flex-wrap: wrap;
    gap: 6px;
  }
}

@media (max-width: 480px) {
  .incident-header .title-l { font-size: 18px; }
}
</style>
