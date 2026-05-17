<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Btn, Chip, GlassPanel, Field } from '../components'
import { useToast } from '../composables/useToast'
import { api } from '../api'

/**
 * EhrList — 患者档案列表(Phase 4)
 *
 * 对应旧版 static/index.html 的 #ehr tab。
 * 消费 GET /api/ehr/list 接口。
 */

interface EHRRecord {
  doc_id: string
  patient_id: string
  name: string
  age?: number
  gender?: string
  bed_number?: string
  care_level?: string
  admission_date?: string
  doc_type: string
}

const { push: toast } = useToast()
const records = ref<EHRRecord[]>([])
const loading = ref(false)
const searchQuery = ref('')

async function fetchRecords() {
  loading.value = true
  try {
    const res = await api.get<{ records: EHRRecord[]; total: number }>('/ehr/list')
    records.value = res.records ?? []
  } catch (e: any) {
    toast({ tone: 'error', text: e.message ?? '加载档案失败' })
  } finally {
    loading.value = false
  }
}

const filteredRecords = computed(() => {
  if (!searchQuery.value.trim()) return records.value
  const q = searchQuery.value.toLowerCase()
  return records.value.filter(
    (r) =>
      r.name?.toLowerCase().includes(q) ||
      r.patient_id?.toLowerCase().includes(q) ||
      r.bed_number?.toLowerCase().includes(q),
  )
})

import { computed } from 'vue'

onMounted(fetchRecords)
</script>

<template>
  <div class="ehr-view">
    <div class="ehr-header">
      <h1 class="title-l">患者档案</h1>
      <Chip>共 {{ records.length }} 人</Chip>
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
      >
        <template #header>
          <span class="title-s">{{ r.name || '未知' }}</span>
          <Chip v-if="r.care_level" tone="accent" style="margin-left: auto;">
            {{ r.care_level }}
          </Chip>
        </template>
        <dl class="ehr-meta">
          <div><dt>ID</dt><dd>{{ r.patient_id }}</dd></div>
          <div v-if="r.age"><dt>年龄</dt><dd>{{ r.age }}</dd></div>
          <div v-if="r.gender"><dt>性别</dt><dd>{{ r.gender }}</dd></div>
          <div v-if="r.bed_number"><dt>床位</dt><dd>{{ r.bed_number }}</dd></div>
          <div v-if="r.admission_date"><dt>入院</dt><dd>{{ r.admission_date }}</dd></div>
        </dl>
      </GlassPanel>

      <div v-if="filteredRecords.length === 0" class="empty" style="grid-column: 1/-1;">
        <p class="empty-title">暂无匹配档案</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ehr-view { display: grid; gap: var(--sp-4, 16px); }
.ehr-header { display: flex; align-items: center; gap: var(--sp-3); }
.ehr-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: var(--sp-3); }
.ehr-meta { display: grid; gap: 4px; font: 400 var(--fz-sm, 13px)/1.5 var(--font-ui); }
.ehr-meta div { display: grid; grid-template-columns: 60px 1fr; gap: 8px; }
.ehr-meta dt { color: var(--ink-3); }
.ehr-meta dd { margin: 0; }
</style>
