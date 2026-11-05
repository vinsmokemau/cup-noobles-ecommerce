<script setup lang="ts">
useHead({
  htmlAttrs: { lang: 'es-MX' },
  titleTemplate: (title) =>
    title && title !== 'Cup Noobles' ? `${title} · Cup Noobles` : 'Cup Noobles',
})
</script>

<template>
  <CnApp>
    <NuxtPage />
  </CnApp>
</template>
