# Accessibility

Build on platform behavior: native semantics, predictable keyboard interaction, perceivable state and recoverable errors. Apply these rules to the requested flow, including its unavailable, loading and failure states. Keep the project's components, styling system and verified tokens.

This domain owns semantics, focus, keyboard, forms, announcements, target boundaries, reduced motion and accessible reflow. For measured color contrast use [colors.md](colors.md); for text sizing use [typography.md](typography.md); for spatial adaptation use [layout.md](layout.md); for message wording use [writing.md](writing.md). Motion polish belongs to [ui.md](ui.md). Review ranking and reporting belong to [review.md](review.md).

## Start with the interaction contract

Identify what each control does, its accessible name, its state and the complete keyboard path. Prefer the project's existing accessible primitive over a custom rebuild. A role promises behavior; adding ARIA alone does not implement it.

- Use `<button>` for actions and `<a href>` for navigation. Real links retain copy-link, context-menu, Cmd/Ctrl-click and middle-click behavior. Set button types deliberately inside forms.
- Use native inputs, selects and disclosure elements when they fit. A custom control needs the matching keyboard model, focus handling, role and state, not just a click handler.
- Prefer names from visible text or `aria-labelledby`. Use `aria-label` for genuinely icon-only controls and hide their decorative icons from assistive technology. Include the visible label in the accessible name so speech commands match what people see.
- Keep referenced IDs present and unique. `aria-labelledby` overrides `aria-label`, which can override native naming; inspect the computed name rather than assuming visible text wins.
- Avoid redundant roles on native controls. Site navigation is a navigation landmark with links, not an application `menu` unless it implements that interaction model.
- Never put `aria-hidden="true"` or presentation semantics on a focusable control or an ancestor containing one. To hide interactive content, remove both its exposure and its focusability; `inert` is useful for inactive regions.

Use one visible primary `<main>`, meaningful landmarks and a coherent heading hierarchy. Distinguish repeated navigation landmarks with labels. Choose heading levels by structure, then style them; a heading-count convention alone is not evidence of a WCAG failure. Set the page title to the current context, most specific information first.

## Keyboard and focus

Walk the task with Tab and Shift+Tab before treating it as operable. Every pointer action needs a keyboard equivalent, including revealing hidden controls, selecting items, dismissing overlays and recovering from errors.

Preserve the browser focus indicator when possible. If styling it, use `:focus-visible` and a verified project token; removing the outline requires an equally perceivable replacement. Check the entire indicator against the surfaces it crosses, including selected states, images and sticky chrome. A familiar color or `currentColor` is not proof of contrast. Retain system color adjustment in forced-colors mode; verify any intentional override. `:focus-within` may emphasize a group but does not replace identifying the focused control.

- Let DOM order define the natural Tab sequence. Use `tabindex="0"` for a necessary custom interactive stop and `-1` for programmatic focus. Fix source order rather than introducing positive tabindex.
- Provide a first-focusable skip link when repeated chrome precedes the main content. Reveal it on focus, make its destination usable and offset anchor scrolling for sticky headers.
- Composite widgets generally occupy one Tab stop. Use the established primitive or the appropriate ARIA Authoring Practices pattern; roving tabindex gives the active member `0` and others `-1`. Do not apply one generic arrow handler to every widget.

| Widget | Expected interaction |
| --- | --- |
| Button / link | Buttons activate with Enter and Space; links with Enter, retaining native navigation behavior |
| Tabs | Orientation-appropriate arrows move among tabs; Tab leaves the tab list; Home/End where supported by the pattern. Automatic activation suits instant panels; manual Enter/Space activation avoids triggering expensive changes on focus |
| Menu button | Enter/Space opens; arrow entry and navigation follow the menu pattern; Escape closes and restores trigger focus |
| Disclosure | A button exposes `aria-expanded`; Enter/Space toggles its associated region |
| Combobox | Typing, list navigation, acceptance and Escape follow the specific editable or select-only pattern; preserve native text-editing keys |
| Listbox / radio group | Arrow movement and selection follow the chosen single- or multi-select pattern; do not turn every item into an unrelated Tab stop |

Escape dismisses the innermost dismissible layer first. Native form Enter behavior should work without a pointer. Keep Enter as a newline in a textarea; offer a documented Ctrl/Cmd+Enter submit shortcut only when the product supports it.

### Dialogs and route changes

