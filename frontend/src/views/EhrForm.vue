<script setup lang="ts">
import { Field } from '../components'

type FormMode = 'create' | 'edit'

type EhrFormState = {
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

defineProps<{
  model: EhrFormState
  mode: FormMode
}>()

defineEmits<{
  submit: []
}>()
</script>

<template>
  <form class="ehr-form" @submit.prevent="$emit('submit')">
    <section class="ehr-form-section ehr-form-section--required">
      <div class="ehr-form-section-head">
        <span class="ehr-form-section-kicker">必填</span>
        <h3 class="title-s">身份识别</h3>
      </div>
      <div class="ehr-form-grid ehr-form-grid--required">
        <Field
          v-model="model.patient_id"
          label="患者 ID"
          required
          :disabled="mode === 'edit'"
          placeholder="例如:P001"
          autocomplete="off"
        />
        <Field v-model="model.name" label="姓名" required autocomplete="off" />
      </div>
    </section>

    <section class="ehr-form-section">
      <div class="ehr-form-section-head">
        <span class="ehr-form-section-kicker">基础</span>
        <h3 class="title-s">基本信息</h3>
      </div>
      <div class="ehr-form-grid">
        <Field v-model="model.age" label="年龄" type="number" inputmode="numeric" />
        <Field v-model="model.gender" label="性别" type="select">
          <option value="">请选择</option>
          <option value="男">男</option>
          <option value="女">女</option>
        </Field>
        <Field v-model="model.birth_date" label="出生日期" type="date" />
        <Field v-model="model.id_card" label="身份证号" inputmode="numeric" />
        <Field v-model="model.blood_type" label="血型" type="select">
          <option value="">请选择</option>
          <option value="A">A</option>
          <option value="B">B</option>
          <option value="AB">AB</option>
          <option value="O">O</option>
          <option value="未知">未知</option>
        </Field>
        <Field v-model="model.height_cm" label="身高(cm)" type="number" inputmode="decimal" />
        <Field v-model="model.weight_kg" label="体重(kg)" type="number" inputmode="decimal" />
      </div>
    </section>

    <section class="ehr-form-section">
      <div class="ehr-form-section-head">
        <span class="ehr-form-section-kicker">入住</span>
        <h3 class="title-s">入住与护理</h3>
      </div>
      <div class="ehr-form-grid">
        <Field v-model="model.admission_date" label="入院日期" type="date" />
        <Field v-model="model.bed_number" label="床位号" placeholder="例如:A-101-1" />
        <Field v-model="model.care_level" label="护理等级" type="select">
          <option value="">请选择</option>
          <option value="一级">一级</option>
          <option value="二级">二级</option>
          <option value="三级">三级</option>
          <option value="特护">特护</option>
        </Field>
        <Field v-model="model.primary_nurse" label="主管护工" />
      </div>
    </section>

    <section class="ehr-form-section">
      <div class="ehr-form-section-head">
        <span class="ehr-form-section-kicker">联系</span>
        <h3 class="title-s">联系人与健康要点</h3>
      </div>
      <div class="ehr-form-grid">
        <Field v-model="model.emergency_contact" label="紧急联系人" />
        <Field v-model="model.emergency_phone" label="联系电话" type="tel" inputmode="tel" />
        <Field v-model="model.emergency_relation" label="关系" placeholder="子女 / 配偶 / 亲属" />
        <Field v-model="model.allergy" label="过敏史" placeholder="无 / 药物 / 食物" />
        <Field v-model="model.diet_restriction" label="饮食禁忌" placeholder="无 / 低盐 / 糖尿病饮食" />
      </div>
    </section>

    <section class="ehr-form-section">
      <div class="ehr-form-section-head">
        <span class="ehr-form-section-kicker">补充</span>
        <h3 class="title-s">病史与备注</h3>
      </div>
      <div class="ehr-form-grid ehr-form-grid--notes">
        <Field
          v-model="model.medical_history"
          label="既往病史 / 用药"
          type="textarea"
          :rows="4"
        />
        <Field v-model="model.notes" label="备注" type="textarea" :rows="3" />
      </div>
    </section>
  </form>
</template>

<style scoped>
.ehr-form {
  display: grid;
  gap: var(--sp-3, 12px);
  width: 100%;
}
.ehr-form-section {
  position: relative;
  display: grid;
  gap: var(--sp-3, 12px);
  padding: 16px;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.86);
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.82), rgba(255, 255, 255, 0.58)),
    radial-gradient(180px 110px at 12% 0%, rgba(94, 234, 212, 0.22), transparent 68%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.92),
    0 10px 30px rgba(15, 23, 42, 0.06);
}
.ehr-form-section--required {
  border-color: rgba(20, 184, 166, 0.32);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.92),
    0 14px 34px rgba(20, 184, 166, 0.12);
}
.ehr-form-section-head {
  display: flex;
  align-items: center;
  gap: 10px;
}
.ehr-form-section-head .title-s {
  margin: 0;
}
.ehr-form-section-kicker {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 42px;
  height: 24px;
  padding: 0 9px;
  border-radius: 999px;
  background: rgba(20, 184, 166, 0.12);
  color: var(--accent-ink, #0f766e);
  font: 700 11px/1 var(--font-ui);
  letter-spacing: 0.08em;
}
.ehr-form-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.ehr-form-grid--required {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.ehr-form-grid--notes {
  grid-template-columns: 1fr;
}
.ehr-form :deep(textarea.field) {
  min-height: 104px;
  resize: vertical;
}
.ehr-form :deep(.field-group) {
  min-width: 0;
}
.ehr-form :deep(.field) {
  background-color: rgba(255, 255, 255, 0.88);
}

@media (max-width: 900px) {
  .ehr-form-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .ehr-form-grid--notes {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .ehr-form-grid {
    grid-template-columns: 1fr;
  }
  .ehr-form-section {
    padding: 14px;
    border-radius: 18px;
  }
  .ehr-form-section-head {
    align-items: flex-start;
    flex-direction: column;
    gap: 6px;
  }
}
</style>