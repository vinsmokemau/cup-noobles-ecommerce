// @vitest-environment node
// Architecture test: the storefront adds no visual styling of its own (REQ-050, CR-27, P12-V26).
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { classifyUtility, scanSource, scanTree, type ViolationKind } from './styling-scan'

const appDir = fileURLToPath(new URL('../../app', import.meta.url))
const fixture = readFileSync(
  fileURLToPath(new URL('./fixtures/styling-violations.vue.txt', import.meta.url)),
  'utf8',
)

const ALL_KINDS: ViolationKind[] = [
  'color',
  'border',
  'radius',
  'shadow',
  'ring',
  'font',
  'arbitrary',
  'style-attribute',
  'style-block',
]

describe('styling scan', () => {
  it('p12_v26 no visual styling in the storefront', () => {
    // The fixture has one violation of each kind, so the scan must report every kind.
    const found = new Set(scanSource('fixture.vue', fixture).map((v) => v.kind))
    expect([...found].sort()).toEqual([...ALL_KINDS].sort())

    // The real tree passes.
    expect(scanTree(appDir)).toEqual([])
  })

  it('p12_v26 layout utilities pass', () => {
    const layout = [
      'flex flex-col items-center justify-between gap-4 p-4 mx-auto',
      'grid grid-cols-2 md:grid-cols-4 sm:gap-6',
      'w-full max-w-screen-lg h-12 min-h-0 size-4',
      'relative absolute inset-0 top-2 z-10 overflow-hidden hidden',
      'text-center text-balance truncate sr-only -mt-2 hover:flex',
    ].join(' ')
    const source = `<template><div class="${layout}" :class="['flex', { 'gap-2': open }]" /></template>`
    expect(scanSource('layout.vue', source)).toEqual([])
  })

  it.each<[string, ViolationKind]>([
    ['bg-primary', 'color'],
    ['text-white', 'color'],
    ['hover:text-red-500', 'color'],
    ['text-2xl', 'font'],
    ['font-sans', 'font'],
    ['border', 'border'],
    ['border-t-2', 'border'],
    ['divide-y', 'border'],
    ['outline-none', 'border'],
    ['rounded', 'radius'],
    ['md:rounded-full', 'radius'],
    ['shadow', 'shadow'],
    ['drop-shadow-lg', 'shadow'],
    ['ring-offset-2', 'ring'],
    ['w-[300px]', 'arbitrary'],
    ['[color:red]', 'arbitrary'],
  ])('p12_v26 classifies %s as %s', (token, kind) => {
    expect(classifyUtility(token)).toBe(kind)
  })

  it('p12_v26 reads class bindings, ui props and script objects', () => {
    const source = [
      '<template>',
      `<UButton :class="active ? 'bg-primary' : 'flex'" :ui="{ base: 'rounded-lg' }" />`,
      '</template>',
      '<script setup lang="ts">',
      `const config = { class: 'shadow-lg' }`,
      '</script>',
    ].join('\n')
    expect(scanSource('bound.vue', source).map((v) => v.match)).toEqual([
      'bg-primary',
      'rounded-lg',
      'shadow-lg',
    ])
  })

  it('p12_v26 style with a layout value passes, with a visual value fails', () => {
    expect(scanSource('a.vue', '<div style="display: flex; gap: 8px" />')).toEqual([])
    expect(scanSource('b.vue', `<div :style="{ width: pct + '%' }" />`)).toEqual([])
    expect(scanSource('c.vue', '<div style="width: 10px; color: #fff" />')).toHaveLength(1)
    expect(scanSource('d.vue', '<div style="width: var(--brand)" />')).toHaveLength(1)
    expect(scanSource('e.vue', `<div :style="{ backgroundColor: c }" />`)).toHaveLength(1)
  })

  it('p12_v26 a stylesheet in the app fails, a layout-only style block passes', () => {
    expect(scanSource('main.css', '.a { color: red }')).toHaveLength(1)
    expect(scanSource('x.vue', '<style>.a { display: grid; gap: 1rem }</style>')).toEqual([])
    expect(scanSource('y.vue', '<style>.a { border-radius: 4px }</style>')).toHaveLength(1)
  })
})
