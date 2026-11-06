<script setup lang="ts">
useHead({
  htmlAttrs: { lang: 'es-MX' },
  titleTemplate: (title) =>
    title && title !== 'Cup Noobles' ? `${title} · Cup Noobles` : 'Cup Noobles',
})

// While pre-launch mode is on, the public sees one page whatever the route (T12.15).
const prelaunch = await usePrelaunch()
</script>

<template>
  <CnApp>
    <PrelaunchPage v-if="prelaunch" />
    <template v-else>
      <SiteHeader />
      <NuxtPage />
    </template>
  </CnApp>
</template>
