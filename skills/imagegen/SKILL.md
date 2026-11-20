---
name: imagegen
description: "Generate inspectable design-reference images for web sections, native mobile screens and flows, responsive website comps, standalone logo concept images (wordmark, symbol, mascot, combination mark, emblem), and brand identity concept boards. Use when the deliverable is generated images: UI imagery, logo concepts, or a brand-system board. Not for generic photos, illustrations, diagrams, slide decks, arbitrary image editing, production vector assets or finished logo files, or frontend implementation."
license: MIT
---

# Image generation

Create design-reference images, inspect the actual files, and return them with a compact implementation handoff. This skill ends at images: it does not implement web, mobile, logo, font, or design-token source files.

## 1. Select the branch

| Requested artifact | Read |
| --- | --- |
| Website section, landing page, marketing/product-site comp | [Frontend common](references/frontend/common.md), then [Web](references/frontend/web.md) |
| Native iOS, Android, or cross-platform app screen/flow | [Frontend common](references/frontend/common.md), then [Mobile](references/frontend/mobile.md) |
| Responsive website shown at a phone viewport | [Frontend common](references/frontend/common.md), then [Web](references/frontend/web.md); treat it as a website, not a native app |
| Standalone logo candidates or lockup variants: wordmark, symbol, mascot, combination mark, emblem | [Logo](references/logo.md); read a style preset only when that direction is selected |
| Brand identity, application, or brand-guidelines concept board | [Brand kit](references/brandkit.md) |
| New logo development together with a brand concept board | [Logo](references/logo.md) and [Brand kit](references/brandkit.md); establish the logo direction first, then reuse it in the board |

For a combined brief, read every applicable branch and keep its outputs separately labeled. Route generic photos or illustrations to the environment's general image workflow, diagrams to a diagram workflow, and slide decks to a presentation workflow. A request outside these branches is not an imagegen task.

## 2. Establish the brief and authority

Resolve from the request and supplied material:

- artifact type, audience, purpose, content, and required count;
- target viewport, platform, orientation, and presentation context;
- owned brand assets and established product design rules to preserve;
- approved copy/assets/tokens versus proposed visual direction;
- required editable or production assets, if any, that a raster concept cannot supply.

Inspect supplied images and project design guidance before choosing a direction. Treat visual references as evidence of composition, density, color, material, and hierarchy—not as permission to copy protected marks or content. Preserve an owned brand rather than redesigning it unless redesign is explicit. Do not turn an aesthetic preference into a defect or force a stock font, palette, theme, image treatment, motion idea, or fictional product claim.

Ask only when an unresolved human-owned choice would produce materially different deliverables. Otherwise make a bounded interpretation and state it in the handoff. **Done:** branch, artifact count, preservation constraints, and known/unknown content are explicit.

## 3. Discover the real generation capability

Inspect the current tool inventory and read the selected image tool's documentation before generation. In this harness, image generation is exposed as `generate_image` through `xd://generate_image`: read that device first, then invoke it by writing only documented arguments to it. Use another environment's actual documented tool when that is what is available.

Build prompts from the brief and selected branch. Use input-image/edit capability only when the tool documents it. Do not assume a vendor, provider, seed, hidden schema, unsupported aspect ratio, exact typeface rendering, or deterministic pixel reproduction. When exact requested dimensions or formats are unsupported, use the nearest documented capability only with explicit disclosure.

If no image-generation capability is available, stop at a concise missing-capability report. Do not substitute CSS, HTML, SVG, placeholder boxes, prompt text, or a claimed artifact for generated imagery.

## 4. Generate the complete image set

Lock the approved assets and a compact visual system before the first call. Generate every required primary image, then only the detail frames justified by the branch. Keep each output's role and sequence visible in its filename or response label. Reuse supplied assets through documented input-image support when preservation depends on them.

Generated copy must stay short. Request sharp, legible, correctly spelled text when the tool supports a text field, but treat text visible in pixels as unverified until inspected. Generated UI, charts, logos, and applications are visual proposals, not evidence of implemented behavior or real data.

Do not write application code, vectorize a logo, define runtime tokens, or begin frontend/mobile implementation in this phase. **Done:** every required image exists at an inspectable artifact path, or missing generation has been reported truthfully.

## 5. Inspect and refine the actual outputs

Open every generated image at its intended viewing size. Check:

- file readability, orientation, framing, and whether the requested artifact is actually present;
- hierarchy, text legibility and spelling, content clipping, overlap, and unsafe edge placement;
- approved asset identity and placement against the supplied source;
- set-wide palette, typography mood, component/logo treatment, spacing, and image-direction consistency;
- branch-specific count, sequence, platform, safe-area, or application requirements;
- invented claims, data, endorsements, controls, or production assets that could mislead a downstream implementer.

A successful tool response is not visual approval. Regenerate the affected image when a visible failure undermines the reference. If a documented tool cannot preserve an asset or render required text reliably, identify that limitation and do not label the result approved. **Done:** all delivered files were actually inspected and any remaining limitation is named.

## 6. Deliver images and handoff

Return:

1. each artifact path and label;
2. whether it is a **primary** image or an optional **detail** frame;
3. section/screen/logo/board role, viewport or intended application size, platform, and sequence where relevant;
4. what is **approved/preserved** versus **proposed**;
5. known copy, tokens, and supplied assets used;
6. unknown behavior, uncertain pixel text, unsupported dimensions/formats, or production assets not delivered;
7. exact inspection performed and any unresolved visible issue.

The handoff may live in the response or an existing project brief; do not create a manifest merely to repeat it. Images are implementation references, not runtime specifications. Keep the imagegen/code boundary explicit so a later implementation phase can resolve behavior and accessibility from real product requirements.