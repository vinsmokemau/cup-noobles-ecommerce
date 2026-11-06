import type { Ref } from 'vue'
import { ApiError } from '~/composables/useApi'

const STATUS_UNAVAILABLE = 503

/** `useAsyncData` wraps what the fetcher threw in an H3 error, which keeps the original as `cause`. */
export function apiErrorOf(error: unknown): ApiError | undefined {
  if (error instanceof ApiError) return error
  const cause = (error as { cause?: unknown } | null | undefined)?.cause
  return cause instanceof ApiError ? cause : undefined
}

/**
 * A server-rendered page whose data call failed to reach the API, or got a 5xx, becomes a real
 * error response, so `error.vue` renders with a 5xx status instead of a 200 that holds only an
 * inline alert (REQ-053). In the browser the page keeps its inline retry (LoadError), because
 * navigation can recover in place. Other 4xx answers stay inline; a 404 is handled by the page.
 */
export function failOnServer(error: Ref<unknown>, server = import.meta.server): void {
  // `server` is a parameter so a unit test, which runs as the client, can take the server path.
  if (!server) return
  const failure = apiErrorOf(error.value)
  if (!failure) return
  const { status } = failure
  if (status !== 0 && status < 500) return
  throw createError({
    statusCode: status >= 500 ? status : STATUS_UNAVAILABLE,
    statusMessage: 'No pudimos mostrar esta página',
    fatal: true,
  })
}
