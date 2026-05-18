<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Chip, GlassPanel } from '../components'
import { useToast } from '../composables/useToast'
import { api } from '../api'

/**
 * Handovers — 交接班列表(Phase 4)
 *
 * 消费 GET /api/handovers 接口。
 * SBAR 格式展开:Situation / Background / Assessment / Recommendation。
 */

interface Handover {
  handover_id: string
  shift_from: string
  shift_to: string
  shift_type: string
  patient_name: string | null
  situation: string
  background: string
  assessment: string
  recommendation: string
  status: string
  created_at: string
}

const { push: toast } = useToast()
const handovers = ref<Handover[]>([])
const loading = ref(false)

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

const statusMap: Record<string, { label: string; tone: 'success' | 'warning' | 'info' }> = {
  pending: { label: '待确认', tone: 'warning' },
  acknowledged: { label: '已确认', tone: 'info' },
  completed: { label: '已完成', tone: 'success' },
}

onMounted(fetchHandovers)
</script>

<template>
  <div class="handover-view">
    <div class="handover-header">
      <h1 class="title-l">交接班记录</h1>
      <Chip>共 {{ handovers.length }} 条</Chip>
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
          <span class="title-s">{{ h.shift_from }} → {{ h.shift_to }}</span>
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
        <template #footer>
          <span class="meta">{{ h.created_at }}</span>
          <Chip v-if="h.patient_name" tone="accent">{{ h.patient_name }}</Chip>
        </template>
      </GlassPanel>

      <div v-if="handovers.length === 0" class="empty">
        <p class="empty-title">暂无交接记录</p>
        <p class="empty-sub">交接班录入功能开发中。</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.handover-view { display: grid; gap: var(--sp-4, 16px); }
.handover-header { display: flex; align-items: center; gap: var(--sp-3); }
.sbar { display: grid; gap: 6px; font: 400 var(--fz-sm, 13px)/1.6 var(--font-ui); }
.sbar strong { color: var(--accent-ink, #0f766e); margin-right: 6px; font-weight: 700; }

@media (max-width: 640px) {
  .handover-view { gap: 12px; }
  .handover-header { flex-wrap: wrap; }
  .handover-header .title-l { font-size: 20px; width: 100%; }
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
    gap: 4px;
  }
}

@media (max-width: 480px) {
  .handover-header .title-l { font-size: 18px; }
  .sbar { font-size: 12px; }
}
</style>
