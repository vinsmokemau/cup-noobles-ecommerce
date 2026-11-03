<script setup lang="ts">
import type { NuxtError } from '#app'

// Built from the DS error-page pattern (docs/03-patterns/error-pages.md). A page that does not
// exist says so and links back to the catalog; every other failure is ours, so it says that and
// offers a retry. The technical message is never shown (REQ-053).
const props = defineProps<{ error: NuxtError }>()

const status = computed(() => props.error.statusCode ?? 500)
const notFound = computed(() => status.value === 404)
const title = computed(() =>
  notFound.value ? 'No encontramos esta página' : 'Algo salió mal de nuestro lado',
)
const message = computed(() =>
  notFound.value
    ? 'Puede que se haya movido o que la dirección tenga un error. Ve al catálogo y búscala desde ahí.'
    : 'No pudimos mostrar esta página. Vuelve a intentarlo en unos minutos.',
)

// A page needs its own title (WCAG 2.4.2), and an error page is not for search engines.
useSeoMeta({ title, robots: 'noindex' })

// A full reload, so the page asks for its data again whatever state the failed render left.
const retry = () => reloadNuxtApp({ persistState: false })
</script>

<template>
  <UApp>
    <ErrorPage
      v-if="notFound"
      :status="status"
      :title="title"
      :message="message"
      action-label="Ver el catálogo"
      to="/catalogo"
    />
    <ErrorPage
      v-else
      :status="status"
      :title="title"
      :message="message"
      action-label="Volver a intentar"
      @action="retry"
    />
  </UApp>
</template>
