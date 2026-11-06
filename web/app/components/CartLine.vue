<script setup lang="ts">
import type { Cart } from '~/composables/useCart'

type CartLine = Cart['lines'][number]

// One row of the cart. It shows what the server sent and asks for changes; it never computes a
// total (CR-02). The cart line carries no product name, so the page passes `name` when it has one.
const props = withDefaults(
  defineProps<{
    line: CartLine
    name?: string
    /** Disables the controls while a cart request is in flight. */
    disabled?: boolean
  }>(),
  { name: undefined, disabled: false },
)
const emit = defineEmits<{
  'update:quantity': [lineId: number, quantity: number]
  remove: [lineId: number]
}>()

const title = computed(() => props.name ?? 'Producto')
const max = computed(() => props.line.max_available ?? undefined)

function setQuantity(value: number | null | undefined) {
  if (value == null || value === props.line.quantity) return
  emit('update:quantity', props.line.id, value)
}
</script>

<template>
  <UCard :data-line-id="line.id" :data-availability="line.availability">
    <div class="flex flex-wrap items-center justify-between gap-4">
      <div class="flex flex-col gap-1">
        <p>{{ title }}</p>
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