Prefer native `<dialog>` opened with `showModal()` or an established accessible dialog primitive. A custom modal needs a name, dialog semantics, a truly inert background and focus containment; `aria-modal="true"` alone supplies none of those behaviors.

On open, choose an initial focus target suited to the task: a first relevant control, a static heading for long structured content, or the least destructive action for an irreversible confirmation. Keep Tab and Shift+Tab inside the modal and provide a keyboard-reachable close path. On close, restore focus to its trigger, or a logical successor when that trigger no longer exists. Keep the dialog outside any ancestor made inert. Contain scroll chaining on its scrollable region and verify background scrolling separately.

For client-side navigation, update the document title and place focus in the new view when navigation changes context. Preserve expected history scroll restoration and distinguish new navigation from back/forward traversal. Do not steal focus for background refreshes or ordinary status updates.

## Forms and recovery

Give every field a persistent visible label, programmatically associated by `for`/`id` or a wrapping label. A placeholder is an example, not the label. Make checkbox/radio text part of the same activation target. Group related choices with native group semantics and a legend where appropriate. Explain required indicators and use native `required` where applicable.

Use a real form, meaningful field names and appropriate autocomplete tokens for recognized personal-data purposes. Match `type` and `inputmode` to the data rather than its appearance:

| Data | Starting choice |
| --- | --- |
| Email, URL, phone | `email`, `url`, `tel` input types with corresponding autocomplete |
| Password | `password`, with `current-password` or `new-password` autocomplete |
| One-time code | Text input, numeric input mode when appropriate, `one-time-code` autocomplete |
| Card number, PIN, postal identifier | Text semantics; numeric input mode only when the accepted format is numeric |
| Actual numeric quantity | Number input when stepping and numeric semantics are useful |
| Locale-sensitive decimal amount | Input mode and parsing consistent with the product's accepted localized format |

Preserve paste, password managers, autofill and text expansion. Avoid keystroke filtering that silently drops valid input or interferes with composition. Normalize only what the field contract permits; trimming incidental whitespace can help ordinary fields but must not silently alter passwords or meaningful text.

Let users submit an incomplete form so validation can explain what is needed. Prefer validation on submit, with subsequent feedback that helps correction rather than scolding during initial entry. A disabled-until-valid submit leaves no recovery path.

For field errors:

1. Preserve entered values and display the error beside the field.
2. Set `aria-invalid="true"` and connect the error with `aria-describedby`, retaining any useful hint IDs.
3. On failed submission, focus the first invalid field or a navigable error summary appropriate to a long form.
4. Remove stale invalid state and error references when corrected.

```html
<label for="email">Email</label>
<input id="email" name="email" type="email" autocomplete="email"
       aria-invalid="true" aria-describedby="email-error">
<p id="email-error">Enter a valid email address.</p>
```

During submission, prevent duplicate requests and keep a meaningful action label beside any progress indicator. Re-enable the action after a recoverable failure. Preserve input and focus across re-renders and hydration; protect unsaved work at navigation boundaries where the product requires it. Error text must agree with actual validation and available recovery, as covered in [writing.md](writing.md).

### Unavailable controls

Native `disabled` supplies disabled behavior, removes controls from the Tab sequence and excludes disabled fields from form submission. Use it for genuinely unavailable native controls, including temporary duplicate-submission prevention where appropriate. Put the reason in reachable visible text rather than only in a tooltip on a disabled element.

Use `aria-disabled="true"` when discoverability in the focus sequence is intentional or the control is custom. It only announces state: suppress pointer, keyboard and applicable form activation yourself, style the state and explain the reason. Do not combine both attributes redundantly. An unavailable appearance is not an activation guard.

## Announcements and alternatives

Choose the smallest mechanism that conveys the update without duplicate speech:

| Situation | Mechanism |
| --- | --- |
| Focus already moves to the new context | Let its name, role and description announce it |
| Information belongs to a field | Connect it with `aria-describedby`; verify any needed announcement while focus stays put |
| Non-urgent background update, saved state or result count | Stable `role="status"` region with concise text |
| Urgent error not conveyed by a field or focus move | `role="alert"`, used sparingly |

Render a stable empty polite region before updating its text; inserting an already-filled region is inconsistently announced. Repeated updates and dynamically inserted alerts need testing on the target browser/screen-reader combinations. Mark a region busy during updates when useful, clear `aria-busy` on completion and announce the outcome rather than every intermediate mutation. Do not move focus to routine toasts.

