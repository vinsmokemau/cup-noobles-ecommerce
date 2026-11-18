// The test environment has no icon provider (vitest.config.ts, T15.5), so every icon a mounted
// component shows fails to load, and Nuxt Icon warns about each one. The warning comes after the
// load gives up, which can be after the file's last test: when it reaches Vitest while the worker
// closes, the run fails with "Closing rpc while onUserConsoleLog was pending" although every test
// passed. No test reads an icon's drawing, so that one warning is dropped; any other is kept.
export const MISSING_ICON_WARNING = '[Icon] failed to load icon'

export function quietMissingIcons(target: Pick<Console, 'warn'>): void {
  const warn = target.warn.bind(target)
  target.warn = (...args: unknown[]) => {
    if (typeof args[0] === 'string' && args[0].startsWith(MISSING_ICON_WARNING)) return
    warn(...args)
  }
}
