<script setup lang="ts">
// Phase 1 index page: the DS layer renders, and the smoke spec (P1-V09) has a page to check.
// Phase 12 replaces it with the home page.
useHead({ title: 'Cup Noobles', htmlAttrs: { lang: 'es-MX' } })
</script>

<template>
  <main>
    <h1>
      <CnLogo variant="horizontal" label="Cup Noobles" />
    </h1>
  </main>
</template>