Reuse the project's visually-hidden utility for text that must remain in the accessibility tree. A conventional clipped one-pixel box works; `display: none`, `visibility: hidden` and zero-size shortcuts do not serve the same purpose. Keep focusable hidden links revealable on focus.

Choose image alternatives by purpose:

- Decorative or redundant image: explicit `alt=""`.
- Informative image: the meaning it contributes, not a filename or inventory of shapes.
- Image acting as a control: action or destination in the control's name.
- Image of text: equivalent text; prefer actual text when possible.
- Complex chart or diagram: concise summary plus accessible detailed data or explanation nearby.

For meaningful inline SVG, use image semantics and a name through `aria-label` or a referenced `<title>`; hide decorative SVG. Provide captions for relevant prerecorded video and transcripts for audio, plus an alternative for essential visual information not conveyed by audio. Keep media controls available and avoid autoplay with sound.

## Pointer and touch boundaries

Measure the interactive area, not just the icon. WCAG 2.2 SC 2.5.8 Level AA uses a 24 by 24 CSS-pixel target or a qualifying spacing, equivalent-control, inline, user-agent or essential exception. Check the applicable exception before calling a smaller control a failure. Under the spacing exception, a 24 CSS-pixel circle centered on an undersized target must not intersect another target or another undersized target's corresponding circle.

Larger targets improve touch usability: roughly 44 CSS pixels is a useful web touch target, while dense desktop controls may use the project's smaller proven scale. These are not interchangeable with native-platform point/dp guidance or universal conformance thresholds.

Prefer real padding or minimum box dimensions; they give scrolling and gestures accurate geometry. If the visible shape must stay small, extend the target on its button or wrapping label with a pseudo-element, not on a replaced input. Check neighboring controls and stacking: expanded areas must not overlap or create dead zones. Give purely decorative overlays `pointer-events: none`; a dismissing scrim is interactive, not decoration.

Gate hover-only treatments with hover capability and keep the underlying action available on touch and keyboard. Retain pinch zoom and page scrolling. Scope any custom `touch-action` restriction to the gesture surface that needs it; provide alternatives to precise dragging or path gestures. If overriding the tap highlight, preserve perceivable activation feedback.

## Motion, timing and reflow

Reduced motion must retain information and usable completion states. Prefer a static base with optional movement under `prefers-reduced-motion: no-preference`, or use the project's equivalent preference handling. Remove parallax, large spatial motion and unnecessary looping; use instant changes or restrained opacity feedback where appropriate. Do not depend solely on animation-end events to complete essential state changes: test the reduced/static path rather than applying a global near-zero-duration workaround blindly.

Provide pause/stop/hide controls for automatically moving, blinking or scrolling content covered by WCAG 2.2.2, including content running for more than five seconds alongside other content unless essential. Assess auto-updating content under its applicable conditions too. Prefer carousels paused under reduced motion. Movement is never the only state cue.

Keep errors, necessary information and actionable toasts available until dismissed or provide an equally reachable persistent location. A fixed timeout is not proof that everyone can read or act; use timing adjustment and pause behavior where a timed interaction is necessary. Never make a disappearing toast the only route to undo.

Verify text resizing to 200% without lost content or functionality. Verify reflow at 320 CSS pixels wide, equivalent to a 1280 CSS-pixel viewport at 400% zoom, with vertical rather than page-wide two-dimensional scrolling. Genuine two-dimensional content such as a data table or map may need a contained scroll region; do not exempt whole pages or ordinary prose. Keep user zoom enabled and allow text containers to grow instead of clipping at fixed heights. Preserve established units while fixing the actual reflow failure.

## Verification evidence

Source inspection can establish native tags, associated labels, existing referenced IDs, focus styles, handler paths and preference guards. It cannot prove rendered focus visibility, computed names, touch collision, reflow or spoken output.

For the requested flow, exercise keyboard entry through completion and error recovery, every focus stop, nested overlay dismissal and restoration. Inspect computed names, roles and states in the accessibility tree. Check forced colors, reduced motion, text resize, narrow reflow and target boundaries in the rendered interface. Test actual screen-reader announcements when that capability is available; an accessibility-tree snapshot is not a screen-reader run. An automated audit supplements these walks but does not establish full conformance. Record unperformed checks and their limits explicitly.
