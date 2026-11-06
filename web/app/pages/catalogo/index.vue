<script setup lang="ts">
// The owner's text (G55, ADR-0062).
const description =
  'Explora el catálogo de Cup Noobles: productos de cultura geek y gamer. Filtra por categoría y encuentra el que buscas.'
</script>

<template>
  <CatalogListing title="Catálogo" :description="description" />
</template>
