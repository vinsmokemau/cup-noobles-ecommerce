/** The absolute URL of a path on the public site. */
export function absoluteUrl(siteUrl: string, path: string) {
  return new URL(path, siteUrl).toString()
}
