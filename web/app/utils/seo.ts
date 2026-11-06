/** The absolute URL of a path on the public site. */
export function absoluteUrl(siteUrl: string, path: string) {
  return new URL(path, siteUrl).toString()
}

const META_DESCRIPTION_MAX = 160

/**
 * The meta description of a product page (G55, ADR-0062): the first paragraph of its plain-text
 * description, on one line, at most 160 characters and cut at a word. Without text, nothing.
 */
export function metaDescription(text: string | undefined | null) {
  const first = (text ?? '').split(/\n{2,}/).find((p) => p.trim())
  const line = (first ?? '').replace(/\s+/g, ' ').trim()
  if (!line) return undefined
  if (line.length <= META_DESCRIPTION_MAX) return line
  const cut = line.slice(0, META_DESCRIPTION_MAX - 1)
  const atWord = cut.slice(0, cut.lastIndexOf(' '))
  return `${atWord || cut}…`
}
