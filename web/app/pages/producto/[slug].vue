<script setup lang="ts">
import type { AttributeSchema, ProductDetailData } from '~/types/catalog'

const api = useApi()
const slug = String(useRoute().params.slug)

const {
  data: product,
  error,
  refresh,
} = await useAsyncData(`product:${slug}`, () =>
  api<ProductDetailData>(`/catalog/products/${encodeURIComponent(slug)}/`),
)
// A product that is not published (or never existed) is a real 404 (REQ-053).
if (apiErrorOf(error.value)?.status === 404) {
  throw createError({ statusCode: 404, statusMessage: 'Producto no encontrado', fatal: true })
}
failOnServer(error)

// Opens on the first variant that can be bought, else the first one.
const selectedId = ref<string | null>(null)
watch(
  product,
  (loaded) => {
    const variants = loaded?.variants ?? []
    const open = variants.find((v) => v.availability.status !== 'out_of_stock') ?? variants[0]
    selectedId.value = open?.public_id ?? null
  },
  { immediate: true },
)
const variant = computed(() =>
  product.value?.variants.find((v) => v.public_id === selectedId.value),
)

const paragraphs = computed(() =>
  (product.value?.description_md ?? '')
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter(Boolean),
)

const SCHEMA_AVAILABILITY = {
  in_stock: 'https://schema.org/InStock',
  low_stock: 'https://schema.org/LimitedAvailability',
  out_of_stock: 'https://schema.org/OutOfStock',
  preorder: 'https://schema.org/PreOrder',
} as const

// Structured data for search engines (P12-V01). The price is the machine form, not display text.
const jsonLd = computed(() => {
  const loaded = product.value
  if (!loaded) return undefined
  const offer = variant.value
  return JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'Product',
    name: loaded.name,
    sku: offer?.sku,
    ...(loaded.brand ? { brand: { '@type': 'Brand', name: loaded.brand.name } } : {}),
    offers: offer
      ? {
          '@type': 'Offer',
          price: (offer.price_cents / 100).toFixed(2),
          priceCurrency: 'MXN',
          availability: SCHEMA_AVAILABILITY[offer.availability.status],
        }
      : undefined,
  }).replace(/</g, '\\u003c')
})

usePageSeo({
  title: () => product.value?.name,
  description: () => metaDescription(product.value?.description_md),
  image: () => pickImageSrc(product.value?.images[0] ?? product.value?.image, 1200),
})
useHead({
  script: computed(() =>
    jsonLd.value ? [{ type: 'application/ld+json', innerHTML: jsonLd.value }] : [],
  ),
})
</script>

<template>
  <main class="mx-auto flex w-full max-w-6xl flex-col gap-8 p-4">
    <LoadError v-if="error" @retry="refresh()" />
    <template v-else-if="product">
      <div class="grid grid-cols-1 gap-8 lg:grid-cols-2">
        <ProductGallery
          v-if="product.images.length"
          class="min-w-0"
          :images="product.images"
          :name="product.name"
          :variant-id="selectedId"
        />
        <div class="flex min-w-0 flex-col gap-4">
          <h1>{{ product.name }}</h1>
          <p v-if="product.subtitle">{{ product.subtitle }}</p>
          <p v-if="variant" class="flex flex-wrap items-center gap-2" aria-live="polite">
            <PriceDisplay
              :cents="variant.price_cents"
              :compare-at-cents="variant.compare_at_cents"
            />
            <AvailabilityBadge :status="variant.availability.status" />
          </p>
          <VariantSelector
            v-model="selectedId"
            :variants="product.variants"
            :axes="product.variant_axes"
          />
        </div>
      </div>
      <section
        v-if="paragraphs.length"
        aria-labelledby="product-description"
        class="flex flex-col gap-2"
      >
        <h2 id="product-description">Descripción</h2>
        <p v-for="(paragraph, index) in paragraphs" :key="index">{{ paragraph }}</p>
      </section>
      <section aria-labelledby="product-attributes" class="flex flex-col gap-2">
        <h2 id="product-attributes">Características</h2>
        <AttributeTable
          :schema="product.attribute_schema as AttributeSchema"
          :attributes="product.attributes as Record<string, unknown>"
        />
      </section>
      <section
        v-if="product.related.length"
        aria-labelledby="product-related"
        class="flex flex-col gap-4"
      >
        <h2 id="product-related">También te puede gustar</h2>
        <ProductGrid :products="product.related" as="h3" />
      </section>
    </template>
  </main>
</template>
