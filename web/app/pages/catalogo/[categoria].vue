<script setup lang="ts">
import type { CategoryNode } from '~/types/catalog'

const api = useApi()
const slug = String(useRoute().params.categoria)

function find(nodes: CategoryNode[]): CategoryNode | undefined {
  for (const node of nodes) {
    if (node.slug.toLowerCase() === slug.toLowerCase()) return node
    const inside = find(node.children)
    if (inside) return inside
  }
  return undefined
}

const {
  data: tree,
  error,
  refresh,
} = await useAsyncData('categories', () => api<CategoryNode[]>('/catalog/categories/'))
const category = computed(() => (tree.value ? find(tree.value) : undefined))
// An unknown category is a real 404, not an empty list (REQ-053).
if (tree.value && !category.value) {
  throw createError({ statusCode: 404, statusMessage: 'Categoría no encontrada', fatal: true })
}
failOnServer(error)
</script>

<template>
  <CatalogListing v-if="category" :title="category.name" :category="category.slug" />
  <main v-else-if="error" class="mx-auto w-full max-w-6xl p-4">
    <LoadError @retry="refresh()" />
  </main>
</template>
