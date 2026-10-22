// Accessibility exceptions (SPEC.md §4.6). Each names the axe rule, the selector, the reason and
// the spec ID that accepts it. The file is empty at launch.
export interface A11yException {
  rule: string
  selector: string
  reason: string
  specId: string
}

export const a11yExceptions: A11yException[] = []
