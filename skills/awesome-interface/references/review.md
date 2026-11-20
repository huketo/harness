# Interface review

Use for a requested screen or flow review. A review is read-only unless implementation is explicitly requested. An explicit change-review request first follows [change-review.md](change-review.md), then uses the evidence, ranking and verdict rules here. Do not turn review into stress testing, variant generation or explanation without that intent.

## Resolve and inspect

1. State the requested screens, flows and boundaries. Identify the framework, styling system, shared components, tokens, supported viewports, existing preview and relevant project guidance. Preserve those conventions in proposed fixes; a review is not a stack or color-system migration.
2. For a full review, load and apply all six owners in order: [accessibility](accessibility.md), [layout](layout.md), [writing](writing.md), [typography](typography.md), [colors](colors.md), [UI polish](ui.md). For a partial request, load only its relevant owners and label the report partial. A missing owner is `Not reviewed`, not permission to reconstruct its rules from memory.
3. Map each requested surface to its actual states: default, empty, loading, error, disabled, selected, hover, focus, active and narrow width where applicable. Inspect the complete requested scope; if it cannot be covered, report the uninspected boundary rather than silently shrinking the task or claiming a full review.
4. Read source and inspect safe local rendering where the claim depends on appearance or interaction. Exercise keyboard paths, supported themes, 320px width and 200% zoom where relevant. For motion, observe normal playback and, when useful, slowed playback and interruption; slow playback alone does not prove the normal experience. Use existing preview mechanisms, not new infrastructure or live destructive actions.
5. Collect evidence by owner, then consolidate into the [report format](../assets/review-format.md). Review domain rules in their owning references; this workflow owns only evidence, severity, ranking and reporting.

## Capture and compare

For a web surface served locally, [`scripts/capture.mjs`](../scripts/capture.mjs) saves a screenshot and accessibility tree per surface, state, width and theme, and [`scripts/pixdiff.mjs`](../scripts/pixdiff.mjs) compares two sets pixel by pixel. Both need Playwright and a Chromium; `node scripts/find-chromium.mjs --root <app>` reports which it found, and `--help` on each script lists its flags. Without them, use the host's browser tool and record the same evidence by hand.

1. Capture a local build with fixed data or state you can throw away. Its guard ([`scripts/capture-guard.mjs`](../scripts/capture-guard.mjs)) sees only the HTTP requests Playwright routes for the page and its context: it lets GET, HEAD and CORS preflight requests to a local host through, along with a POST listed as a read by exact name, answers fixtured calls in the browser, and aborts the rest. It does not see WebSocket traffic, or the route status check capture.mjs sends from Node, a GET, before the browser opens. It also does not see any hop after a redirect: Playwright calls a route handler only for a request's first URL ([`page.route`](https://playwright.dev/docs/api/class-page#page-route)), so a request the guard lets through, such as a listed POST read, that is answered 307 or 308 is sent again with its body to the new location unjudged. A GET that writes, such as a logout link, also passes. An app that writes over a WebSocket or a GET, or whose listed reads redirect, is not safe to capture against shared data.
2. Before a run that can reach a backend, list every write the app sends, in the shape its network log shows, and pass the file as `--writes`. capture.mjs checks the guard's decision on each listed request, and on nothing else, then stops before opening a browser if one would get through or a line is not `METHOD URL`. Pass `--no-backend` only for a page that sends no writes. It skips that check and nothing else: the guard decides each request as it always does (a GET or HEAD to a local host continues, a GET logout included), and the run prints `WARN` for each aborted request whose method is not GET, HEAD or OPTIONS.
3. Write captures outside the checkout (`--out /tmp/...`). Reach each reviewed state with `--surfaces` and a `--states` module, at the reviewed widths and themes. Take the baseline with `--kind before` and the changed build with `--kind after`, with otherwise identical flags. A run short of its plan exits 1 and lists what it missed; its `Coverage:` line names what it never captures (hover, focus and pressed states, motion in flight).
4. Compare the two folders with `pixdiff.mjs <before> <after>`. Each changed region it reports, with its box and diff image, must trace to an intended change. An unexplained difference is a finding: cite the diff image and region, and rate it by the harm the region shows, at least `LOW`. When two captures of the same build already differ, the capture is unstable and the comparison is `Not verified`, not a finding. Diff the `.aria.yml` trees too, for names, roles and states that disappeared.
5. Request bodies stay out of `guard.log` by default. When the review must show that a change still sends the same request, capture the same state before and after, each with its own `--bodies <file>`, and diff the two files.

## Evidence

Every source finding cites `path/to/file:line` at the reviewed revision and includes the current implementation. Every runtime finding names the screen/component, viewport, state, exact interaction and observed result; attach the relevant capture when available. A screenshot-only finding cites its artifact and region instead of inventing a source location.

