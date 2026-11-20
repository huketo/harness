# Redesign without losing the product

Use for an explicitly requested redesign of an existing interface. A read-only review remains a review; a focused improvement remains focused. Reuse the existing framework, components, tokens, and domain references rather than installing a new design system by default.

## Set the change boundary

Inspect the current rendered surface and the owning source before proposing replacements. Record a concise working distinction:

| Area | Preserve unless the request authorizes change |
| --- | --- |
| Identity | Brand name, owned logo, approved assets, color and typography commitments |
| Information architecture | Existing destinations, navigation meaning, URL structure, content hierarchy needed for task completion |
| Behavior | Actions, validation, state transitions, keyboard operation, integrations, analytics hooks |
| Content and obligations | Real claims, prices, dates, legal notices, consent behavior, source data |
| Operations | Supported platforms, responsive breakpoints, dependencies, deployment and publication boundaries |

Choose the authorized mode:

- **Preserve and improve:** repair hierarchy, spacing, readability, consistency, feedback, and responsive behavior inside the existing identity and architecture. This is the conservative interpretation of “make it better.”
- **Visual overhaul:** change the authorized visual language while retaining working destinations, content, and interactions. A visual redesign alone does not authorize brand replacement or data changes.
- **Structural redesign:** change navigation, content organization, or flow only where explicitly in scope. Identify affected destinations and transitions, migrate their consumers, and verify old required tasks remain reachable.

For missing runtime access, distinguish source findings from unverified visual hypotheses. Do not claim to have audited states or screens that were not inspected.

## Diagnose before decorating

Start with failures that block or mislead users, then scan hierarchy, reading order, grouping, copy, typography, semantic colors, and polish. Prioritize by user impact, evidence, and requested scope, not by a universal “swap fonts first” recipe.

Useful checks include:

- Can users identify the primary task and distinguish actions from static labels?
- Does repeated content use consistent structure, alignment, spacing, and action placement without hiding important differences?
- Do headings, descriptions, and controls align optically and wrap with real content?
- Do labels name the actual action, and do empty/error states provide a truthful next step?
- Do borders, shadows, imagery, and color roles clarify groups or compete for attention?
- Do responsive changes preserve reading order, functionality, and deliberate information density?

Apply the relevant domain reference for a confirmed issue. Do not fabricate social proof, replace factual copy with impressive numbers, remove required density, or delete useful affordances to make a screenshot cleaner. A stylistic preference is not a defect.

## Change and verify in coherent slices

Capture the affected views before changing them, and the same surfaces, states, widths and themes after each slice. For a locally served web build, use capture.mjs `--kind before` and `--kind after` and compare with pixdiff as [capture and compare](review.md#capture-and-compare) describes. Each changed region belongs to the slice; a region outside it is an unexplained difference and a finding, and often marks a preserved area the slice touched. Implement the smallest coherent slice that serves the redesign, preserving existing components and data contracts. Use existing fixtures or synthetic content rather than changing production records to preview states.

For a visual overhaul, use [art direction](art-direction.md) only where the new visual language needs a decision. Do not generate multiple alternatives, a brand board, screenshots, or DESIGN.md by default. A requested comparison uses the main skill's alternatives workflow and retains the original until selection.

Exercise the primary task after the change, along with affected links, controls, responsive arrangements, and relevant loading/empty/error states. Verify preserved behavior as well as the new appearance. Report the redesign boundary, exact checks, and remaining unknowns; do not claim an untouched product-wide audit.

Adapted selectively from Leonxlnx/taste-skill and redesign-skill; see `../LICENSE.taste-skill` and the repository's adopted-skills provenance record.
