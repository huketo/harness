# Token mapping report

Use this mode when the user asks how values in an existing implementation map onto the project's own tokens: "are we using our tokens on the settings page", "which hardcoded colors match which tokens", a token audit, or groundwork for a token migration. The output is a report in the reply. This mode writes no file: it does not edit code, token definitions, or the design-system artifact, and it never names a new token. `git status` reads the same before and after the run.

A finding the user wants recorded afterwards (a gap, a conflict between sources) becomes a separate documentation request through the main workflow, where it enters the artifact as **Proposed** or **Unknown**. Replacing values in code is a UI implementation task outside this skill.

## 1. Find the token list

The list is the project's runtime token owner: token files, theme configuration, custom properties on `:root`, or a component library's variable pairs. Record its name, path, and how you read it. A framework's default theme or a public design system's names are not the project's list unless the project consumes them as its own.

The design-system artifact is evidence about the list, not the list. A token the artifact marks **Current** must exist in the runtime owner; one it marks **Approved** or **Proposed** is not yet a mapping target. When the only candidate for a row is Approved, say so in the row's reason and leave it a Gap until the runtime owner implements it.

If no list exists or a read fails, stop and report it. Never reconstruct a list from memory or from the values being mapped.

Complete when the list's owner, path, modes (light, dark, density, brand), and read method are recorded.

## 2. Find the values

Take the scope the user named; otherwise the branch diff; otherwise the product code. Record each value with its file, line, CSS property or prop, and its job (what the value does on the surface). A job read from code is **Current**; a job taken from a class name, variable name, or nearby markup is marked *inferred*.

A palette utility (`text-gray-500`) names a value and no job. It gets a row, counted apart from raw values.

Complete when every value in scope has a row with its location and job, and every inferred job is marked.

## 3. Resolve and normalise

Follow every alias to its final value in each mode, and record every disagreement between two sources (see Source conflicts).

Normalise both sides with code, never by eye:

- Lengths to px, using a 16 px root for `rem` unless the project sets another. Line height to a unitless ratio.
- Colors to OKLCH plus alpha with [`scripts/oklch.mjs`](../scripts/oklch.mjs) in this skill's directory. Run it by absolute path from the repository root: `node <design-md skill directory>/scripts/oklch.mjs <color>...` prints one OKLCH line per color, and `--delta <a> <b>` prints the deltaE OK (OKLab distance times 100) and both alphas. It reads hex (3, 4, 6 and 8 digits), `rgb()`, `hsl()`, `hwb()`, `oklch()`, `oklab()` and the CSS named colors, each with its alpha. It refuses `color()`, `lab()`, `lch()`, `color-mix()`, relative colors, `var()` and `currentColor` with exit code 2; resolve those through a browser's computed style and say so in Source, or leave the row's value **Unknown**.
- A deltaE OK under 0.5 counts as identical, which absorbs 8-bit rounding.
- Alpha is part of the color. `--delta` prints `alpha differs` when the alphas are more than 0.02 apart, and such a pair is never Exact.

Complete when every row and every candidate token has a normalised value per mode, or an Unknown value with the reason.

## 4. Classify

Give each row one class per mode. Check purpose first, then value; tolerances apply only after the purpose fits.

| Class | Condition |
| --- | --- |
| Exact | The token's documented job covers the row and the normalised values match. |
| Semantic | The job covers the row and the difference is within tolerance. State the difference in numbers. |
| Ambiguous | Two or more tokens fit and no source picks one. Name every candidate. |
| Gap | No token's job covers the row, or the only fitting token is out of tolerance. A gap gets no new token name. |

**Not mapped** (counted in the Summary, no row): a role token with alpha applied (`color-mix()` over its `var()`, a utility's alpha modifier), and graphic values such as logo art, illustrations, and decorative gradient stops.

Rules that decide a class:

- A value match with the wrong job is never a match. Wrong: `#6b7280` mapped to `color.border.default` because the hex is equal. Right: the value colors text, so the candidates are text tokens, and the border token goes under Do not use.
- A semantic token wins over the primitive it aliases. Map to a primitive only when no semantic token covers the job, and say so.
- A row whose job cannot be read is Ambiguous when the jobs it might do give two or more candidates, and otherwise a Gap marked "job unread".
- If the list states no purposes at all, the run matches values only. Each reason begins "Value only", Do not use stays empty because purpose cannot be checked, and the report adds Consistency by role. A palette-only list makes almost every palette row Exact by definition, so Consistency by role becomes the main output and the table keeps only rows that are not Exact.

Complete when every row has a job, a class per mode, and a reason.

### Categories

A candidate belongs to the same category as the row's job:

- Color by role: surface, text, border, icon, action, focus, status.
- Spacing by job: inset (inside a component) and gap (between items). One scale often serves both, so record which job the row does.
- Size, radius, border width, typography (family, size, weight, line height, letter spacing), shadow (each part its own row), opacity, motion (duration, easing), z-index.

### Tolerances

When the design-system artifact or another project source states tolerances, use those and cite them in Source. Otherwise use these defaults and say so. A difference equal to the limit is inside it.

| Category | Limit |
| --- | --- |
| Color | deltaE OK 2 |
| Spacing, size, radius | 2 px |
| Font size | 1 px |
| Line height | 0.05 as a ratio |
| Letter spacing | 0.01 em |
| Opacity | 0.02 |
| Duration | 30 ms |
| Border width, weight, family, easing | none |

## 5. Stops

Stop only on these, and return what stopped the run, the groundwork so far, and the shortest message that unblocks it (for example, "Give the path of the token file the settings page consumes."):

- No token list exists, or reading it failed.
- One token name has two values in the same mode.
- Two sources disagree and no project rule says which wins (report both).

## 6. Report

Report in the user's language, in this order:

1. **Summary** — counts with their unit (occurrences, lines, or mapping rows), per class and mode, plus Not mapped.
2. **Mapping** — a table of location, property, job (with *inferred* where it applies), value, class, token, and reason.
3. **Do not use** — tokens whose value matches but whose job differs, with the rows they would mislead.
4. **Ambiguous** — each row with its candidates.
5. **Gaps** — each row and why no token covers it.
6. **For a person to decide** — unresolved source conflicts and Approved-only candidates.
7. **Source** — the token list and how it was read, the tolerances used and their origin, values resolved through computed style, and every source conflict.
8. **Coverage** — the last line, `Coverage:` followed by what was scanned and what was not.

When Gaps exceed 30% of rows and number 12 or more, the list is usually the wrong one for this scope. Say so, still deliver the table, and open the report with `Status: not actionable (gap threshold)`.

Close with one prompt the user can paste to take the next step, such as a documentation update that records the gaps as Proposed.

### Consistency by role

Write it when the list states no purposes or the ask is about consistency. Group every color row by role. For each role give the distinct values with counts, their spread in deltaE OK, and near pairs (under 5) that likely mean one thing:

```
Text: 6 values over 200 rows. gray-500 (80), gray-600 (60), #666 (10) sit within deltaE OK 4 and likely mean one muted text role.
```

### Source conflicts

Two sources that disagree on a value go under Source with both sides. Quote the project rule that says which wins. Otherwise choose neither and move the question to For a person to decide.

## Done

Every row has a job, a class, and a reason; every Ambiguous row names two or more candidates; every inferred job is marked; nothing in the repository changed; the last line starts with `Coverage:`.

Adapted from design.how's `token-mapping` skill and its `references/mapping-rules.md` (Arlan Marat); see `../LICENSE.design-how` and the repository's adopted-skills provenance record.
