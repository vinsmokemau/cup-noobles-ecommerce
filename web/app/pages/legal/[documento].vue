<script setup lang="ts">
// The four legal pages. The texts are the owner's (D2); until they arrive each page shows the
// placeholder. The agent never drafts legal text (CR-45).
const TITLES: Record<string, string> = {
  terminos: 'Términos y condiciones',
  privacidad: 'Aviso de privacidad',
  envios: 'Envíos',
  devoluciones: 'Devoluciones',
}
const title = TITLES[String(useRoute().params.documento)]
if (!title) {
  throw createError({ statusCode: 404, statusMessage: 'Página no encontrada', fatal: true })
}
useSeoMeta({ title })
</script>

<template>
  <main class="mx-auto flex w-full max-w-3xl flex-col gap-4 p-4">
    <h1>{{ title }}</h1>
    <p>[PLACEHOLDER] Este texto está pendiente de publicación.</p>
  </main>
</template>
