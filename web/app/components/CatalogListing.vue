<script setup lang="ts">
import type { Facet, ProductPage } from '~/types/catalog'

// The catalog grid with its facet sidebar. The filters live in the URL (`attr.<key>`), so a filtered
// list can be shared and the back button undoes a choice. The category page is this component with a scope.
const props = defineProps<{
  title: string
  /** Category slug; the list and the facets cover that category and its descendants. */
  category?: string
}>()

const api = useApi()
const route = useRoute()
const router = useRouter()

const filters = computed(() => attrFiltersFromQuery(route.query))
const cursor = computed(() => (typeof route.query.cursor === 'string' ? route.query.cursor : null))

const filterQuery = computed(() => ({
  ...(props.category ? { category: props.category } : {}),
  ...Object.fromEntries(Object.entries(filters.value).map(([k, v]) => [`attr.${k}`, v[0]])),
}))

const key = computed(() => `catalog:${JSON.stringify(filterQuery.value)}:${cursor.value ?? ''}`)
const { data, error, refresh, status } = await useAsyncData(
  () => key.value,
  async () => {
    const [page, facets] = await Promise.all([
      api<ProductPage>('/catalog/products/', {
        query: { ...filterQuery.value, ...(cursor.value ? { cursor: cursor.value } : {}) },
      }),
      api<{ facets: Facet[] }>('/catalog/facets/', { query: filterQuery.value }),
    ])
    return { page, facets: facets.facets }
  },
  { watch: [key] },
)
failOnServer(error)

function setFilters(next: Record<string, string[]>) {
  router.push({
    query: { ...queryWithoutFilters(route.query), ...attrFiltersToQuery(next, filters.value) },
  })
}
const nextCursor = computed(() => cursorOf(data.value?.page.next))
const previousCursor = computed(() => cursorOf(data.value?.page.previous))
const pageLink = (value: string) => ({ query: { ...route.query, cursor: value } })

useSeoMeta({ title: () => props.title })
</script>

<template>
  <main class="mx-auto flex w-full max-w-6xl flex-col gap-6 p-4">
    <h1>{{ title }}</h1>
    <LoadError v-if="error" @retry="refresh()" />
    <div v-else-if="data" class="flex flex-col gap-6 lg:flex-row">
      <FilterSidebar
        class="lg:w-64 lg:shrink-0"
        :facets="data.facets"
        :model-value="filters"
        @update:model-value="setFilters"
      />
      <div class="flex min-w-0 flex-1 flex-col gap-6" :aria-busy="status === 'pending'">
        <ProductGrid v-if="data.page.results.length" :products="data.page.results" as="h2" />
        <p v-else>No encontramos productos con estos filtros.</p>
        <nav
          v-if="nextCursor || previousCursor"
          aria-label="Paginación"
          class="flex justify-between gap-4"
        >
          <UButton
            v-if="previousCursor"
            :to="pageLink(previousCursor)"
            color="primary"
            variant="ghost"
            size="xl"
            label="Anterior"
          />
          <UButton
            v-if="nextCursor"
            :to="pageLink(nextCursor)"
            color="primary"
            variant="ghost"
            size="xl"
            label="Siguiente"
          />
        </nav>
      </div>
    </div>
  </main>
</template>
