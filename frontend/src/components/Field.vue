<script setup lang="ts">
import { computed, useId } from 'vue'

/**
 * Field — 表单字段(input / textarea / select 三合一)
 *
 * 直接套用 ui.css 的 .field / .field-group / .field-label / .field-hint。
 *
 * 设计取舍:
 *   - 三个原生 element 都套同一个 .field class,通过 type prop 切换
 *     (textarea / select 的特殊样式 ui.css 已经覆盖)
 *   - label / hint / error 全在 prop 里,业务侧不用自己拼 .field-group
 *   - error 时不改边框颜色 —— 留到首个真实表单视图再决定(避免现在乱定标准)
 *   - 用 useId() 把 label 和控件 for/id 关起来,a11y 必须的
 *
 * v-model 兼容字符串、数字、字符串数组(为了 multiple select)。Phase 3 真用到时
 * 再加复杂校验,本 phase 不做。
 *
 * select 的 options 通过 slot 接受 <option> 列表,而不是 prop 数组 —— 给业务
 * 留最大灵活度,避免造一套半成品的 OptionList API。
 */
type ModelValue = string | number | string[]

const props = defineProps<{
  modelValue?: ModelValue
  label?: string
  hint?: string
  error?: string
  required?: boolean
  type?: 'text' | 'password' | 'email' | 'number' | 'tel' | 'date' | 'textarea' | 'select'
  placeholder?: string
  disabled?: boolean
  name?: string
  rows?: number
  multiple?: boolean
}>()

defineEmits<{
  'update:modelValue': [value: ModelValue]
}>()

const id = useId()
const inputType = computed(() => props.type ?? 'text')
</script>

<template>
  <div class="field-group">
    <label v-if="label" :for="id" class="field-label">
      {{ label }}<span v-if="required" class="req">*</span>
    </label>

    <textarea
      v-if="inputType === 'textarea'"
      :id="id"
      class="field"
      :value="modelValue as string | number | undefined"
      :placeholder="placeholder"
      :disabled="disabled"
      :name="name"
      :rows="rows ?? 4"
      :required="required || undefined"
      @input="$emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
    />

    <select
      v-else-if="inputType === 'select'"
      :id="id"
      class="field"
      :value="modelValue as string | number | undefined"
      :disabled="disabled"
      :name="name"
      :multiple="multiple"
      :required="required || undefined"
      @change="$emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
    >
      <slot />
    </select>

    <input
      v-else
      :id="id"
      class="field"
      :type="inputType"
      :value="modelValue as string | number | undefined"
      :placeholder="placeholder"
      :disabled="disabled"
      :name="name"
      :required="required || undefined"
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    />

    <p v-if="error" class="field-hint" role="alert" style="color: var(--red, #dc2626)">
      {{ error }}
    </p>
    <p v-else-if="hint" class="field-hint">{{ hint }}</p>
  </div>
</template>
