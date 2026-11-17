import { execFileSync } from 'node:child_process'
import { lookup } from 'node:dns/promises'
import { fileURLToPath } from 'node:url'

// The E2E and development stacks are one Compose project with two database volumes (ADR-0070).
// A command that starts `db` from docker-compose.yml alone (`make test` does) puts the container
// back on the development volume while the E2E `api` keeps running, so specs started by hand
// right after it would read and write development data (G69). Playwright checks before it starts.

/** The fixed name `docker-compose.e2e.yml` gives the E2E database volume. */
export const E2E_VOLUME = 'cupnoobles_pgdata_e2e'

/** The network name `docker-compose.e2e.yml` gives the `db` container, and no other file does. */
export const E2E_DATABASE_ALIAS = 'db-e2e'

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

/**
 * The same check from inside the `e2e` compose service (T15.5), where there is no Docker CLI: the
 * `db` container answers to its E2E alias only when the E2E override made it, volume included.
 */
export function aliasProblem(answers: boolean): string | null {
  if (answers) return null
  return (
    `No container answers to ${E2E_DATABASE_ALIAS}, so the db container was not started with ` +
    `docker-compose.e2e.yml and is not on the E2E database volume (${E2E_VOLUME}). ` +
    'The specs would use development data, so Playwright will not start. ' +
    'Run them with `make test-all`, or `make e2e FILES=…`, which start the E2E stack first.'
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

/** Whether a container on the compose network answers to the E2E database alias. */
async function aliasAnswers(): Promise<boolean> {
  return lookup(E2E_DATABASE_ALIAS).then(
    () => true,
    () => false,
  )
}

/** Throws unless the running `db` container is on the E2E volume. */
export async function assertE2EDatabase(): Promise<void> {
  const problem = process.env.E2E_IN_COMPOSE
    ? aliasProblem(await aliasAnswers())
    : databaseProblem(databaseVolumes())
  if (problem) throw new Error(problem)
}
