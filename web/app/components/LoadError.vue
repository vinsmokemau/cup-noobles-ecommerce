<script setup lang="ts">
// A page whose data failed to load offers a retry instead of a blank page (REQ-053).
withDefaults(
  defineProps<{
    title?: string
    description?: string
    retryLabel?: string
  }>(),
  {
    title: 'No pudimos mostrar esta sección',
    description: 'Algo salió mal de nuestro lado. Inténtalo de nuevo.',
    retryLabel: 'Reintentar',
  },
)
const emit = defineEmits<{ retry: [] }>()
</script>

<template>
  <UAlert :title="title" :description="description" color="error" variant="subtle" role="alert">
    <template #actions>
      <UButton
        color="primary"
        variant="solid"
        size="xl"
        :label="retryLabel"
        @click="emit('retry')"
      />
    </template>
  </UAlert>
</template>
