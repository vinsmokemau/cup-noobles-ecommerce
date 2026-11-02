<script setup lang="ts">
import type { Facet } from '~/types/catalog'

// Facet filters: a sidebar from `lg`, and a slideover opened by a button below that (360 px first).
// `modelValue` maps a facet key to its chosen values; the page keeps it in the URL as `attr.<key>` (T12.16).
const props = withDefaults(
  defineProps<{
    facets: Facet[]
    modelValue: Record<string, string[]>
    labels?: { title: string; open: string; clear: string; yes: string; no: string }
  }>(),
  {
    labels: () => ({
      title: 'Filtros',
      open: 'Filtrar',
      clear: 'Limpiar filtros',
      yes: 'Sí',
      no: 'No',
    }),
  },
)
const emit = defineEmits<{ 'update:modelValue': [value: Record<string, string[]>] }>()

const open = ref(false)
const active = computed(() => Object.values(props.modelValue).some((v) => v.length))
</script>

<template>
  <div v-if="facets.length">
    <div class="lg:hidden">
      <USlideover v-model:open="open" :title="labels.title" side="left">
        <UButton
          color="primary"
          variant="ghost"
          size="xl"
          icon="i-ph-funnel-bold"
          :label="labels.open"
        />
        <template #body>
          <FilterSidebarGroups
            :facets="facets"
            :model-value="modelValue"
            :labels="labels"
            @update:model-value="emit('update:modelValue', $event)"
          />
          <UButton
            v-if="active"
            color="primary"
            variant="ghost"
            size="xl"
            :label="labels.clear"
            @click="emit('update:modelValue', {})"
          />
        </template>
      </USlideover>
    </div>
    <aside class="hidden lg:block" :aria-label="labels.title">
      <FilterSidebarGroups
        :facets="facets"
        :model-value="modelValue"
        :labels="labels"
        @update:model-value="emit('update:modelValue', $event)"
      />
      <UButton
        v-if="active"
        color="primary"
        variant="ghost"
        size="xl"
        :label="labels.clear"
        @click="emit('update:modelValue', {})"
      />
    </aside>
  </div>
</template>
