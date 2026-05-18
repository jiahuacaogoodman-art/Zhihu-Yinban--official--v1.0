<script setup lang="ts">
import { ref } from 'vue'
import { Btn, Field, GlassPanel } from '../components'
import { useToast } from '../composables/useToast'
import { api } from '../api'

/**
 * PatientAdd — 录入老人档案
 *
 * 对应旧版 index.html 的 tab-add：完整 21 字段表单 → POST /api/ehr/patients
 */

const { push: toast } = useToast()
const loading = ref(false)

const form = ref({
  patient_id: '',
  name: '',
  age: '',
  gender: '',
  birth_date: '',
  id_card: '',
  blood_type: '',
  height_cm: '',
  weight_kg: '',
  care_level: '',
  bed_number: '',
  primary_nurse: '',
  admission_date: '',
  emergency_contact: '',
  emergency_phone: '',
  emergency_relation: '',
  medical_history: '',
  allergy: '',
  diet_restriction: '',
  notes: '',
})

async function submitPatient() {
  if (!form.value.patient_id.trim() || !form.value.name.trim()) {
    toast({ tone: 'warning', text: '编号和姓名为必填项' })
    return
  }
  loading.value = true
  try {
    const payload: Record<string, any> = { ...form.value }
    // 数字字段转换
    payload.age = payload.age ? parseInt(payload.age) || null : null
    payload.height_cm = payload.height_cm ? parseFloat(payload.height_cm) || null : null
    payload.weight_kg = payload.weight_kg ? parseFloat(payload.weight_kg) || null : null
    // 空字符串转 null
    Object.keys(payload).forEach((k) => {
      if (payload[k] === '') payload[k] = null
    })
    // 必填字段还原
    payload.patient_id = form.value.patient_id.trim()
    payload.name = form.value.name.trim()

    await api.post('/ehr/patients', payload)
    toast({ tone: 'success', text: '档案保存成功' })
    // 重置表单
    Object.keys(form.value).forEach((k) => {
      ;(form.value as any)[k] = ''
    })
  } catch (e: any) {
    toast({ tone: 'error', text: e.message ?? '保存失败' })
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="pa-view">
    <GlassPanel variant="card">
      <template #header>
        <span class="title-l">录入老人档案</span>
        <p class="meta">填写完整信息，用于后续护理和 AI 建议参考</p>
      </template>

      <h3 class="section-label">基本信息</h3>
      <div class="form-grid cols-3">
        <Field v-model="form.patient_id" label="编号" required placeholder="P001" />
        <Field v-model="form.name" label="姓名" required placeholder="张三" />
        <Field v-model="form.age" label="年龄" type="number" placeholder="78" />
        <div class="field-group">
          <span class="field-label">性别</span>
          <select v-model="form.gender" class="field">
            <option value="">请选择</option>
            <option>男</option>
            <option>女</option>
            <option>其他</option>
          </select>
        </div>
        <Field v-model="form.birth_date" label="出生日期" type="date" />
        <Field v-model="form.id_card" label="身份证号" placeholder="可选" />
      </div>

      <h3 class="section-label">体征信息</h3>
      <div class="form-grid cols-3">
        <div class="field-group">
          <span class="field-label">血型</span>
          <select v-model="form.blood_type" class="field">
            <option value="">—</option>
            <option>A</option>
            <option>B</option>
            <option>AB</option>
            <option>O</option>
          </select>
        </div>
        <Field v-model="form.height_cm" label="身高（cm）" type="number" placeholder="168" />
        <Field v-model="form.weight_kg" label="体重（kg）" type="number" placeholder="65" />
      </div>

      <h3 class="section-label">护理信息</h3>
      <div class="form-grid cols-4">
        <div class="field-group">
          <span class="field-label">护理级别</span>
          <select v-model="form.care_level" class="field">
            <option value="">—</option>
            <option>特级</option>
            <option>一级</option>
            <option>二级</option>
            <option>三级</option>
          </select>
        </div>
        <Field v-model="form.bed_number" label="床位号" placeholder="301-A" />
        <Field v-model="form.primary_nurse" label="主管护士" placeholder="王护士" />
        <Field v-model="form.admission_date" label="入院日期" type="date" />
      </div>

      <h3 class="section-label">紧急联系</h3>
      <div class="form-grid cols-3">
        <Field v-model="form.emergency_contact" label="联系人" placeholder="张小明" />
        <Field v-model="form.emergency_phone" label="联系电话" placeholder="138xxxx" />
        <Field v-model="form.emergency_relation" label="关系" placeholder="子女" />
      </div>

      <h3 class="section-label">病史与备注</h3>
      <div class="form-grid cols-2">
        <Field v-model="form.allergy" label="过敏史" placeholder="青霉素" />
        <Field v-model="form.diet_restriction" label="饮食禁忌" placeholder="低盐低糖" />
        <Field
          v-model="form.medical_history"
          label="既往病史"
          type="textarea"
          :rows="3"
          placeholder="高血压、糖尿病、冠心病 …"
          class="full"
        />
        <Field
          v-model="form.notes"
          label="备注"
          type="textarea"
          :rows="2"
          placeholder="其他需要注意的事项"
          class="full"
        />
      </div>

      <div class="form-footer">
        <Btn variant="primary" :loading="loading" @click="submitPatient">
          保存档案
        </Btn>
      </div>
    </GlassPanel>
  </div>
</template>

<style scoped>
.pa-view {
  max-width: 900px;
}
.section-label {
  font: 600 var(--fz-sm, 13px) / 1.4 var(--font-ui);
  color: var(--ink-2);
  margin: var(--sp-4, 16px) 0 var(--sp-2, 8px);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.form-grid {
  display: grid;
  gap: var(--sp-2, 8px);
}
.form-grid.cols-2 { grid-template-columns: repeat(2, 1fr); }
.form-grid.cols-3 { grid-template-columns: repeat(3, 1fr); }
.form-grid.cols-4 { grid-template-columns: repeat(4, 1fr); }
.form-grid .full { grid-column: 1 / -1; }
.field-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.field-label {
  font: 600 var(--fz-xs, 11px) / 1.4 var(--font-ui);
  color: var(--ink-3);
}
.form-footer {
  margin-top: var(--sp-5, 20px);
  display: flex;
  justify-content: flex-end;
}
@media (max-width: 640px) {
  .form-grid.cols-3,
  .form-grid.cols-4 {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 480px) {
  .form-grid.cols-2,
  .form-grid.cols-3,
  .form-grid.cols-4 {
    grid-template-columns: 1fr;
  }
}
</style>
