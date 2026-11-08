<script setup lang="ts">
// The page the provider sends the browser to after a card payment (T13.7). The webhook may arrive
// after the browser does, so the page polls the order-status endpoint until the order is paid.
const { fetchStatus, token } = useOrderStatus()
const { order, phase } = useOrderPolling(fetchStatus, token !== '', (o) => isPaidOrLater(o.state))

usePageSeo({ title: 'Tu pedido', noindex: true })
</script>

<template>
  <main class="mx-auto flex w-full max-w-xl flex-col gap-4 p-4">
    <!-- One persistent live region, so each change of phase is announced. -->
    <div aria-live="polite" class="flex flex-col gap-4">
      <section
        v-if="phase === 'waiting'"
        class="flex flex-col gap-2"
        aria-busy="true"
        data-testid="order-confirming"
      >
        <h1>Confirmando tu pago…</h1>
        <p>Esto puede tardar unos segundos.</p>
      </section>

      <section v-else-if="phase === 'done' && order" class="flex flex-col gap-4">
        <h1 data-testid="order-confirmed">Pago confirmado</h1>
        <p>
          Tu pedido <strong translate="no">{{ order.number }}</strong> está pagado. Te enviaremos un
          correo con los detalles.
        </p>
        <dl class="flex justify-between gap-4">
          <dt>Total</dt>
          <dd>{{ formatMXN(order.total_cents) }}</dd>
        </dl>
        <UButton
          to="/catalogo"
          color="primary"
          variant="solid"
          size="xl"
          label="Seguir comprando"
          class="self-start"
        />
      </section>

      <section v-else-if="phase === 'timeout'" class="flex flex-col gap-4">
        <h1 data-testid="order-timeout">Seguimos confirmando tu pago</h1>
        <p>Te avisaremos por correo en cuanto lo confirmemos.</p>
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
        <h1 data-testid="order-closed">Este pedido ya no está activo</h1>
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
