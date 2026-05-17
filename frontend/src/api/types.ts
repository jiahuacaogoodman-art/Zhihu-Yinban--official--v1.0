/**
 * API 类型定义 —— 对齐后端 app/models/care_schemas.py
 *
 * 注意:这里只写 Phase 3 试点需要的 Bed 相关类型;其余视图迁移时再逐步加。
 * 命名规范:与后端 schema 同名(camelCase ↔ snake_case 由 JSON 自然映射,
 * 后端返回的就是 snake_case,前端类型也用 snake_case,不做转换——
 * 减少中间层,debug 时看 Network 和 store 里的 key 完全一致)。
 */

export type BedStatus = 'available' | 'occupied' | 'maintenance' | 'reserved'

export interface Bed {
  bed_id: string
  bed_number: string
  floor: string | null
  building: string | null
  room: string | null
  bed_type: string
  status: BedStatus
  patient_id: string | null
  patient_name: string | null
  assigned_at: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}
