# Component entry format

Use this format when the user asks to document one shared component in depth: "document the Button", "what states does Select have", usage rules for a new or changed component. The entry is built only from what the component's sources say. It does not judge the design, change the component, or publish anything. Foundations and pages that span several components belong in the design-system artifact itself ([artifact guide](artifact.md)).

## Destination and evidence

Prefer the repository's existing component-documentation location; otherwise put the entry where documentation ownership puts it. When a design-system artifact exists, link the entry from its Components and states section, so one place owns each component's contract. When none exists, the entry stands on its own and the link waits until an artifact is requested.

The entry uses the artifact's evidence notation:

- A fact read from the component's code, props type, styles, stories, or a real call site is **Current**. The Sources list after the entry names each source, so a Current line needs no inline label.
- A planned use or behavior with a named authority is **Approved**; mark it inline.
- A recommendation the sources do not settle is **Proposed**; mark it inline with the decision needed.
- A section or fact the sources cannot establish is **Unknown**; write `Unknown: <what would resolve it>`. A section that does not apply reads `Not applicable: <reason>`.

Never write a variant, prop, state, token name, example, or use without a listed source, and never invent a state or a precedence order to fill a section.

## Steps

1. Paste the nine headings below into the draft, empty.
2. Read the component's code, props type, styles, and stories, and record each as a Sources line.
3. Find two real uses by call-site search or from the request. With one real use, mark the section that rests on it "single use"; with none, see Stops.
4. Trace which source gave each example, variant, prop, state, and token. Every disagreement between sources is a line under Conflicts, with the quoted project rule that settles it, or "no rule, not chosen".
5. Fill each section from sourced facts, copying token names and example code character for character.
6. Write Usage rules last, in the rule shape below. Cut any rule you cannot break with a real snippet.
7. Fill Guessed at, one line per judgment call, then reread the draft against Done.

## Headings, in order

Every entry uses these nine H2s. Usage holds six fixed H3s, Examples holds `### Example files`, Variants holds one H3 per axis named after its prop, and Description may hold `### Parts`. Keep project headings when updating an existing entry that already uses another order.

1. `## Description`
2. `## Examples`
3. `## Variants`
4. `## States`
5. `## Props`
6. `## Usage`: `### When to use`, `### When not to use`, `### Rules`, `### Content`, `### Agent defaults`, `### Limits`
7. `## Accessibility`
8. `## Tokens`
9. `## Related`

## What goes in each

**Description.** One sentence on the job the component does, not how it looks. Under it, one plain line with the import, whether it runs on the client or the server, the source path, and its registry status (`Unknown` when the repository has no registry). A part also used on its own gets `### Parts`; a compound component (`Tabs` with `Tab`) is one entry.

**Examples.** The default example first, copied verbatim from a story or example file, with its path above it. With none, use the most common real call site, simplified by dropping unrelated props and nothing else, and write `simplified from <path>`. Then `### Example files`: a table of file, what it covers, and caption, for the default, each variant value and state that looks or behaves differently, and one composition inside a parent. List a missing example as `Unknown: no example for <variant or state>`; this skill does not write example code.

**Variants.** One H3 per axis, one line per value with the job it covers. When two values cover the same job, say so. A props type with no variant prop reads `None.` with the reason.

**States.** One line per state that exists, saying what the user can do in it. Check default, hover, focus, pressed, selected, disabled, loading, and error, and drop the ones the component lacks. A state whose only cue is visual names the cue. State precedence goes here when states can overlap. A static story proves only the state it shows; transitions and keyboard behavior need code or runtime evidence.

**Props.** From code only: name, type, default, and when to change it. `Unknown: no props type was read` when none was found.

**Usage.** Rules a designer or agent follows before reaching for the component.

- *When to use, When not to use.* Two to four lines each, each a situation the designer is in, not a property of the component. Each "when not" names the other component to use instead.
- *Rules.* States over time, input methods, focus, feedback, composition, placement, density.
- *Content.* Rules per copy slot: casing, template, length, forbidden words.
- *Agent defaults.* What an agent writes by default that this project does not, taken from a comparison that already exists (a review note, an eval result, or a recorded diff of agent code against the call sites), cited by path. Without one, write `Unknown: not compared`.
- *Limits.* A number set below a measured break, with the measurement's path, or `Unknown: not measured` and what to measure.

