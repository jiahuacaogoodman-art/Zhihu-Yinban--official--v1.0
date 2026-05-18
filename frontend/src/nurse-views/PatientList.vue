<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Field, Chip, GlassPanel, PullToRefresh, Skeleton } from '../components'
import { api } from '../api'
import { useToast } from '../composables/useToast'

/**
 * PatientList — 护工端老人列表
 *
 * 对应旧版 nurse.html 左侧 panel-list。
 * 移动端优先:卡片化列表,搜索置顶,点击跳详情页。
 */

interface Patient {
  patient_id: string
  name: string
  age?: number
  gender?: string
  bed_number?: string
  care_level?: string
}

const router = useRouter()
const { push: toast } = useToast()

const patients = ref<Patient[]>([])
const loading = ref(false)
const searchQuery = ref('')

const filtered = computed(() => {
  if (!searchQuery.value.trim()) return patients.value
  const q = searchQuery.value.toLowerCase()
  return patients.value.filter(
    (p) =>
      p.name?.toLowerCase().includes(q) ||
      p.patient_id?.toLowerCase().includes(q) ||
      p.bed_number?.toLowerCase().includes(q),
  )
})

async function fetchPatients() {
  loading.value = true
  try {
    const res = await api.get<Patient[] | { records: Patient[] }>('/ehr/patients')
    patients.value = Array.isArray(res) ? res : (res as any).records ?? []
  } catch (e: any) {
    toast({ tone: 'error', text: e.message ?? '加载老人列表失败' })
  } finally {
    loading.value = false
  }
}

function selectPatient(pid: string) {
  router.push(`/patient/${encodeURIComponent(pid)}`)
}

onMounted(fetchPatients)

async function handleRefresh(done: () => void) {
  try {
    await fetchPatients()
  } finally {
    done()
  }
}
</script>

<template>
  <PullToRefresh @refresh="handleRefresh">
  <div class="pt-list-view">
    <Field
      v-model="searchQuery"
      placeholder="搜索姓名 / 编号 / 床位"
      class="pt-search"
    />

    <div v-if="loading" class="pt-cards">
      <Skeleton v-for="i in 5" :key="i" shape="row" height="64px" />
    </div>

    <div v-else class="pt-cards">
      <div
        v-for="p in filtered"
        :key="p.patient_id"
        class="pt-card"
        @click="selectPatient(p.patient_id)"
      >
        <div class="pt-avatar">{{ (p.name || '?').slice(0, 1) }}</div>
        <div class="pt-info">
          <div class="pt-name">{{ p.name }}</div>
          <div class="pt-sub">
            {{ p.patient_id }} · {{ p.age ?? '?' }}岁 · {{ p.bed_number ?? '—' }}床
          </div>
        </div>
        <Chip v-if="p.care_level" tone="accent" class="pt-level">
          {{ p.care_level }}
        </Chip>
      </div>

      <div v-if="filtered.length === 0" class="empty">
        <p class="empty-title">暂无匹配老人</p>
      </div>
    </div>
  </div>
  </PullToRefresh>
</template>

<style scoped>
.pt-list-view {
  display: grid;
  gap: var(--sp-3, 12px);
}
.pt-search {
  position: sticky;
  top: 0;
  z-index: 5;
}
.pt-cards {
  display: grid;
  gap: 6px;
}
.pt-card {
  display: grid;
  grid-template-columns: 40px 1fr auto;
  align-items: center;
  gap: var(--sp-2, 8px);
  padding: var(--sp-3, 12px);
  border-radius: var(--r-s, 10px);
  background: rgba(255, 255, 255, 0.75);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(15, 23, 42, 0.06);
  cursor: pointer;
  transition: border-color 120ms ease, background 120ms ease;
}
.pt-card:hover {
  border-color: rgba(20, 184, 166, 0.3);
  background: #fff;
}
.pt-card:active {
  background: rgba(20, 184, 166, 0.06);
}
.pt-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: rgba(20, 184, 166, 0.12);
  color: var(--accent-ink, #0f766e);
  display: flex;
  align-items: center;
  justify-content: center;
  font: 600 16px / 1 var(--font-display, serif);
}
.pt-name {
  font: 600 var(--fz-sm, 13px) / 1.3 var(--font-ui, sans-serif);
  color: var(--ink-1);
}
.pt-sub {
  font: 400 var(--fz-xs, 11px) / 1.4 var(--font-ui, sans-serif);
  color: var(--ink-3);
  margin-top: 2px;
}

@media (max-width: 640px) {
  .pt-card {
    padding: 14px;
    min-height: 64px;
  }
  .pt-avatar {
    width: 44px;
    height: 44px;
    font-size: 18px;
  }
  .pt-name { font-size: 15px; }
  .pt-sub { font-size: 12.5px; }
}
</style>
