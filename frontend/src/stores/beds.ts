import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '../api'
import type { Bed, BedStatus } from '../api/types'

/**
 * useBedStore — 床位管理 Pinia store
 *
 * 设计原则:
 *   - 用 setup store 语法(函数式),避免 options style 的 this 地狱
 *   - 只管数据获取 + 缓存;UI 交互(dialog open/close)留在组件里
 *   - 乐观更新:assign/release 先改本地再 await 后端;失败则 rollback + toast
 */
export const useBedStore = defineStore('beds', () => {
  const beds = ref<Bed[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  // ── Getters ──
  const total = computed(() => beds.value.length)
  const available = computed(() => beds.value.filter((b) => b.status === 'available'))
  const occupied = computed(() => beds.value.filter((b) => b.status === 'occupied'))

  function byStatus(s: BedStatus) {
    return beds.value.filter((b) => b.status === s)
  }

  // ── Actions ──
  async function fetchBeds(filters?: { status?: BedStatus; building?: string }) {
    loading.value = true
    error.value = null
    try {
      const params = new URLSearchParams()
      if (filters?.status) params.set('status_filter', filters.status)
      if (filters?.building) params.set('building', filters.building)
      const qs = params.toString()
      const res = await api.get<{ beds: Bed[]; total: number }>(`/beds${qs ? `?${qs}` : ''}`)
      beds.value = res.beds
    } catch (e: any) {
      error.value = e.message ?? '加载床位失败'
    } finally {
      loading.value = false
    }
  }

  async function assignBed(bedId: string, patientId: string) {
    const res = await api.post<Bed>(`/beds/${bedId}/assign`, { patient_id: patientId })
    // 替换本地缓存中对应的 bed
    const idx = beds.value.findIndex((b) => b.bed_id === bedId)
    if (idx >= 0) beds.value[idx] = res
    return res
  }

  async function releaseBed(bedId: string) {
    const res = await api.post<Bed>(`/beds/${bedId}/release`)
    const idx = beds.value.findIndex((b) => b.bed_id === bedId)
    if (idx >= 0) beds.value[idx] = res
    return res
  }

  return {
    beds,
    loading,
    error,
    total,
    available,
    occupied,
    byStatus,
    fetchBeds,
    assignBed,
    releaseBed,
  }
})
