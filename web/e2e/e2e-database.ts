import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

// The E2E and development stacks are one Compose project with two database volumes (ADR-0070).
// A command that starts `db` from docker-compose.yml alone (`make test` does) puts the container
// back on the development volume while the E2E `api` keeps running, so specs started by hand
// right after it would read and write development data (G69). Playwright checks before it starts.

/** The fixed name `docker-compose.e2e.yml` gives the E2E database volume. */
export const E2E_VOLUME = 'cupnoobles_pgdata_e2e'

const COMPOSE = ['compose', '-f', 'docker-compose.yml', '-f', 'docker-compose.e2e.yml']

/** What is wrong with the `db` container's volumes, or `null` when it is on the E2E volume alone. */
export function databaseProblem(volumes: string[]): string | null {
  if (volumes.length === 1 && volumes[0] === E2E_VOLUME) return null
  const found = volumes.length ? volumes.join(', ') : 'no volume'
  return (
    `The db container is not on the E2E database volume (${E2E_VOLUME}); it has ${found}. ` +
    'The specs would use development data, so Playwright will not start. ' +
    'Run the specs with `make e2e FILES=…`, which starts the E2E stack first.'
  )
}

function docker(args: string[]): string {
  // Resolved here, not at import: the unit test imports this file where the URL is not a file's.
  const repoRoot = fileURLToPath(new URL('../../', import.meta.url))
  return execFileSync('docker', args, { cwd: repoRoot, encoding: 'utf8' }).trim()
}

/** The named volumes mounted in the running `db` container of this Compose project. */
function databaseVolumes(): string[] {
  const container = docker([...COMPOSE, 'ps', '-q', 'db'])
  if (!container) return []
  const names = docker(['inspect', '--format', '{{range .Mounts}}{{.Name}} {{end}}', container])
  return names.split(/\s+/).filter(Boolean)
}

/** Throws unless the running `db` container is on the E2E volume. */
export function assertE2EDatabase(): void {
  const problem = databaseProblem(databaseVolumes())
  if (problem) throw new Error(problem)
}
