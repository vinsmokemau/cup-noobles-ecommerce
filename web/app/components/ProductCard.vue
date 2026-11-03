<script setup lang="ts">
import type { ProductCardData } from '~/types/catalog'

// A catalog card: the DS media card with the price and availability in its `meta` slot (DSR-01).
const props = defineProps<{
  product: ProductCardData
  /** Heading level of the title. */
  as?: 'h2' | 'h3' | 'h4'
  /** The card is above the fold: its picture loads at once instead of lazily. */
  priority?: boolean
}>()

const src = computed(() => pickImageSrc(props.product.image, 480))
const tags = computed(() => (props.product.franchise ? [props.product.franchise.name] : undefined))
</script>

<template>
  <CnMediaCard
    v-if="src"
    :title="product.name"
    :to="`/producto/${product.slug}`"
    :as="as"
    :src="src"
    :priority="priority"
    :alt="product.image?.alt || product.name"
    :tags="tags"
  >
    <template #meta>
      <PriceDisplay :cents="product.price_cents" :compare-at-cents="product.compare_at_cents" />
      <AvailabilityBadge :status="product.availability.status" />
    </template>
  </CnMediaCard>
  <CnMediaCard
    v-else
    :title="product.name"
    :to="`/producto/${product.slug}`"
    :as="as"
    decorative
    :tags="tags"
  >
    <template #meta>
      <PriceDisplay :cents="product.price_cents" :compare-at-cents="product.compare_at_cents" />
      <AvailabilityBadge :status="product.availability.status" />
    </template>
  </CnMediaCard>
</template>
