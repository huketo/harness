# Playbook: named patterns and symptoms

Read this when a request names a pattern or symptom ("declutter this", "the spacing feels off", "add a reveal hero", "nudge the arrow on hover") rather than a domain. Each play routes to the section that owns its rule; read that section, apply it, and run its verification. This file owns only the recipes after the table. A play does not widen the task's authority: scope and read-only boundaries stay as the main skill sets them.

## Plays

| Play | Symptom it answers | Read |
| --- | --- | --- |
| Declutter | One relationship is drawn by borders, backgrounds, dividers and gaps at once; decoration or motion competes with content | [Layout: group with space](layout.md#group-with-space-and-shared-edges) |
| Spacing | Equal gaps everywhere, so groups do not read | [Layout: group with space](layout.md#group-with-space-and-shared-edges), line height in [typography](typography.md#hierarchy-measure-and-spacing) |
| Copy | Labels, confirmations or errors do not say what happens next | [Writing: labels](writing.md#labels-that-predict-the-outcome), [errors](writing.md#errors-are-recovery-instructions) |
| Alignment | Ragged left edges; a centered icon that looks off-center | Shared edges in [layout](layout.md#group-with-space-and-shared-edges), [optical alignment](ui.md#optical-alignment) |
| Font | An unrequested typeface change, a missing weight, digits that jitter as values change | [Typography: fonts](typography.md#fonts-and-supported-features), [numerals](typography.md#numerals-punctuation-and-language) |
| Font size | Ad hoc sizes blur the hierarchy; body lines run too long | [Typography: hierarchy and measure](typography.md#hierarchy-measure-and-spacing) |
| Imagery | Stretched or squashed images, layout shift on load, oversized downloads, edges melting into the surface | [UI: imagery](ui.md#imagery) |
| Navigation dropdown | Panels grow from the center, or close and reopen between sibling triggers | [UI: entrances and exits](ui.md#entrances-exits-and-icon-swaps), then the [recipe](#navigation-dropdown) |
| Arrow shift button | Hover widens the button, shifts its neighbors or sticks after a tap | The [recipe](#arrow-shift-button) |
| Reveal hero | A page entrance makes the user wait through stacked or uniform delays | [Choreography](choreography.md), then the [recipe](#reveal-hero) |
| Group motion | Several elements animate on one event; a removed item leaves a gap that closes late | [Choreography](choreography.md) |
| Drag and sheets | A drag trails the finger, jumps on release or cannot be caught mid-animation | [Web gestures](gestures.md) |
| Hostile content | Long names, empty lists, huge counts, extreme images | [Stress test](stress-test.md) when explicitly requested, with [worst-case data](worst-case-data.md) |

## Recipes

Each recipe is one dependency-free implementation for the web. Map its durations and curves onto the project's motion tokens (`--ease-out` stands for the project's strong ease-out) and its markup onto existing components; when the project's component library already provides the pattern, configure that instead. The owning sections above decide whether the pattern applies at all.

### Navigation dropdown

For site navigation whose triggers open panels of links. Triggers are buttons that expose their expanded state and control the panel; the bar remains a navigation landmark of links, not an application menu ([accessibility](accessibility.md#start-with-the-interaction-contract)).

Use one panel for the whole bar. It opens from the trigger, closes faster than it opens, and moves between triggers without closing:

```css
.nav-panel {
  position: absolute;
  translate: var(--panel-x, 0) 0;
  transform-origin: var(--origin-x, 50%) 0;
  opacity: 0;
  transform: scale(0.96);
  visibility: hidden;
  transition: opacity 120ms var(--ease-out), transform 120ms var(--ease-out),
    translate 200ms var(--ease-out), visibility 0s 120ms;
}
.nav-panel[data-open] {
  opacity: 1;
  transform: none;
  visibility: visible;
  transition: opacity 180ms var(--ease-out), transform 180ms var(--ease-out),
    translate 200ms var(--ease-out), visibility 0s;
}
```

When a trigger is selected, set `--panel-x` to the trigger's offset clamped so the panel stays inside the viewport, and `--origin-x` to the trigger's center relative to the panel. If the panel was already open for a sibling, keep `data-open`, append the new content offset toward the side of the new trigger, and fade the old content out toward the other side before removing it. When closing starts, set `inert` on the panel so its links leave focus and the accessibility tree at once, as [UI motion](ui.md#entrances-exits-and-icon-swaps) requires; `visibility` then hides it when the exit ends. Remove `inert` when it opens. Keep the panel open across the pointer's path from trigger to panel through the component's hover-intent or close-delay option, and open on click as well for touch and keyboard.

Check: a quick sweep across triggers moves one panel without a closed frame between them; the keyboard opens it, Escape closes it and returns focus to the trigger; collision-flipped placements keep the origin under the trigger. Under reduced motion, change position and content without sliding.

### Arrow shift button

For a call to action whose trailing arrow moves slightly on hover or focus. Move only the arrow with a transform; padding, gap or letter-spacing changes resize the button and push its neighbors.

```css
.cta-arrow {
  display: inline-block;
  transition: translate 150ms var(--ease-out);
}
@media (hover: hover) and (pointer: fine) {
  .cta:hover .cta-arrow { translate: var(--arrow-shift, 3px) 0; }
}
.cta:focus-visible .cta-arrow { translate: var(--arrow-shift, 3px) 0; }
[dir="rtl"] .cta { --arrow-shift: -3px; }
@media (prefers-reduced-motion: reduce) {
  .cta-arrow { transition: none; }
}
```

The hover rule is gated to fine pointers so a tap does not leave it stuck ([mobile web](mobile-web.md)); keyboard focus gets the same signal. In RTL the arrow glyph mirrors as the [icon rules](ui.md#icon-rendering-and-state) describe, and the shift direction follows it; when the project's icon component already mirrors directional glyphs, mirror only once.

Check: the button's width is identical at rest, on hover and on focus; after a tap on a touch device no shifted state remains; RTL points and moves the arrow toward the end edge.

### Reveal hero

For a one-time page or first-run entrance with a title, supporting text and actions, not for a surface the user opens repeatedly. The section itself stays still; the title and first paragraph share the first beat, and later gaps shrink:

```html
<section class="hero">
  <h1 style="--delay: 0ms">…</h1>
  <p style="--delay: 0ms">…</p>
  <p style="--delay: 120ms">…</p>
  <div class="hero-actions" style="--delay: 200ms">…</div>
</section>
```

```css
@media (prefers-reduced-motion: no-preference) {
  .hero > * {
    animation: hero-enter 600ms var(--ease-out) both;
    animation-delay: var(--delay, 0ms);
  }
}
@keyframes hero-enter {
  from { opacity: 0; translate: 0 10px; }
}
```

The static content is the base, and movement is added only for users without a reduced-motion preference ([accessibility](accessibility.md#motion-timing-and-reflow)). `both` holds the first keyframe during each delay so later items do not flash their final state first. Play it once on load; do not replay it as the user scrolls past.

Check: measure the time until the last action is visible (`200ms + 600ms` here) and confirm the actions respond during the entrance; with reduced motion enabled, the hero renders complete without animation.

The reveal hero recipe adapts the CSS stagger from Emil Kowalski's `choreograph` skill, and the navigation dropdown draws on its sibling-menu direction rule; see `../LICENSE.emilkowalski` and the repository's adopted-skills provenance record. The arrow shift recipe is original to this repository.
