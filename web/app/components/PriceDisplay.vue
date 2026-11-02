<script setup lang="ts">
// The single place that formats centavos on screen, through `formatMXN` (CR-30, ADR-0024).
withDefaults(
  defineProps<{
    /** Integer centavos of MXN. Nothing renders when it is null. */
    cents: number | null
    /** The price before a discount, in centavos. */
    compareAtCents?: number | null
    /** Screen-reader text for the old price. */
    compareAtLabel?: string
  }>(),
  { compareAtCents: null, compareAtLabel: 'Precio anterior' },
)
</script>

<template>
  <span v-if="cents !== null">
    <span>{{ formatMXN(cents) }}</span>
    <template v-if="compareAtCents && compareAtCents > cents">
      {{ ' ' }}
      <del>
        <span class="sr-only">{{ compareAtLabel }}: </span>
        {{ formatMXN(compareAtCents) }}
      </del>
    </template>
  </span>
</template>
