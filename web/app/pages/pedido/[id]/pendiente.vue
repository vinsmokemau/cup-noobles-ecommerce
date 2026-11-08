<script setup lang="ts">
// OXXO and SPEI: the customer pays later with a voucher, so the page puts the voucher link and its
// deadline first (T13.7). The voucher exists once the provider's notification has been processed,
// which can be after the browser arrives, so the page waits for it the way `gracias` waits for
// the payment. The expiry is shown in the store timezone (CR-31).
const { fetchStatus, token, publicId } = useOrderStatus()
const { order, phase } = useOrderPolling(
  fetchStatus,
  token !== '',
  (o) => o.voucher_url !== null || isPaidOrLater(o.state),
)

// A payment that already arrived belongs on the confirmation page.
watch(phase, async (next) => {
  if (next === 'done' && order.value && isPaidOrLater(order.value.state)) {
    await navigateTo(
      { path: `/pedido/${publicId}/gracias`, query: { t: token } },
      { replace: true },
    )
  }
})

usePageSeo({ title: 'Tu pedido', noindex: true })
</script>

<template>
  <main class="mx-auto flex w-full max-w-xl flex-col gap-4 p-4">
    <!-- One persistent live region, so each change of phase is announced. -->
    <div aria-live="polite" class="flex flex-col gap-4">
      <section
        v-if="phase === 'done' && order?.voucher_url"
        class="flex flex-col gap-4"
        data-testid="order-voucher"
      >
        <h1>Tu pedido espera tu pago</h1>
        <p>
          Pedido <strong translate="no">{{ order.number }}</strong
          >. Paga con tu ficha por {{ formatMXN(order.total_cents) }}.
        </p>
        <UButton
          :href="order.voucher_url"
          target="_blank"
          rel="noopener"
          color="primary"
          variant="solid"
          size="xl"
          label="Ver mi ficha de pago"
          class="self-start"
          data-testid="voucher-link"
        />
        <p v-if="order.voucher_expires_at" data-testid="voucher-expiry">
          Págala antes del
          <time :datetime="order.voucher_expires_at">{{
            formatDateTime(order.voucher_expires_at)
          }}</time
          >. Después de esa fecha la ficha deja de funcionar.
        </p>
        <p>Cuando recibamos tu pago, te lo confirmaremos por correo.</p>
      </section>

      <section
        v-else-if="phase === 'waiting' || phase === 'done'"
        class="flex flex-col gap-2"
        aria-busy="true"
      >
        <h1>Estamos preparando tu ficha de pago</h1>
        <p>Esto puede tardar unos segundos.</p>
      </section>

      <section v-else-if="phase === 'timeout'" class="flex flex-col gap-4">
        <h1>Tu ficha de pago aún no está lista</h1>
        <p>Te la enviaremos por correo en cuanto esté lista.</p>
        <UButton
          to="/catalogo"
          color="primary"
          variant="solid"
          size="xl"
          label="Seguir comprando"
          class="self-start"
        />
      </section>

      <section v-else-if="phase === 'closed'" class="flex flex-col gap-4">
        <h1>Este pedido ya no está activo</h1>
        <p>Si pagaste, te avisaremos por correo. Si no, puedes hacer un pedido nuevo.</p>
        <UButton
          to="/catalogo"
          color="primary"
          variant="solid"
          size="xl"
          label="Explorar el catálogo"
          class="self-start"
        />
      </section>

      <OrderUnavailable v-else />
    </div>
  </main>
</template>
