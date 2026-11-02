<script setup lang="ts">
import type { AttributeSchema } from '~/types/catalog'

// Rows come from the product type's schema: its property titles are the labels and its order is the order.
// The component names no product type, so a new type needs no frontend work (SPEC.md §4.4).
const props = withDefaults(
  defineProps<{
    schema: AttributeSchema | null | undefined
    attributes: Record<string, unknown> | null | undefined
    labels?: { yes: string; no: string }
  }>(),
  { labels: () => ({ yes: 'Sí', no: 'No' }) },
)

function display(value: unknown): string {
  if (typeof value === 'boolean') return value ? props.labels.yes : props.labels.no
  if (Array.isArray(value)) return value.map(display).join(', ')
  return String(value)
}

const items = computed(() =>
  Object.entries(props.schema?.properties ?? {}).flatMap(([key, property]) => {
    const value = props.attributes?.[key]
    if (value === undefined || value === null || value === '') return []
    return [{ label: property.title || key, value: display(value) }]
  }),
)
</script>

<template>
  <CnKeyValueList :items="items" />
</template>
