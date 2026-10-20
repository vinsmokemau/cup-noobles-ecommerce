---
name: ui-review
description: Review storefront files against the pinned Web Interface Guidelines, with the Cup Noobles Design System and SPEC.md taking precedence. Reports findings only. Use for /ui-review, and before the task report of every storefront task in Phases 12–14.
argument-hint: "[files or glob, e.g. web/app/pages/checkout.vue]"
---

<!-- Adapted from the web-design-guidelines skill of vercel-labs/agent-skills. The rules are a pinned copy of vercel-labs/web-interface-guidelines command.md at commit 434b7f9 (MIT License; see LICENSE in this folder), kept in docs/review/web-interface-guidelines.md. Changes: a local pinned copy instead of a fetch, Design System precedence, the Nuxt mapping. -->

Review $ARGUMENTS against `docs/review/web-interface-guidelines.md`. With no argument, review the storefront files the current task changed (`git diff --name-only` under `web/app/`). Change no code.

## 1. Load

- Read `docs/review/web-interface-guidelines.md`. Never fetch a newer version: the pinned copy is the rule set (SPEC.md §0.5). Updating it is an amendment.
- Read SPEC.md §4.5 and the rules CR-26 to CR-36.
- Read the files.

## 2. Precedence

The Design System and SPEC.md win where a guideline disagrees:

- Visual styling — colors, borders, radii, shadows, focus rings, hover and active looks — belongs to the DS layer (CR-27, DS:ADR-0009). When a guideline's fix would add styling in the storefront, report it as a `DS request`, never as a storefront fix.
- Copy casing, voice and wording follow the DS voice and microcopy rules in es-MX (CR-32). Ignore the guidelines' English copy rules, such as Title Case and the use of "&".
- Numbers, currency and dates follow DS formatting.md (CR-30, CR-31), which already requires `Intl`.
- Tap targets are at least 44 px, reached through DS size props (CR-36).
- Dark mode is forced by the layer (CR-34). `color-scheme` and `theme-color` are DSR-06.

## 3. Map React wording to Nuxt

- `onClick`, `onKeyDown` → `@click`, `@keydown`; `<Link>` → `<NuxtLink>`; `htmlFor` → `for`; `spellCheck` → `spellcheck`; `autoFocus` → `autofocus`.
- URL state with `useState` and nuqs → the route query through `useRoute` and `navigateTo`.
- `priority` on an image → `@nuxt/image` with `preload` or `fetchpriority="high"`.
- The hydration rules apply to Nuxt server rendering as written.

## 4. Output

Group findings by file, in `file:line` format, one finding per line, as the guidelines specify. Tag each finding:

- `fix` — the storefront should change;
- `DS request` — only the Design System can fix it;
- `n/a` — overridden by section 2, naming the rule.

End with the number of `fix` and `DS request` findings. The task fixes its `fix` findings or registers them through the owner; `DS request` findings become DSR items.