Source can establish a missing attribute or an authored declaration, but cannot alone establish rendered contrast, clipping, focus visibility, animation quality or the winning cascade. Inspect the rendered state or mark that claim `Not verified`. Likewise, pixels alone cannot prove which source rule caused a symptom. Separate confirmed symptoms from suspected causes. A surface that writes, such as a form, a toggle that saves or a picker that commits on select, stays `Not verified` until its write path ran in a browser; name the command that would run it.

Judge a focus indicator by reaching the control with real Tab presses (Playwright `keyboard.press("Tab")`, not `element.focus()`) and reading a capture of that state. A focused element whose computed outline is `none` does not prove a missing ring, because a container can draw it through `:has(:focus-visible)` or a pseudo-element.

Responsiveness is measured, never read from a screenshot. Before the interaction, observe Event Timing entries in the page, which Chromium exposes: `new PerformanceObserver((l) => entries.push(...l.getEntries())).observe({ type: "event", durationThreshold: 16, buffered: true })`. Perform the press, key or tap with real input, then report each entry's `name` and `duration`. An entry's `duration` runs from the input to the next paint, rounded to 8 ms; entries under the threshold are not reported. An interaction with an entry at 100 ms or more fails its feedback check.

Project preferences are context, not findings. Report demonstrated user harm, not disagreement with density, radius or voice. If a shared token or documented convention causes the harm, cite that source once and list its confirmed affected consumers.

## Severity and ranking

- `HIGH`: blocks a task, misleads, hides content or controls, risks data loss, or causes a repeated systemic failure.
- `MEDIUM`: materially harms comprehension, efficiency, adaptability or consistency.
- `LOW`: isolated polish with limited task impact.

The owning domain establishes whether a defect exists. Once confirmed, these escalation triggers are `HIGH`:

- Interactive control without an accessible name.
- Keyboard-reachable control without a visible focus indicator, or a pointer path unavailable by keyboard.
- Motion or autoplay ignoring reduced-motion preferences.
- Content or controls clipped, overlapped or unreachable at 320px width or 200% zoom.
- Body or control text failing its required rendered contrast ratio.
- Meaning or state conveyed by color alone.
- Destructive action without confirmation, undo or distinct treatment.
- Truncated content with no way to access its full value.
- Content or controls beyond a scroll edge or disclosure without a visible cue.
- Error without a recovery path.
- Semantic color used against its meaning.
- State change conveyed only by motion, with no persistent static cue.

Rank triggers first, then severity, then reach and leverage of one correction. One root cause is one finding, even across domains or components; assign its underlying rule to one owner and describe secondary effects in the rationale. List confirmed locations together. Report at most 15 ranked findings, never pad. If more confirmed findings exist, disclose the excluded count and severity, including any additional HIGH blockers; the cap cannot produce an approval by hiding blockers.

Propose the smallest effective correction, in this order when viable: delete unnecessary work, use native platform behavior, reuse existing primitives/tokens, correct the value, then add structure. A symptom-specific patch is not preferable to correcting its shared source. State each correction as a check that fails on the reviewed build and passes once fixed, such as `Enter in Email sends 1 POST /invites (now 0)` or `Tab reaches Save and the capture shows its ring`.

## Coverage and verdict

`Clear` means the stated evidence was inspected with no actionable finding. `Not reviewed` names an uninspected domain or state and why. `Not verified` names a required runtime check that was not exercised; absence of evidence is not a defect.

Choose the verdict in this order:

1. `Block` when a confirmed in-scope HIGH remains, including blockers beyond the table cap.
2. `Not verified` when required coverage or evidence is missing, or a material unresolved claim prevents a supported verdict. List what would resolve it.
3. `Needs changes` when only confirmed MEDIUM or LOW findings remain.
4. `Approve` when no actionable findings remain and the declared scope is covered. A partial approval applies only to the stated partial scope, never to the whole interface.

The report opens with a ship line that restates the verdict for the reviewed scope, its leading reason and the finding counts:

| Verdict | Ship line |
| --- | --- |
| `Block` | `Ready to ship: no. Enter in Email cancels the invite (1 HIGH, 2 MEDIUM).` |
| `Not verified` | `Ready to ship: no, pending <the check>.` |
| `Needs changes` | `Ready to ship: yes, with fixes (2 MEDIUM, 1 LOW).` |
| `Approve` | `Ready to ship: yes.` |

A partial or change review names its scope in the line (`Ready to ship, settings dialog only: …`). The ship line, the verdict and the findings agree.

For change reviews, only confirmed `Introduced` and `Regression` findings enter the ranked cap and severity verdict. `Pre-existing` findings stay separate; `Unclear` attribution cannot become a confirmed change defect and is handled as an evidence gap. A domain demonstrably unaffected by the resolved change is not a missing check, but must be labeled rather than called clear.

If implementation was requested, use the agreed findings as its scope, apply the owning domain guidance in the project’s existing idiom, and re-exercise changed states. Distinguish proposed fixes from applied and verified fixes.
