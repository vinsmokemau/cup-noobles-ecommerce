<script setup lang="ts">
import type { ProductCardData } from '~/types/catalog'

const api = useApi()
const route = useRoute()
const router = useRouter()

const term = computed(() => (typeof route.query.q === 'string' ? route.query.q.trim() : ''))
const draft = ref(term.value)
watch(term, (value) => (draft.value = value))

const { data, error, refresh, status } = await useAsyncData(
  () => `search:${term.value}`,
  () =>
    term.value
      ? api<ProductCardData[]>('/catalog/search/', { query: { q: term.value } })
      : Promise.resolve([] as ProductCardData[]),
  { watch: [term] },
)
failOnServer(error)

function submit() {
  const q = draft.value.trim()
  router.push({ query: q ? { q } : {} })
}

// Search results are not worth indexing; the products they list are in the sitemap.
usePageSeo({ title: 'Buscar', noindex: true })
</script>

<template>
  <main class="mx-auto flex w-full max-w-6xl flex-col gap-6 p-4">
    <h1>Buscar</h1>
    <form role="search" class="flex gap-2" @submit.prevent="submit">
      <UInput
        v-model="draft"
        name="q"
        autocomplete="off"
        type="search"
        size="xl"
        class="min-w-0 flex-1"
        aria-label="Buscar productos"
        placeholder="Buscar productos"
        maxlength="100"
      />
      <UButton type="submit" color="primary" variant="solid" size="xl" label="Buscar" />
    </form>
    <LoadError v-if="error" :loading="status === 'pending'" @retry="refresh()" />
    <div v-else-if="term && data" class="flex flex-col gap-6" :aria-busy="status === 'pending'">
      <ProductGrid v-if="data.length" :products="data" as="h2" :priority-count="1" />
      <p v-else>No encontramos resultados para «{{ term }}».</p>
    </div>
  </main>
</template>
