import type { PublicImage } from '~/types/catalog'

/** The URL of the smallest derivative at least `width` px wide, or the largest one when none reaches it. */
export function pickImageSrc(
  image: Pick<PublicImage, 'sources'> | null | undefined,
  width: number,
) {
  const sources = [...(image?.sources ?? [])].sort((a, b) => a.width - b.width)
  return (sources.find((s) => s.width >= width) ?? sources.at(-1))?.url
}
