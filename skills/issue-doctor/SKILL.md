---
name: issue-doctor
description: Diagnose whether tracked issues still hold and expose evidence-backed drift among repository claims, implementation, and external precedent. Use by name for issue staleness reviews, repository claim audits, and corpus evidence-health checks.
disable-model-invocation: true
---

# Issue Doctor

Diagnose work already being carried. Determine whether an issue still holds on the premises it was written on, and expose disagreements among repository claims, implementation, and external precedent. Present evidence for a person to judge; do not choose the correct surface, rank findings, edit issues, or publish drafts.

## Vocabulary

- **Premise (전제)**: what an issue took to be true when written, such as code behavior, documented behavior, or an earlier decision; age is not a premise.
- **Drift (드리프트)**: a disagreement among external precedent, repository claims, and implementation that requires human judgment.
- **Reference (레퍼런스)**: an external primary source read as evidence or precedent, never as automatic authority.
- **Ungrounded (미검증)**: written before the repository's earliest recorded reference reading, and therefore unchecked rather than wrong.
- **Blocker (차단)**: a directional hard constraint under which one issue cannot start until another closes.
- **Direction decision (방향 결정)**: an issue whose resolution changes what other issues mean rather than producing a deliverable.
- **Impact (영향 범위)**: every issue transitively blocked by a direction decision and therefore put back in question when it resolves.

## Evidence discipline

Read the thing a claim describes. Check code in the repository, run the tool, call the service, or fetch the primary source. Agreement between two documents is not verification of either.

Label every evidence line:

- `[VERIFIED]` only when this run directly read, ran, called, or fetched the named thing. Include a file and line, exact command, stable URL and section, service request, or tracker query.
- `[UNVERIFIED]` when the thing itself was unavailable. State what could not be reached and the exact obstacle; do not replace it with agreement from another document.
- `[INFERENCE]` when a conclusion follows from verified facts but was not observed directly. Name the facts and keep the conclusion distinct from them.

Never describe remembered behavior, a search snippet, or an inaccessible source as verified. Sanitize credentials and sensitive response data while preserving a reproducible command or request description.

A claim can drift; a decision cannot. Check a decision record's premises and stated consequences, but treat the choice itself as a human decision that can only be replaced.

A reference about another system does not contradict this repository's behavior. It demonstrates an alternative. State what each system does and leave the comparison open.

Read external sources during the run rather than relying on recall:

- For source code, pin the full commit SHA and record repository URL, path, and lines read.
- For a specification, record its stable URL, version or retrieval date, and exact section.
- For a live service, record the sanitized request or command, response relevant to the claim, and observation time.

If the repository already records reference readings, follow that convention. Otherwise keep the complete source identity in the report and state where the report was stored.

## 1. Establish the subject and evidence boundary

Choose one explicit subject: an issue, a document, a topic spanning named surfaces, the surfaces changed by a revision, or the open-issue corpus. Record:

- subject and exclusions;
- repository revision and run date;
- tracker and source access available;
- report location;
- any evidence surface that is already unavailable.

Read every claim inside that boundary. Do not generalize an all-clear from a sample. Finish this step when every in-scope claim has a corresponding evidence attempt.

## 2. Read repository and tracker state

Discover the repository's tracker and maintained conventions from its remotes, configuration, and instructions. Use native directional blocking when available; otherwise use a repository-documented representation. Parent-child decomposition and nondirectional links are not blockers.

Treat pre-existing labels or fields as hints unless the repository explicitly owns and maintains their meaning. When no reliable direction-decision marker or blocker representation is discoverable, record that reading as `[UNVERIFIED]` instead of inventing one.

For GitLab, use `glab` directly. The list command defaults to open issues; page until a page is empty:

```bash
glab issue list --output json --per-page 100 --page 1
glab issue list --output json --per-page 100 --page 2
```

Use `--repo OWNER/REPO` when the current checkout does not identify the intended project. Read an issue and its discussion with:

```bash
glab issue view <id> --output json --comments --per-page 100 --page 1
```

Page comments when needed. For GitLab fields or relations absent from the high-level commands, use `glab api --paginate` with the applicable GitLab API v4 endpoint and record the exact command. If authentication, authorization, or API support blocks a reading, preserve the error as an `[UNVERIFIED]` limitation.

For another tracker, use its repository-configured CLI or API to obtain the same facts: open issues, issue bodies and discussions, maintained markers, and directional blocker relations. The diagnosis does not depend on one tracker's storage model.

## 3. Diagnose drift

For each in-scope claim, compare every surface it touches against the thing itself. Keep paths, line numbers, commands, versions, responses, and pinned SHAs while reading.

Write each disagreement as a question so the report leaves the resolution to a person:

```markdown
### Does the retry budget cover a timeout, or only a server error?

- **Repository claim** `[VERIFIED]`: every failed call is retried three times — `<document>:<line>`.
- **Implementation** `[VERIFIED]`: server errors are retried; a timeout exits on the first attempt — `<implementation>:<line>`.
- **External precedent**: none read; this finding is between repository surfaces.
```

When precedent was read, include it without turning it into a verdict:

