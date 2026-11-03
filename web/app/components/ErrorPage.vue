<script setup lang="ts">
// The four parts of the DS error-page pattern, in order: the status code, a title in a real `h1`
// that says what happened, one sentence that says what to do, and one primary action. It never
// shows technical details. The action is a link when `to` is set, and a button otherwise.
defineProps<{
  status: number | string
  title: string
  message: string
  actionLabel: string
  to?: string
}>()
defineEmits<{ action: [] }>()
</script>

<template>
  <main
    class="mx-auto flex w-full max-w-xl flex-col items-center gap-4 px-4 py-12 text-center"
    data-testid="error-page"
  >
    <p data-testid="error-status">{{ status }}</p>
    <h1>{{ title }}</h1>
    <p>{{ message }}</p>
    <UButton v-if="to" :to="to" color="primary" variant="solid" size="xl" :label="actionLabel" />
    <UButton
      v-else
      color="primary"
      variant="solid"
      size="xl"
      :label="actionLabel"
      @click="$emit('action')"
    />
  </main>
</template>
