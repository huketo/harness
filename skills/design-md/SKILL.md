---
name: design-md
description: "Create or maintain design-system documentation when the user explicitly requests a DESIGN.md, design-system brief, or documented design update from a brief, existing implementation, or supplied UI references, or asks to turn the session's design corrections into documented rules. Not for ordinary UI fixes, reviews, implementation, or runtime token definitions."
license: MIT
---

# Design-system documentation

Produce one truthful, agent-friendly design-system artifact at the repository-owned or requested location. The artifact describes the product's current system, approved intent, and open proposals; it does not replace the code, token package, component library, brand source, or asset registry that owns runtime behavior.

## 1. Confirm scope and destination

Use this workflow only when design-system documentation or a token mapping report is explicitly requested. An ordinary UI fix, implementation, or review stays in [awesome-interface](../awesome-interface/SKILL.md) and does not require a `DESIGN.md`.

Identify the product or surface, audiences, source inputs, requested output, and whether the user wants extraction, creation, maintenance, an intentional design update, rules learned from corrections, one component's entry, or a token mapping report. Inspect repository guidance and search narrowly for the existing design-system document and its inbound links.

To learn rules from the user's corrections, settle the destination here, then follow [learning from corrections](references/corrections.md) in place of sections 2–4; section 5's completion checks still apply to whatever it writes.

To report how values in an existing implementation map onto the project's own tokens, follow [the token mapping report](references/mapping-rules.md) in place of sections 2–5. That mode is read-only: it writes no file, edits no code, token definition, or artifact, and delivers its report in the reply, so the destination rules below do not apply to it.

- Honor an explicit output location.
- Otherwise update the existing repository-owned artifact in place, even when it is not named `DESIGN.md`.
- If no artifact exists, create one path consistent with repository documentation ownership. Do not create parallel root and docs copies.
- Preserve useful verified content when updating. Do not turn a small UI edit into a documentation requirement.

The destination is settled when exactly one artifact owns the requested scope and existing consumers still point to it.

## 2. Build an evidence ledger

Read the brief, relevant runtime token definitions, shared component sources, existing design documents, asset/font metadata, and supplied UI references. Follow each claimed rule to its owner rather than copying a whole stylesheet or component API into prose.

Classify every material statement:

- **Current** — extracted from current source or observed on the actual surface. Cite the owning file, symbol, URL, or supplied reference and say whether the evidence is source or visual.
- **Approved** — intended change explicitly approved in the request or an authoritative project decision, but not yet established as current implementation. Name that authority.
- **Proposed** — unresolved recommendation. Give its purpose and decision needed; wording must not imply adoption.
- **Unknown** — information the available evidence cannot establish.

Exact token values, font families, timing values, breakpoints, component behavior, licenses, and compliance claims require a source or a clearly named approved/proposed value. A screenshot can establish visible arrangement, relative emphasis, apparent color relationships, and a static state; it cannot prove token values, font identity, motion, responsive rules, interaction behavior, asset license, or accessibility compliance. Do not sample a screenshot and silently promote the result to a runtime token.

An existing document is evidence, not automatically the current runtime owner. Resolve conflicts against code and authoritative decisions, and preserve the disagreement as an unknown or proposal when it cannot be resolved.

## 3. Synthesize the artifact

Use [the artifact guide](references/artifact.md). Cover the requested system across atmosphere and audience, semantic color roles, typography and script support, spacing and layout, platform and responsiveness, components and states, motion and reduced-motion intent, asset provenance, constraints, and unknowns. A section with no evidence states the unknown instead of receiving template defaults.

Keep semantic descriptions beside traceable values. Link to the current runtime owners with paths relative to the artifact. Preserve established brands, terminology, notation, density, themes, and platform conventions unless the user has deliberately approved a change. Treat aesthetic preference as a proposal, not a defect or universal rule.

Load deeper guidance only for a domain being documented or changed:

- [colors](../awesome-interface/references/colors.md) for semantic roles, appearances, notation, gamut, and measured contrast;
- [typography](../awesome-interface/references/typography.md) for font loading, scripts, hierarchy, wrapping, and rendering;
- [layout](../awesome-interface/references/layout.md) for grouping, adaptation, directionality, and content states;
- [UI and motion](../awesome-interface/references/ui.md) for components, surfaces, icons, motion, and interaction states;
- [accessibility](../awesome-interface/references/accessibility.md) for semantics, focus, reduced motion, reflow, and evidence limits.

These references guide documentation quality; they do not authorize a redesign or a full interface audit.

To document one shared component in depth, write its entry in [the component entry format](references/component.md) and link it from the artifact's Components and states section.

## 4. Apply deliberate updates

When the request changes design intent, record the approved decision and affected roles or components without rewriting unrelated sections. Keep an approved value labeled **Approved** until its runtime owner implements it; then source evidence can promote it to **Current**. Leave alternatives labeled **Proposed** and keep the decision boundary explicit.

Update links when an owner moved. Prefer a short semantic contract plus links over duplicated token tables or component implementation details. Never introduce a second token source, component API, theme controller, schema, CLI, or publication process through the document.

## 5. Optional adapters and completion

For an explicit Stitch export or Stitch-targeted section, read [the Stitch adapter](references/stitch.md). Stitch access, an MCP call, generation, upload, and publication are separate optional actions and are not prerequisites for ordinary design-system authoring.

Before delivery, inspect the written artifact at its final path and account for every section and exact value:

1. Each statement is visibly Current, Approved, Proposed, or Unknown, with evidence at the appropriate boundary.
2. Runtime-owner and provenance links resolve from the artifact's location; the document does not claim ownership it lacks.
3. Static visual evidence and intended runtime behavior are distinguished.
4. No unsourced palette, font, spacing, breakpoint, motion, theme, image, fictional product claim, or compliance claim was added.
5. No duplicate design-system artifact was created.

Report the artifact path, whether it was created or updated, the principal sources used, and unavailable checks or unresolved decisions. Claim only the source, output, and runtime verification actually performed.
