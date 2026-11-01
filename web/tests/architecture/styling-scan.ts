// Styling scan for the storefront (SPEC.md §4.5 Consumption rules, CR-27, P12-V26).
// Tailwind is for layout only: the Design System owns every color, border, radius, shadow,
// ring and font. The scan is a deny-list of visual utilities, so layout utilities
// (display, flex, grid, gap, spacing, sizing, position, overflow) pass without being listed.
// It is the fallback until the DS publishes its raw-value lint rule (DSR-09).
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'

export type ViolationKind =
  | 'color'
  | 'border'
  | 'radius'
  | 'shadow'
  | 'ring'
  | 'font'
  | 'arbitrary'
  | 'style-attribute'
  | 'style-block'

export interface Violation {
  file: string
  kind: ViolationKind
  /** The offending utility, or the CSS declaration. */
  match: string
}

const SCANNED_EXTENSIONS = ['.vue', '.ts', '.js', '.mjs', '.css', '.html']

// Tailwind text-* utilities that are not colors or sizes.
const TEXT_LAYOUT =
  /^text-(left|center|right|justify|start|end|wrap|nowrap|balance|pretty|ellipsis|clip)$/
const TEXT_SIZE = /^text-(xs|sm|base|lg|xl|[2-9]xl)(\/.+)?$/

/** Strips variants (`md:`, `hover:`), the important marker and a negative sign. */
function baseUtility(token: string): string {
  // Split on `:` outside square brackets, so `[&>*]:flex` and `bg-[url(a:b)]` stay whole.
  let depth = 0
  let start = 0
  for (let i = 0; i < token.length; i++) {
    const ch = token[i]
    if (ch === '[') depth++
    else if (ch === ']') depth--
    else if (ch === ':' && depth === 0) start = i + 1
  }
  return token.slice(start).replace(/^!/, '').replace(/!$/, '').replace(/^-/, '')
}

/** Returns the kind of visual utility a class token is, or null for layout and unknown tokens. */
export function classifyUtility(token: string): ViolationKind | null {
  const raw = token.trim()
  if (!raw) return null
  const base = baseUtility(raw)

  // An arbitrary-value utility or arbitrary property (`w-[300px]`, `[color:red]`).
  if (/-\[.*\]/.test(base) || /^\[.+:.+\]/.test(base)) return 'arbitrary'

  if (/^(rounded)(-|$)/.test(base)) return 'radius'
  if (/^(shadow|drop-shadow|inset-shadow|text-shadow)(-|$)/.test(base)) return 'shadow'
  if (/^(ring|inset-ring)(-|$)/.test(base)) return 'ring'
  if (/^border-(collapse|separate|spacing)/.test(base)) return null
  if (/^(border|divide|outline)(-|$)/.test(base)) return 'border'
  if (/^font-/.test(base)) return 'font'
  if (/^(italic|not-italic)$/.test(base)) return 'font'
  if (/^(tracking|leading)-/.test(base)) return 'font'
  if (TEXT_LAYOUT.test(base)) return null
  if (TEXT_SIZE.test(base)) return 'font'
  if (
    /^(bg|text|fill|stroke|from|via|to|accent|caret|decoration|placeholder|opacity)-/.test(base)
  ) {
    // `stroke-1` and `stroke-2` are widths, but still a visual value; the DS owns icon weight.
    return 'color'
  }
  return null
}

