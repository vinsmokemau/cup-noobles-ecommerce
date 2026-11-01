// The only place the storefront calls `$fetch` (CR-29, enforced by T12.11).

const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

const MESSAGE_RATE_LIMITED = 'Hiciste demasiados intentos. Espera un momento e inténtalo de nuevo.'
const MESSAGE_NETWORK = 'No pudimos conectarnos. Revisa tu conexión e inténtalo de nuevo.'
const MESSAGE_GENERIC = 'Algo salió mal. Inténtalo de nuevo.'

/** The one error every failed request becomes. */
export class ApiError extends Error {
  readonly status: number
  readonly detail: string
  readonly fieldErrors: Record<string, string[]>

  constructor(status: number, detail: string, fieldErrors: Record<string, string[]> = {}) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.fieldErrors = fieldErrors
  }
}

type FetchFailure = {
  status?: number
  statusCode?: number
  response?: { status?: number; _data?: unknown }
  data?: unknown
}

function toStrings(value: unknown): string[] {
  if (typeof value === 'string') return [value]
  if (Array.isArray(value)) return value.filter((item): item is string => typeof item === 'string')
  return []
}

/** Maps a failed `$fetch` call (DRF error shapes, or no response at all) to an `ApiError`. */
export function toApiError(failure: unknown): ApiError {
  if (failure instanceof ApiError) return failure
  const error = (failure ?? {}) as FetchFailure
  const status = error.response?.status ?? error.statusCode ?? error.status ?? 0
  if (status === 0) return new ApiError(0, MESSAGE_NETWORK)
  if (status === 429) return new ApiError(429, MESSAGE_RATE_LIMITED)

  const payload = error.data ?? error.response?._data
  let detail = ''
  const fieldErrors: Record<string, string[]> = {}
  if (payload && typeof payload === 'object' && !Array.isArray(payload)) {
    for (const [key, value] of Object.entries(payload)) {
      const messages = toStrings(value)
      if (!messages.length) continue
      if (key === 'detail' || key === 'non_field_errors') detail = messages.join(' ')
      else fieldErrors[key] = messages
    }
  } else {
    detail = toStrings(payload).join(' ')
  }
  return new ApiError(status, detail || MESSAGE_GENERIC, fieldErrors)
}

function readCookie(cookies: string | undefined, name: string): string | undefined {
  for (const part of (cookies ?? '').split(';')) {
    const [key, ...rest] = part.trim().split('=')
    if (key === name) return decodeURIComponent(rest.join('='))
  }
  return undefined
}

type ApiOptions = {
  method?: string
  query?: Record<string, unknown>
  body?: Record<string, unknown> | unknown[] | FormData
  headers?: Record<string, string>
}

export function useApi() {
  const baseURL = useRuntimeConfig().public.apiBase
  // Server render: the incoming cookie, so the API sees the visitor's session. In the browser
  // this is empty and the browser attaches cookies itself.
  const incoming = useRequestHeaders(['cookie'])

  return async function api<T = unknown>(path: string, options: ApiOptions = {}): Promise<T> {
    const method = (options.method ?? 'GET').toUpperCase()
    const headers: Record<string, string> = { ...options.headers }
    if (incoming.cookie) headers.cookie = incoming.cookie
    if (UNSAFE_METHODS.has(method)) {
      const cookies = import.meta.client ? document.cookie : incoming.cookie
      const token = readCookie(cookies, 'csrftoken')
      if (token) headers['X-CSRFToken'] = token
    }
    try {
      return await $fetch<T>(path, { ...options, method, baseURL, headers } as never)
    } catch (failure) {
      throw toApiError(failure)
    }
  }
}
