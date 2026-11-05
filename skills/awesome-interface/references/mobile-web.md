# Mobile web

Read this reference when a web app or PWA is built for or reviewed on phone browsers, or when a defect appears only on a touch device. It covers the platform layer: viewport units, touch input, scroll chaining, safe areas and browser chrome. [Accessibility](accessibility.md) owns zoom, target size, hover alternatives and `touch-action` limits; [layout](layout.md) owns safe-area placement; [typography](typography.md) owns input text size; [web gestures](gestures.md) owns custom drag behavior. Native-platform apps need their own project guidance.

## Symptoms

Match the observed or reported symptom, then apply the smallest fix in the project's existing styling mechanism. Apply each fix where its reason holds, not globally out of habit.

| Symptom | Cause | Starting fix |
| --- | --- | --- |
| Bottom bar or button hidden under the browser toolbar; shell taller than the screen | `100vh` is the largest viewport, measured with the browser chrome collapsed | `100dvh` for an app shell or bottom-pinned UI; `100svh` for a hero or first screen that should not shift during scroll |
| Hover style stays after a tap | Touch browsers emulate `:hover` on tap | Gate hover rules with `@media (hover: hover) and (pointer: fine)`; give touch press feedback through `:active` |
| Gray or blue flash on tap | The browser's default tap highlight | `-webkit-tap-highlight-color: transparent`, only when every tappable control keeps its own press state |
| Page zooms when an input is focused | iOS Safari zooms into input text under 16px | The input-size rule in [typography](typography.md#rendering-details): raise the size for touch without changing desktop; never disable user zoom |
| Long press selects a button label or opens a callout | Control text is selectable | The `user-select` rule in [typography](typography.md#rendering-details), with the `-webkit-user-select` prefix for Safari; add `-webkit-touch-callout: none` only for links or images used as controls |
| Tap feels late | Feedback on `click` only, or double-tap zoom delay | `:active` or `pointerdown` feedback; `touch-action: manipulation` on controls |
| Pulling past the top refreshes the page or scrolls the page behind a sheet | Scroll chaining to the document | `overscroll-behavior: none` on the root for an app shell, `contain` on inner scroll containers; keep pull-to-refresh on document-style pages. Never block scrolling with `touchmove` and `preventDefault()` |
| Header or tab bar collides with the notch or home indicator | Safe-area insets not applied | `viewport-fit=cover` in the viewport meta, then `env(safe-area-inset-*, 0px)` padding on fixed headers, bars, sheets and toasts. Without the meta tag the insets are `0` |
| A horizontal carousel scrolls the page vertically | Gesture axis not declared | `touch-action: pan-y` on a JavaScript carousel; prefer native `scroll-snap` for a scrolling track |
| Status bar color mismatches the page or theme | One `theme-color` for both schemes | One `theme-color` per `prefers-color-scheme`, matched to the top edge of the page; update it on a manual theme toggle |

Use capability media queries, not user-agent or width checks, to detect touch. Touch and mouse can coexist on one device.

## Verify

Desktop device emulation does not reproduce sticky hover, tap highlight, browser toolbar height, input zoom, overscroll, safe areas or the software keyboard. Check the changed rules in source and in a narrow viewport, confirm desktop behavior is unchanged, and report which fixes still need a physical phone. When none was available, say so instead of declaring the fix verified.
