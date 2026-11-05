<script setup lang="ts">
// The "próximamente" page (G32, ADR-0038): built from CnLogo, a DS motif (CnSparkle) and
// CnMediaCard. It shows no date or countdown, never calls the warehouse a store (CR-47), and has
// no link to an interest list until D17 is decided. It is not for search engines.
useSeoMeta({ title: 'Próximamente', robots: 'noindex' })
</script>

<template>
  <main
    class="mx-auto flex w-full max-w-xl flex-col items-center gap-6 px-4 py-12 text-center"
    data-testid="prelaunch-page"
  >
    <CnLogo variant="vertical" label="Cup Noobles" />
    <h1>Próximamente</h1>
    <p>Estamos preparando todo. Vuelve pronto.</p>
    <CnSparkle animated />
    <CnMediaCard title="Cup Noobles" decorative as="h2" />
  </main>
</template>