**Accessibility.** The native element or primitive it rests on, its role, the keys that operate it, where focus goes afterwards, and the accessible name in every variant. Say which facts came from code and which from a rendered story; neither establishes conformance for the whole product.

**Tokens.** Token names grouped by what they control, spelled as the source spells them, read from named references in the styles and never inferred from a raw value. A raw value in the styles is listed as such; [the token mapping report](mapping-rules.md) can classify it on request.

**Related.** Components people confuse with this one, each with when to pick it instead.

## Rule shape

```
- `rule/<component>-<slug>`: When <condition>, <action> instead of <alternative>, because <reason>. Evidence: <ground>. Check: <lint | test | probe | review> <what runs>.
  - Don't: <one line of real code that breaks it>
  - Do: <the fix>
```

Evidence is two call sites, a measurement with its path, a named project principle, or the user's words. A rule resting on the user's words alone is **Approved** with that authority named. Before keeping a rule, write the violating snippet and confirm the named check or a reviewer would catch it, negate the rule and sharpen it if the opposite sounds just as reasonable, and sweep every call site: each follows it or is a listed exception.

A behavior that looks like a bug is written as it is, followed by a `Defect:` line addressed to the owner with what goes wrong for the user and the smallest fix. The entry does not fix it.

## After the entry

Add Sources, Conflicts, and Guessed at after the nine sections, and Gates (a question with its default) only where a rule adds one. Report the entry's path, what it covers, which sections are Unknown, up to three questions with defaults, and one prompt the user can paste to take the next step. Take counts in the report from the saved file (for example `grep -o`), not from memory.

## Stops

| Missing after searching | Why it stops |
| --- | --- |
| The component's code | Nothing else sources the variants, props, or behavior |
| The variant list (props type or stories) | A guessed list documents a different component |
| Any use, real or planned | Invented uses read like real ones, and readers copy them first |

One real use, Approved planned uses, and a deprecated predecessor are marked as such rather than stopping the run. A stopped run returns the stop, the facts sourced so far by section, and the smallest reply that unblocks it, such as "Name one screen that renders the component and which variant it shows."

## Worked example

A segmented control from a fictional budgeting app, Lumen Ledger, cut to the parts that teach most. Its paths, names, and call sites are invented for this example.

````markdown
## Description
SegmentedControl switches between two to four views of the same data without leaving the screen.

`import { SegmentedControl } from "@/ui/segmented-control"`, client only, `src/ui/segmented-control/SegmentedControl.tsx`, registry status Unknown (no registry in this repository).

## Variants

### size
- `md`: the default inside page headers
- `sm`: dense table toolbars. Single use, `src/budgets/BudgetTable.tsx:28`
- `lg`: Unknown. Present in the stories, missing from the `size` type. See Conflicts

## States
- Default: one segment is selected; arrow keys move the selection
- Disabled: the whole control ignores input; its only cue is reduced opacity
- Loading: Unknown. No story or code path shows it

## Usage

### Rules
- `rule/segmented-control-max-four`: When more than four views exist, use `Tabs` instead of adding segments, because a fifth segment truncates its label at the `md` size. Evidence: story `FiveOptions` in `src/ui/segmented-control/SegmentedControl.stories.tsx` rendered at 360 px; `src/reports/ReportsHeader.tsx:14` and `src/budgets/BudgetHeader.tsx:9` each stop at four. Check: review.
  - Don't: `<SegmentedControl options={["Day", "Week", "Month", "Quarter", "Year"]} />`
  - Do: `<Tabs items={periods} />`

### Agent defaults
Unknown: not compared.
````

Adapted from design.how's `component-docs` skill and its `references/doc-format.md` (Arlan Marat); see `../LICENSE.design-how` and the repository's adopted-skills provenance record.
