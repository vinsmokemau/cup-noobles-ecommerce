<script setup lang="ts">
import type { AvailabilityStatus } from '~/types/catalog'

// The status is in the text, never only in the color (P12-V12, REQ-051). The badge variants are the DS's:
// solid for what can be bought now, outline for what cannot, tag for a pre-order.
const props = withDefaults(
  defineProps<{
    status: AvailabilityStatus
    /** Release date of a pre-order, `YYYY-MM-DD`. */
    releaseDate?: string | null
    labels?: Partial<Record<AvailabilityStatus, string>> & { preorderArrives?: string }
  }>(),
  { releaseDate: null, labels: () => ({}) },
)

const DEFAULTS: Record<AvailabilityStatus, string> = {
  in_stock: 'Disponible',
  low_stock: 'Últimas piezas',
  out_of_stock: 'Agotado',
  preorder: 'Preventa',
}

const label = computed(() => {
  const text = props.labels[props.status] ?? DEFAULTS[props.status]
  if (props.status !== 'preorder' || !props.releaseDate) return text
  const arrives = props.labels.preorderArrives ?? 'llega el'
  return `${text} · ${arrives} ${formatDate(props.releaseDate)}`
})

const look = computed(() => {
  if (props.status === 'in_stock') return { color: 'primary', variant: 'solid' } as const
  if (props.status === 'preorder') return { color: 'secondary', variant: 'solid' } as const
  return { color: 'primary', variant: 'outline' } as const
})
</script>

<template>
  <UBadge :label="label" :color="look.color" :variant="look.variant" :data-status="status" />
</template>
