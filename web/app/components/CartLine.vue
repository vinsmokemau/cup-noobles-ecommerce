<script setup lang="ts">
import type { Cart } from '~/composables/useCart'

type CartLine = Cart['lines'][number]

// One row of the cart. It shows what the server sent and asks for changes; it never computes a
// total (CR-02). The name and the variant's options come from the line itself (G56).
const props = withDefaults(
  defineProps<{
    line: CartLine
    /** Disables the controls while a cart request is in flight. */
    disabled?: boolean
  }>(),
  { disabled: false },
)
const emit = defineEmits<{
  'update:quantity': [lineId: number, quantity: number]
  remove: [lineId: number]
}>()

const title = computed(() => props.line.product_name)
// "Talla: L · Color: negro", in the order the catalog sent them; a product with no variation has none.
const optionsText = computed(() =>
  Object.entries(props.line.options ?? {})
    .map(([key, value]) => `${key}: ${value}`)
    .join(' · '),
)
const max = computed(() => props.line.max_available ?? undefined)

function setQuantity(value: number | null | undefined) {
  if (value == null || value === props.line.quantity) return
  emit('update:quantity', props.line.id, value)
}
</script>

<template>
  <UCard :data-line-id="line.id" :data-availability="line.availability">
    <div class="flex flex-wrap items-center justify-between gap-4">
      <div class="flex min-w-0 flex-col gap-1 break-words">
        <p>{{ title }}</p>
        <p v-if="optionsText" data-testid="line-options">{{ optionsText }}</p>
        <p>{{ formatMXN(line.unit_price_cents) }}</p>
        <slot />
      </div>
      <div class="flex items-center gap-4">
        <UInputNumber
          :model-value="line.quantity"
          :min="1"
          :max="max"
          size="xl"
          :disabled="disabled || line.availability === 'unavailable'"
          :aria-label="`Cantidad de ${title}`"
          @update:model-value="setQuantity"
        />
        <p>{{ formatMXN(line.line_total_cents) }}</p>
        <UButton
          label="Quitar"
          variant="outline"
          size="xl"
          :disabled="disabled"
          :aria-label="`Quitar ${title}`"
          @click="emit('remove', line.id)"
        />
      </div>
    </div>
  </UCard>
</template>