```markdown
- **External precedent** `[VERIFIED]`: `owner/repository` at `<full-sha>` uses one budget for both outcomes — `<path>:<line>`.
```

Include every touched surface. Keep the external-precedent line even when none was read so a person can distinguish an internal disagreement from a comparison grounded outside the repository. State no resolution and assign no severity or priority.

Finish this step when every in-scope claim is either supported by a direct reading, represented by a finding, or explicitly marked `[UNVERIFIED]`.

## 4. Diagnose whether each issue still holds

Complete three readings for every in-scope issue, in this order.

### Premise reading

Extract what the issue assumes about repository or system behavior and check each premise against the thing itself. A moved premise produces `premise moved` with the path, line, command, or request showing the change. An old issue whose premises still stand is not stale.

### Grounding reading

Find existing records of external-source readings using the repository's own conventions. The earliest recorded reading date is the grounding boundary. An issue authored before it is `Ungrounded`; one authored on or after it is not. If no readings exist after searching the declared scope, classify the issue as `Ungrounded` and record the search scope. This says unchecked, not wrong.

### Direction-decision reading

Identify explicitly maintained direction-decision markers and follow blocker edges transitively. An issue inside a direction decision's impact is `pending`. Impact identifies what must be reviewed after the decision resolves; it does not predict invalidation.

A completed diagnosis may state any supported combination of `premise moved`, `Ungrounded`, and `pending`. State `holds` only when all three readings completed and no premise moved or pending state was found. If a required reading is unavailable, write `judgment not established` with the `[UNVERIFIED]` line rather than claiming the issue holds.

Write every judgment with all three readings:

```markdown
### #42 — holds, and Ungrounded

- **Premises** `[VERIFIED]`: the implementation still takes the timestamp from the record, as assumed — `<path>:<line>`.
- **Grounding** `[VERIFIED]`: authored `<date>`; the earliest recorded reference reading is `<date>` — Ungrounded.
- **Direction decisions** `[VERIFIED]`: no marked direction decision reaches this issue through blocker edges.
```

```markdown
### #57 — premise moved, and pending

- **Premises** `[VERIFIED]`: the issue assumes timeouts share the retry budget; only server errors do — `<path>:<line>`.
- **Grounding** `[VERIFIED]`: authored `<date>`, after the recorded boundary.
- **Direction decisions** `[VERIFIED]`: waits behind #31, an explicitly marked direction decision, so its impact reaches this issue.
```

Do not modify, close, relabel, or comment on judged issues. A moved premise calls for correcting the existing issue, not filing a duplicate.

## 5. Account for each drift finding

Search open issues for work that already carries each finding. For every finding, report exactly one disposition:

1. an existing issue that already carries the work;
2. a draft issue; or
3. a concrete reason there is no buildable work.

Draft only work created by a drift finding. Copy the complete question and evidence lines into the draft so it remains useful outside the report. Name the Issue Doctor run's subject, date, and report location. Derive acceptance criteria from the evidence without deciding which surface is correct.

When the underlying thing was unavailable, make direct verification the first criterion. When the work is blocked, name the blocker using the tracker's available representation. Keep drafts in the report for human publication; do not create tracker issues automatically.

```markdown
## Draft issue — <neutral title>

Found by the Issue Doctor run for `<subject>` on `<date>` — `<report location>`.

### <finding question>

<complete evidence lines>

## Acceptance criteria

- [ ] The underlying behavior is verified and the observation is recorded. <!-- only when needed -->
- [ ] The surface that proves wrong is corrected, and the change names which surface it was.
```

Finish this step when every finding has one recorded disposition.

## 6. Measure evidence coverage only for a corpus audit

Skip this step for a single issue, document, topic, or change-surface diagnosis unless the user explicitly asks for the metric.

For an open-issue corpus audit, count an issue as citing checkable evidence when it names at least one of:

- a repository path with a line;
- a command that can be rerun; or
- an external primary source at a pinned SHA or stable URL and section.

A heading named “Evidence” without one of those does not count. A citation only to another repository document does not close the verification loop.

Report numerator, denominator, population, date, and the counting rule together, for example `7 of 83 open issues, <date>`. Never report a bare percentage.

## Report for human judgment

Follow an existing repository convention for audit or investigation records. If none exists, choose a discoverable repository-local location and name that location in the report itself. Date every report.

Use this order:

```markdown
# Issue Doctor report — <subject>

- **Run date**: <date>
- **Repository revision**: <revision>
- **Subject**: <scope and exclusions>
- **Report location**: <chosen location>

## Access and limitations

<tools, tracker access, inaccessible surfaces, and [UNVERIFIED] items>

## Findings

<question-led drift findings, each with direct evidence and one disposition>

## Issue judgments

<all three readings for every in-scope issue>

## Evidence coverage

<corpus metric and rule, or “Not requested for this subject.”>

## Draft issues

<self-contained drafts for findings not already carried elsewhere>
```

The report is complete when every claim in scope has an evidence attempt, every judgment shows all three readings, every finding has one disposition, and every inaccessible fact is visibly `[UNVERIFIED]`. Stop at diagnosis and drafts so the person reading it retains every decision.
