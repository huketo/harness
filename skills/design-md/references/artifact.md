# Design-system artifact guide

Use this structure as a coverage guide, not a fill-in-the-blanks generator. Keep established headings when updating an existing document. Omit an inapplicable subsection; when a required system area matters but evidence is absent, record it as **Unknown**. Do not invent values to make a table look complete.

## Evidence notation

Label entries inline so agents can distinguish reality from intent:

- **Current** — current implementation or observed surface, followed by its source.
- **Approved** — authorized intended change, followed by the approving brief or decision.
- **Proposed** — unresolved option, its rationale, and the decision required.
- **Unknown** — missing evidence and what would resolve it.

Prefer repository-relative links to owners. Add a symbol, token name, or stable section anchor when useful. Line numbers may supplement a link, but should not be the only locator.

For repeated structured data, use a table such as:

```markdown
| Status | Role | Description or value | Owner / evidence |
| --- | --- | --- | --- |
| Current | Text / primary | `var(--color-text-primary)` → `#17202a` | [`tokens.css`](relative/path/tokens.css), `--color-text-primary` |
| Approved | Focus indicator | Use the approved focus role after its runtime change lands | Product accessibility brief, “Focus states” |
| Unknown | Disabled text | Effective value over translucent surfaces is not established | Inspect computed style in each supported appearance |
```

The example demonstrates notation only. Copy none of its values or decisions unless they belong to the target project.

## Recommended structure

```markdown
# Design system: <product or bounded surface>

## Scope and evidence
## Audience, tasks, and atmosphere
## Color roles and appearances
## Typography and language support
## Spacing, layout, and responsiveness
## Components and states
## Motion and reduced motion
## Assets and provenance
## Approved changes and open proposals
## Constraints and unknowns
```

### Scope and evidence

Name the surfaces, platforms, appearances, and locales covered. List the authoritative implementation owners, decisions, briefs, and supplied references. State important exclusions and evidence limitations. If this document covers only one product area, do not imply organization-wide authority.

### Audience, tasks, and atmosphere

Describe the intended audience, primary tasks, product voice, desired atmosphere, and functional density. Tie aesthetic language to the brief or visible system. Explain how hierarchy supports work rather than assigning generic creativity, variance, or luxury scores. Preserve established brand character; proposals for a different direction remain proposals.

### Color roles and appearances

Document consumed semantic roles: canvas and surfaces, text, borders, focus, actions, selection, status, data visualization, and disabled states that the product actually uses. For each role, identify supported appearances and runtime owner. Exact values and mappings come from token source or a named approved/proposed decision.

Keep existing notation and theme mechanism. Record measured contrast only with the pair, state, appearance, method, and applicable criterion; otherwise say it was not measured. A screenshot supports qualitative relationships, not declared values or conformance.

### Typography and language support

Document role-based styles and their runtime owners: display, heading, body, label, caption, code, and numeric data as applicable. Include the actual family or stack, available faces/axes, sizes, weights, line heights, tracking, and fallbacks only when sourced.

Name required scripts, locales, directionality, numeral behavior, and fallback coverage. Link font files or loading configuration and record license/provenance when known. A font's appearance in a screenshot does not identify the family, supported glyphs, webfont format, or license.

### Spacing, layout, and responsiveness

Describe the spacing scale or layout primitives actually consumed, content hierarchy, grids or flow, containment, density, directionality, and supported platforms. Record breakpoints, container thresholds, safe-area handling, viewport behavior, and adaptation rules only from source or approved intent. Distinguish observed behavior at a tested size from a universal responsive rule.

Include populated, empty, loading, error, partial-data, and unusually long-content arrangements when the system defines them. Link to the layout primitives or owning components instead of reproducing their implementation.

### Components and states

List shared component owners and the semantic contract for components in scope. Cover applicable default, hover, focus, pressed, selected, disabled, loading, success, error, empty, and open/closed states. Include content and accessibility semantics when they are part of the established design contract.

Describe shape, surface, icon, and feedback behavior with source-backed tokens. Keep local exceptions explicit. A static reference proves only the state shown; keyboard behavior, state transitions, data behavior, and recovery paths require implementation or runtime evidence.

An in-depth entry for one component follows [the component entry format](component.md); link it from this section instead of repeating its contents.

### Motion and reduced motion

Separate three evidence layers:

1. **Current runtime** — implemented trigger, duration or physics, properties, interruption behavior, and owner.
2. **Approved runtime intent** — behavior authorized but not yet implemented.
3. **Static composition** — spatial cues visible in a still reference, with motion left Unknown.

Describe what information motion communicates and the final state when decorative motion is reduced. Cite the existing reduced-motion mechanism. Exact timing, easing, performance, and reduced-motion behavior require source or runtime evidence; a still image proves none of them.

### Assets and provenance

Inventory material logos, icons, illustrations, photography, generated images, and fonts. For each, name purpose, owner or path, source, license or usage restriction when known, and any approved transformation. Preserve brand marks and existing icon systems. Mark missing provenance rather than guessing or substituting a convenient asset.

### Approved changes and open proposals

Summarize deliberate updates with status, authority, affected runtime owners, migration state, and verification needed before becoming Current. Keep unresolved alternatives under Proposed with a decision question. This section is an index; domain sections remain the semantic home of each rule.

### Constraints and unknowns

Record supported and unsupported platforms, localization or content constraints, technical dependencies, brand restrictions, and evidence gaps. Phrase compliance as scoped evidence, not a whole-product guarantee. For each consequential unknown, name the source or observation that could resolve it.

## Completion review

Read the final artifact as an implementation agent would. It is complete when the agent can locate the runtime owners, tell current behavior from intended change, identify unresolved decisions, and avoid inventing missing details. Remove duplicated implementation data, aesthetic bans not owned by the project, and sections that merely restate the template.
