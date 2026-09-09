# Verification

Use this reference after a deck runs and before delivery. Verification means exercising the actual presentation and each requested output, not inferring quality from source, a successful build, or one representative screenshot.

Use available built-in tools and browser capabilities. Adapt to the project's existing preview and export mechanisms. Do not require a fixed port, a particular browser product, a permanently running server, or new test infrastructure solely to perform this pass.

## Define the observable contract

Derive the check from the requested use:

- a speaker-led deck must present every planned state, preserve navigation and notes, and remain legible on its stage;
- a self-contained reading artifact must retain the context, captions, sources, and detail needed without narration;
- an offline package must operate without network access after all required files are present;
- a PDF or PPTX request is complete only when that exported file exists and has been inspected;
- a sample source or export command is not the requested deliverable unless the user asked only for a sample or instructions.

Record the engine, preview route, requested artifacts, supported presentation size, click/export policy, language, and offline or privacy requirements. Use that scope to decide states and outputs; do not invent fixed counts, type sizes, or density limits.

## Exercise the live deck

Open the real deck in an available browser and inspect every slide. Navigate through the same controls a presenter will use rather than visiting only generated thumbnails.

Isolate each deck's browser context or origin when comparing samples. Presentation frameworks can synchronize navigation through same-origin storage or broadcast channels; separate file paths alone do not isolate them.

Wait for the active slide and its transition to finish before capturing settled content. A mounted element with nonzero bounds may still be transparent or covered by the outgoing slide. Likewise, inspect a toggle's current state before activating it: a responsive layout may already have entered reading mode.

For slides with progressive disclosure, tabs, toggles, accordions, demos, animation-driven states, or other meaningful interaction, inspect every state that changes what the audience can learn. At minimum, include the initial and final states plus each intermediate state that adds, removes, reorders, or qualifies evidence. Decorative transitions with the same settled content do not create a new semantic state.

At each observed state, confirm:

- the intended title, evidence, labels, caption, source, and current-state cue are present;
- nothing meaningful overlaps, clips, escapes the stage, or sits behind another layer;
- hidden future content is actually hidden and revealed content is fully visible;
- backgrounds, text, code, charts, diagrams, images, and video posters render as intended;
- the layout remains stable after fonts and media finish loading.

A screenshot can establish a visual state, not keyboard behavior or media readiness. Use rendered inspection, element bounds, computed state, console/network evidence, and interaction as appropriate to the question.

Review composition separately from functional integrity. A deck can pass every overflow, navigation, and numerical check while still being visually unacceptable. At full-slide size, judge phrase-level line breaks, hierarchy, proximity within groups, space between groups, optical placement, and the purpose of each decorative mark. Then use a contact sheet to inspect repetitive scaffolds and pacing across the deck. When the user supplied visual references, compare actual rendered examples side by side; reading their design prose is not that comparison. Do not report a functional assertion score as aesthetic approval or recommend a rejected sample as a template.

## Wait for fonts and media

Do not capture or approve a slide while it is still using a temporary font or unresolved asset. Wait for the document's font readiness mechanism when available, and confirm that the rendered faces cover Korean/CJK glyphs, mixed identifiers, symbols, code, and every used weight. Inspect fallback behavior when a required face is unavailable or offline.

For images, audio, and video, distinguish a requested lazy state from a failed load. Confirm intrinsic dimensions and completion or error state where the browser exposes them. Exercise the meaningful media controls and verify the intended poster or static replacement independently of successful playback.

Treat a successful network response as evidence of transfer only. It does not prove that the correct font, image, frame, caption, or media track is visible.

## Detect loss, overlap, and masking

Inspect both container overflow and spatial collisions. `scrollHeight` or `scrollWidth` can expose some overflow but cannot prove that neighboring panels, absolute elements, transforms, or overlays do not collide. Compare meaningful element bounds and visually inspect complex compositions.

Required content must remain visible and reachable. Fix the owning layout or split the content when it does not fit. Never approve a defect because global scaling, `overflow: hidden`, a crop, a mask, or a clamp made the missing content invisible.

Do not misclassify intentional fixed-stage clipping. It is acceptable for a background bleed, decorative off-canvas element, or frame-filling media to clip at the 16:9 stage boundary when the clipped area carries no meaning and the supported live and exported results match the design. Record the distinction whenever a clipping rule is material to approval.

## Walk keyboard, focus, links, and notes

Run the complete presentation path with the keyboard used by the engine. Confirm forward and backward navigation, meaningful click progression, and any direct slide or overview controls the presentation relies on. Interaction must not trap focus or steal editing keys from an active control.

