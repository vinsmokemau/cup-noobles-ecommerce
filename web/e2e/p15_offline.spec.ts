import { expect, test } from './fixtures'

// P15-V13 (T15.5): `make test-all-offline` runs the suite with the project network internal
// (docker-compose.offline.yml), so no container can reach the internet. This asks Node, not the
// browser, for an outside address from inside the `e2e` container: it proves the isolation without
// the Playwright guard, which only watches the pages (P1-V08). It runs in the `selftest` project.

// What Node reports when a name cannot be resolved or an address has no route.
const NETWORK_FAILURES = ['ENOTFOUND', 'EAI_AGAIN', 'ENETUNREACH', 'EHOSTUNREACH', 'ECONNREFUSED']

// The system error under a failed `fetch`, which may sit inside an AggregateError (one error for
// each address tried).
function failureCodes(error: unknown): string[] {
  const cause = (error as { cause?: { code?: string; errors?: { code?: string }[] } }).cause
  const codes = [cause?.code, ...(cause?.errors ?? []).map((inner) => inner.code)]
  return codes.filter((code): code is string => typeof code === 'string')
}

test('p15_v13 internal network blocks egress', async () => {
  // Only the offline run has an internal network. On any other run the request would get its
  // answer, and Part A makes no outbound connection (A13), so it is not even sent.
  test.skip(
    !process.env.E2E_OFFLINE,
    'P15-V13 needs the internal network: it runs in `make test-all-offline` (P15-V14)',
  )

  const outcome = await fetch('https://example.com', { signal: AbortSignal.timeout(20_000) }).then(
    (response) => ({ answered: response.status as number | null, error: null as unknown }),
    (error: unknown) => ({ answered: null, error }),
  )

  expect(outcome.answered, 'an outside address answered: the network is not internal').toBeNull()
  // A failure of the network itself, not a timeout and not an answer that was refused.
  expect(outcome.error).toBeInstanceOf(TypeError)
  const codes = failureCodes(outcome.error)
  expect(codes.length, `no system error under: ${String(outcome.error)}`).toBeGreaterThan(0)
  for (const code of codes) expect(NETWORK_FAILURES).toContain(code)
})
