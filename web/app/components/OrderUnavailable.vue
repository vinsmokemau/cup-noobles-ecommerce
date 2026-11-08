<script setup lang="ts">
// The landing pages' answer when the order cannot be read: a missing, expired or tampered link all
// look the same, by design (ADR-0065).
</script>

<template>
  <section class="flex flex-col gap-4" data-testid="order-unavailable">
    <h1>No encontramos este pedido</h1>
    <p>El enlace puede haber vencido. Revisa tu correo para ver el estado de tu pedido.</p>
    <UButton
      to="/catalogo"
      color="primary"
      variant="solid"
      size="xl"
      label="Explorar el catálogo"
      class="self-start"
    />
  </section>
</template>
