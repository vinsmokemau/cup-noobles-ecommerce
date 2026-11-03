<script setup lang="ts">
import type { CategoryNode, ProductPage } from '~/types/catalog'

const api = useApi()

const { data, error, refresh } = await useAsyncData('home', async () => {
  const [featured, categories] = await Promise.all([
    api<ProductPage>('/catalog/products/', { query: { featured: true, page_size: 8 } }),
    api<CategoryNode[]>('/catalog/categories/'),
  ])
  return { featured: featured.results, categories }
})

useSeoMeta({ title: 'Cup Noobles' })
</script>

<template>
  <main class="mx-auto flex w-full max-w-6xl flex-col gap-8 p-4">
    <h1>
      <CnLogo variant="horizontal" label="Cup Noobles" />
    </h1>
    <LoadError v-if="error" @retry="refresh()" />
    <template v-else-if="data">
      <section
        v-if="data.featured.length"
        aria-labelledby="home-featured"
        class="flex flex-col gap-4"
      >
        <h2 id="home-featured">Destacados</h2>
        <ProductGrid :products="data.featured" as="h3" />
      </section>
      <section aria-labelledby="home-categories" class="flex flex-col gap-4">
        <h2 id="home-categories">Categorías</h2>
        <ul class="flex flex-wrap gap-2">
          <li v-for="category in data.categories" :key="category.slug">
            <UButton
              :to="`/catalogo/${category.slug}`"
              color="primary"
              variant="ghost"
              size="xl"
              :label="category.name"
            />
          </li>
          <li>
            <UButton
              to="/catalogo"
              color="primary"
              variant="solid"
              size="xl"
              label="Ver todo el catálogo"
            />
          </li>
        </ul>
      </section>
    </template>
  </main>
</template>