/** Class tokens found in the class-bearing attributes and object keys of a source file. */
function classStrings(source: string): string[] {
  const found: string[] = []
  const stringLiteral = /(['"`])((?:\\.|(?!\1)[^\\])*)\1/g

  // Template attributes: class="…", :class="…", ui="…", :ui="…".
  const attribute = /(?:^|[\s<])(?::|v-bind:)?(class|ui)\s*=\s*("([^"]*)"|'([^']*)')/g
  for (const m of source.matchAll(attribute)) {
    const value = m[3] ?? m[4] ?? ''
    const isBound = /(?::|v-bind:)(class|ui)\s*=/.test(m[0])
    if (isBound) {
      for (const s of value.matchAll(stringLiteral)) found.push(s[2] ?? '')
    } else {
      found.push(value)
    }
  }

  // Script objects: `class: '…'`, `ui: { root: '…' }`, `classes: […]` on one line.
  for (const line of source.split('\n')) {
    if (!/\b(class|classes|ui)\s*:/.test(line)) continue
    for (const s of line.matchAll(stringLiteral)) found.push(s[2] ?? '')
  }
  return found
}

// CSS properties that are layout. Anything else in a `style` attribute or `<style>` block
// is treated as a visual value.
const LAYOUT_PROPERTIES = new Set([
  'display',
  'flex',
  'flex-basis',
  'flex-direction',
  'flex-flow',
  'flex-grow',
  'flex-shrink',
  'flex-wrap',
  'grid',
  'grid-area',
  'grid-auto-columns',
  'grid-auto-flow',
  'grid-auto-rows',
  'grid-column',
  'grid-row',
  'grid-template',
  'grid-template-areas',
  'grid-template-columns',
  'grid-template-rows',
  'gap',
  'row-gap',
  'column-gap',
  'align-content',
  'align-items',
  'align-self',
  'justify-content',
  'justify-items',
  'justify-self',
  'place-content',
  'place-items',
  'place-self',
  'order',
  'margin',
  'margin-top',
  'margin-right',
  'margin-bottom',
  'margin-left',
  'margin-inline',
  'margin-block',
  'padding',
  'padding-top',
  'padding-right',
  'padding-bottom',
  'padding-left',
  'padding-inline',
  'padding-block',
  'width',
  'height',
  'min-width',
  'min-height',
  'max-width',
  'max-height',
  'inline-size',
  'block-size',
  'aspect-ratio',
  'position',
  'top',
  'right',
  'bottom',
  'left',
  'inset',
  'z-index',
  'overflow',
  'overflow-x',
  'overflow-y',
])

// A value that carries a brand value even on a layout property.
const VISUAL_VALUE =
  /#[0-9a-f]{3,8}\b|\b(rgb|rgba|hsl|hsla|oklch|oklab|lab|lch|color-mix|url)\(|var\(--/i

function kebab(property: string): string {
  return property.startsWith('--')
    ? property
    : property.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`).toLowerCase()
}

function isVisualDeclaration(property: string, value: string): boolean {
  return !LAYOUT_PROPERTIES.has(kebab(property.trim())) || VISUAL_VALUE.test(value)
}

/** Declarations (`prop: value`) from a CSS text. */
function cssDeclarations(css: string): Array<[string, string]> {
  const withoutComments = css.replace(/\/\*[\s\S]*?\*\//g, '')
  const out: Array<[string, string]> = []
  for (const m of withoutComments.matchAll(/([a-zA-Z-]+)\s*:\s*([^;{}]+)(?=[;}]|$)/g)) {
    out.push([m[1] ?? '', (m[2] ?? '').trim()])
  }
  return out
}

/** Keys and values of the object literal in a bound `:style`. */
function styleObjectDeclarations(expression: string): Array<[string, string]> {
  const out: Array<[string, string]> = []
  for (const m of expression.matchAll(/['"]?([a-zA-Z-]+)['"]?\s*:\s*([^,}]+)/g)) {
    out.push([m[1] ?? '', (m[2] ?? '').trim()])
  }
  return out
}

/** Scans one file's text. `file` is only used to label the violations. */
export function scanSource(file: string, source: string): Violation[] {
  const violations: Violation[] = []

  if (file.endsWith('.css')) {
    for (const [prop, value] of cssDeclarations(source)) {
      if (isVisualDeclaration(prop, value)) {
        violations.push({ file, kind: 'style-block', match: `${prop}: ${value}` })
      }
    }
    return violations
  }

  for (const token of classStrings(source).flatMap((s) => s.split(/\s+/))) {
    const kind = classifyUtility(token)
    if (kind) violations.push({ file, kind, match: token })
  }

  // `style="…"` and `:style="…"` attributes.
  for (const m of source.matchAll(/(?:^|[\s<])(:|v-bind:)?style\s*=\s*"([^"]*)"/g)) {
    const bound = Boolean(m[1])
    const declarations = bound ? styleObjectDeclarations(m[2] ?? '') : cssDeclarations(m[2] ?? '')
    for (const [prop, value] of declarations) {
      if (isVisualDeclaration(prop, value)) {
        violations.push({ file, kind: 'style-attribute', match: `${prop}: ${value}` })
      }
    }
  }

  // `<style>` blocks.
  for (const m of source.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/g)) {
    for (const [prop, value] of cssDeclarations(m[1] ?? '')) {
      if (isVisualDeclaration(prop, value)) {
        violations.push({ file, kind: 'style-block', match: `${prop}: ${value}` })
      }
    }
  }

  return violations
}

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return walk(path)
    return SCANNED_EXTENSIONS.some((ext) => path.endsWith(ext)) ? [path] : []
  })
}

/** Scans every source file under `dir` (the storefront's `app/` directory). */
export function scanTree(dir: string): Violation[] {
  return walk(dir)
    .filter((path) => !path.endsWith('.d.ts'))
    .flatMap((path) => scanSource(relative(dir, path), readFileSync(path, 'utf8')))
}
