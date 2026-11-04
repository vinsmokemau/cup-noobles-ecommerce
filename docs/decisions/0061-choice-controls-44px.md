# ADR-0061: Checkboxes and radios reach the 44 px tap target through the DS size `2xl`

## Status

accepted (2026-11-03)

## Context

CR-36 requires storefront tap targets of at least 44 px, reached through DS size props and never by restyling. P12-V21 measures it at 360 px. Buttons at `xl` reach 44 px, but `UCheckbox`, `UCheckboxGroup` and `URadioGroup` were 24 px tall at `xl`, the DS minimum (REQ-028 AC2), and no size prop went higher (DSR-12, found in T12.9). Padding added in the storefront would be restyling, which CR-36 forbids. Lowering P12-V21 to 24 px would drop the storefront's own rule. The DS added the size `2xl` to the three controls in 1.7.0: every row is at least 44 px tall and the label fills the row. The box, the text size, the focus ring and the sizes `xs` to `xl` are unchanged.

## Decision

T12.9 waits for the DS. A new task, T12.23, raises the three DS packages to exactly 1.7.0. T12.9 depends on it and sets `size="2xl"` on the checkboxes and radios in `VariantSelector` and `FilterSidebarGroups`. P12-V21 keeps its 44 px assertion. The storefront adds no padding or sizing of its own to these controls.

## Consequences

T12.9, T12.15 and T12.12 wait for T12.23. The storefront adds no styling. A later DS change to the `2xl` size is picked up by the next DS upgrade task.

## Source

DSR-12; OA-77; CR-36; DS 1.7.0.