For every interactive element in scope:

- reach it in a coherent focus order;
- observe a visible focus indicator on its actual background;
- operate it with the expected keyboard input;
- confirm its state is exposed without color alone;
- dismiss or reverse it and verify focus returns sensibly.

Open each audience-facing link and verify the intended destination, including fragments and local assets. Treat QR codes as links with a second representation: decode or follow the encoded target rather than approving their appearance alone.

Inspect speaker notes through the actual presenter or exported-notes path when notes are part of the request. Confirm slide association, ordering, transitions, timing cues, and privacy. A source comment does not prove the presenter can see a note, and a note visible in presenter mode may still be omitted from or exposed by an export.

## Prove offline behavior only when required

Package the deck according to its documented offline use. Open the final artifact in a fresh browser context with network access disabled before navigation, then exercise the required presentation and media states. A warm cache or an already loaded tab does not establish offline portability. Inspect requests and failures: fonts, images, scripts, styles, embeds, analytics, and media must resolve locally or have an explicitly accepted offline replacement.

A single HTML file can still make remote requests; a successful online rehearsal does not prove offline operation. Conversely, do not impose offline packaging or a network audit when the request permits network dependencies.

## Inspect exported PDF

Generate the actual PDF using the deck's supported export path and the requested click-state policy. Open the exported file, inspect every page, and compare its order and content with the live semantic states it is meant to represent.

Confirm page size and orientation, font rendering, images, transparency, code, charts, links when required, speaker notes policy, selectable/searchable text expectations, and the absence of unexpected blank or duplicate pages. Check that captions and sources remain attached to their evidence.

For video or interactive content, verify a deliberate poster, summary, or final state on the relevant PDF page. A blank player, control chrome, or arbitrary captured frame is not an adequate static substitute when the media carries evidence.

Report when a PDF is image-based. Do not claim selectable text, accessible reading order, or searchable content unless the actual file demonstrates it.

## Inspect exported PPTX

Identify the requested PPTX contract before approval:

- **Native-editable PPTX** uses editable PowerPoint text, shapes, charts, tables, and notes where those objects are expected. Open it in an available compatible editor and modify representative text and structured objects to confirm editability and layout stability.
- **Image-based PPTX** places rendered slide images into PowerPoint pages. It may satisfy projection or handoff needs but does not make slide text, charts, or layout natively editable. Inspect image fit, resolution, page order, notes transfer, and any links, then label the limitation explicitly.

Never describe image-based export as native editing. If native editing was requested, an image deck is a failed deliverable rather than a close substitute. If the target editor is unavailable, report compatibility and editability as unverified; file creation alone is not proof.

For either form, inspect every slide in the actual file. Check page geometry, font substitution, text and object overflow, cropping, layering, transparency, equations, media placeholders, notes, and static alternatives. Confirm that embedded fonts and media comply with their licenses and the requested distribution model.

## Review privacy and provenance

Inspect visible slides, notes, source maps when shipped, file properties, embedded media, screenshots, links, QR targets, and exported metadata for confidential names, tokens, internal hosts, personal data, unreleased figures, or comments that should not leave the intended audience.

Verify that external claims, charts, images, icons, fonts, datasets, quotations, and demos have the necessary source cue and allowed use. Distinguish measured data, user-provided material, synthetic examples, reenactments, and projections wherever confusing them would alter the conclusion. Public availability does not establish redistribution rights.

## Repair and recheck the same state

When a defect appears, correct the owning source or asset. Then reproduce the same slide, click state, viewport, preference, network condition, or exported page that exposed it. A different slide or a fresh build alone does not close the finding.

After the targeted recheck passes, inspect affected neighboring states and regenerate any deliverable derived from the changed source. Do not approve a stale PDF or PPTX because the live deck is now correct.

## Report evidence honestly

Report what was observed with enough precision to reproduce it:

- live deck and browser/runtime used;
- slide numbers or routes and semantic click states exercised;
- stage sizes, reading widths, language/font states, and reduced-motion mode checked;
- keyboard, focus, links, notes, media, offline, privacy, and provenance checks actually performed;
- each exported file opened, its page/slide coverage, click policy, and whether text and objects were native or image-based;
- defects fixed and the exact same-state recheck result;
- unavailable editors, devices, browsers, screen readers, projector conditions, or other unobserved environments.

Scope the conclusion to that evidence. Source inspection is not a visual pass; one screenshot is not all-slide coverage; an accessibility tree is not a screen-reader session; and a generated file is not an inspected export. State remaining uncertainty instead of inventing successful observation.