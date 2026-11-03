import { describe, expect, it } from 'vitest'
import {
  attrFiltersFromQuery,
  attrFiltersToQuery,
  cursorOf,
  queryWithoutFilters,
} from '~/utils/catalog'

describe('catalog URL helpers', () => {
  it('reads attr filters from the query', () => {
    expect(
      attrFiltersFromQuery({ 'attr.linea': 'Nendoroid', q: 'x', 'attr.a': ['1', '2'] }),
    ).toEqual({ linea: ['Nendoroid'], a: ['1'] })
  })

  it('a second value in a facet replaces the first', () => {
    expect(attrFiltersToQuery({ linea: ['Figma', 'Nendoroid'] }, { linea: ['Figma'] })).toEqual({
      'attr.linea': 'Nendoroid',
    })
    expect(attrFiltersToQuery({ linea: [] }, { linea: ['Figma'] })).toEqual({})
  })

  it('a filter change drops filters and the cursor but keeps the rest', () => {
    expect(queryWithoutFilters({ 'attr.linea': 'a', cursor: 'c', q: 'x' })).toEqual({ q: 'x' })
  })

  it('reads the cursor of a page link', () => {
    expect(cursorOf('http://api/x/?cursor=abc&page_size=8')).toBe('abc')
    expect(cursorOf(null)).toBeNull()
  })
})
