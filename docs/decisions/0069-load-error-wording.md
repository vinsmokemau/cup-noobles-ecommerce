# ADR-0069: The shared wording of the load-error alert

## Status

accepted (2026-11-07)

## Context

`LoadError` is the alert the storefront shows with a "Reintentar" button when a page or region cannot be shown. T13.4 put it inside the `NuxtErrorBoundary` of the cart and checkout, where it can also stand for a render error and not only a failed call. Its text said "Revisa tu conexión", which blames the customer's connection and is wrong for a render error. The Design System microcopy and this spec gave no wording for that case (G60). Three options were shown: a new wording that fits both causes, a variant of the old title with a neutral description, and the old text.

## Decision

`LoadError` shows, by default, the title "No pudimos mostrar esta sección" and the description "Algo salió mal de nuestro lado. Inténtalo de nuevo.". The button label stays "Reintentar". The text is shared by every use of `LoadError`: the catalog and product pages, the cart and the checkout.

## Consequences

One wording for every load failure, in the tone of `error.vue`. The network-failure message of `useApi` ("No pudimos conectarnos…") is a different message and is unchanged. Changing the text later touches only `LoadError.vue`.

## Source

OA-87; G60. G61 (no feedback while a retry runs) is not decided here: the owner accepted its suggested action, and it stays Open.
