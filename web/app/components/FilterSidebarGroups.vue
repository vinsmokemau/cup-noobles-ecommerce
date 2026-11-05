<script setup lang="ts">
import type { Facet } from '~/types/catalog'

// The facet groups of the filter sidebar: one checkbox group for each facet.
const props = defineProps<{
  facets: Facet[]
  modelValue: Record<string, string[]>
  labels: { yes: string; no: string }
}>()
const emit = defineEmits<{ 'update:modelValue': [value: Record<string, string[]>] }>()

function valueLabel(value: unknown) {
  if (typeof value === 'boolean') return value ? props.labels.yes : props.labels.no
  return String(value)
}
function update(key: string, selected: string[]) {
  emit('update:modelValue', { ...props.modelValue, [key]: selected })
}
</script>

<template>
  <div class="flex flex-col gap-6">
    <UCheckboxGroup
      v-for="facet in facets"
      :key="facet.key"
      :model-value="modelValue[facet.key] ?? []"
      :legend="facet.title"
      size="2xl"
      :items="
        facet.values.map((v) => ({
          value: String(v.value),
          label: `${valueLabel(v.value)} (${v.count})`,
        }))
      "
      @update:model-value="update(facet.key, $event as string[])"
    />
  </div>
</template>
