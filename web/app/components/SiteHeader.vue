<script setup lang="ts">
// The site header (T13.5): the logo home and the cart link with the number of units in the cart.
// The count is read from `useCart` state; the server's answer is the only source (CR-24).
const { cart, count, refresh } = useCart()

// Read in the browser, not during server rendering: the API hands the visitor their cart and CSRF
// cookies on this first read, and a server-side read cannot pass them on to the browser. A failed
// read must not break the header: the badge stays as it was and the rest keeps working.
onMounted(async () => {
  if (cart.value) return
  try {
    await refresh()
  } catch {
    // The cart page and the product page report their own failures.
  }
})

const label = computed(() => {
  if (count.value === 0) return 'Carrito'
  return count.value === 1 ? 'Carrito, 1 producto' : `Carrito, ${count.value} productos`
})
</script>

<template>
  <header class="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 p-4">
    <ULink to="/" class="inline-flex min-h-11 items-center">
      <CnLogo variant="horizontal" label="Cup Noobles, inicio" />
    </ULink>
    <nav aria-label="Principal">
      <UButton
        to="/carrito"
        color="neutral"
        variant="ghost"
        size="xl"
        icon="i-ph-shopping-cart-bold"
        data-testid="cart-link"
      >
        <span class="sr-only" aria-live="polite">{{ label }}</span>
        <UBadge
          v-if="count > 0"
          color="primary"
          variant="solid"
          :label="String(count)"
          data-testid="cart-badge"
          aria-hidden="true"
        />
      </UButton>
    </nav>
  </header>
</template>
