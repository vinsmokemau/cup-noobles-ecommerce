/**
 * Whether the store is in pre-launch mode for this visitor (G32, ADR-0038). The API decides: it
 * answers a catalog request with `503 {"prelaunch": true}` to the public and with the catalog to
 * a staff session, and the server render forwards the visitor's cookie. Any other failure counts
 * as "off", so the page that follows reports its own error (REQ-053).
 */
export async function usePrelaunch() {
  const api = useApi()
  const { data } = await useAsyncData('prelaunch', async () => {
    try {
      await api('/catalog/categories/')
      return false
    } catch (failure) {
      return toApiError(failure).prelaunch
    }
  })
  return computed(() => data.value === true)
}
