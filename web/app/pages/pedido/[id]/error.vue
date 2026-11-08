<script setup lang="ts">
import { ApiError } from '~/composables/useApi'

// The provider could not take the payment. The order keeps its stock until its deadline, so the
// customer can try again from here without building a new cart (G22, ADR-0066).
const { retryPayment, token } = useOrderStatus()

const retrying = ref(false)
const failure = ref('')

async function retry() {
  if (retrying.value) return
  retrying.value = true
  failure.value = ''
  try {
    const { checkout_url } = await retryPayment()
    // Stay disabled while the browser leaves for the provider's page.
    window.location.href = checkout_url
  } catch (caught) {
    retrying.value = false
    if (caught instanceof ApiError && caught.status === 409) {
      failure.value =
        'Este pedido ya no admite un nuevo pago. Vuelve al carrito para hacer un pedido nuevo.'
    } else if (caught instanceof ApiError && caught.status === 404) {
      failure.value = 'Este enlace ya no es válido. Revisa tu correo o haz un pedido nuevo.'
    } else {
      failure.value =
        caught instanceof ApiError ? caught.detail : 'Algo salió mal. Inténtalo de nuevo.'
    }
  }
}

usePageSeo({ title: 'Tu pedido', noindex: true })
</script>

<template>
  <main class="mx-auto flex w-full max-w-xl flex-col gap-4 p-4">
    <OrderUnavailable v-if="!token" />
    <template v-else>
      <h1>No pudimos procesar tu pago</h1>
      <p>Tu pedido sigue guardado. Puedes intentar el pago de nuevo.</p>
      <UAlert v-if="failure" :description="failure" color="error" variant="subtle" role="alert" />
      <div class="flex flex-wrap items-center gap-4">
        <UButton
          label="Intentar el pago de nuevo"
          color="primary"
          variant="solid"
          size="xl"
          :loading="retrying"
          :disabled="retrying"
          @click="retry"
        />
        <UButton to="/carrito" variant="outline" size="xl" label="Volver al carrito" />
      </div>
    </template>
  </main>
</template>
