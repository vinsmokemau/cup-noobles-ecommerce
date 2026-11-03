<script setup lang="ts">
import type { ProductCardData } from '~/types/catalog'

defineProps<{
  products: ProductCardData[]
  /** Heading level of the card titles. */
  as?: 'h2' | 'h3' | 'h4'
  /** How many cards, from the first, are above the fold and load their picture at once. */
  priorityCount?: number
}>()
</script>

<template>
  <ul class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
    <li v-for="(product, index) in products" :key="product.public_id" class="min-w-0">
      <ProductCard :product="product" :as="as" :priority="index < (priorityCount ?? 0)" />
    </li>
  </ul>
</template>
