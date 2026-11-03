<script setup lang="ts">
import type { ProductCardData } from '~/types/catalog'

defineProps<{
  products: ProductCardData[]
  /** Heading level of the card titles. */
  as?: 'h2' | 'h3' | 'h4'
}>()
</script>

<template>
  <ul class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
    <li v-for="product in products" :key="product.public_id" class="min-w-0">
      <ProductCard :product="product" :as="as" />
    </li>
  </ul>
</template>
