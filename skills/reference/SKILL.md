---
name: reference
description: Register or revisit external primary-source precedent as version-pinned evidence when a task needs reproducible facts from source code, a specification, or a live service.
disable-model-invocation: true
---

# Reference

A **reference** is an external primary source consulted as precedent. It is evidence of what another implementation, specification, or service does, not authority over the current project.

A **drift** is a disagreement between the reference, the current project's documentation, and its code. Report it for a person to decide; do not resolve it automatically.

A reference becomes reproducible evidence only at an identifiable version. Establish the full commit SHA, release or specification version, or live-observation timestamp before investigating, then carry it through the clone name, citations, and entry.

## Keep clones outside repositories

Put source clones in a scratch workspace so they cannot be formatted, checked, or committed with the target repository:

```bash
BASE="${XDG_RUNTIME_DIR:-${TMPDIR:-/tmp}}"
WORKSPACE="$BASE/references"
mkdir -p "$WORKSPACE" 2>/dev/null || WORKSPACE="$(mktemp -d "${TMPDIR:-/tmp}/references.XXXXXX")"
```

With a commit SHA in hand, fetch exactly it:

```bash
DIR="$WORKSPACE/<name>@<sha>"
git init -q "$DIR" && git -C "$DIR" remote add origin <url>
git -C "$DIR" fetch --depth 1 origin <sha> && git -C "$DIR" checkout -q FETCH_HEAD
```

Without one, clone the default branch shallowly, resolve its full SHA, and rename the directory before reading:

```bash
git clone --depth 1 <url> "$WORKSPACE/<name>"
SHA=$(git -C "$WORKSPACE/<name>" rev-parse HEAD)
mv "$WORKSPACE/<name>" "$WORKSPACE/<name>@$SHA"
```

The scratch workspace may disappear. The recorded source and version must be sufficient to recreate it.

## Read the primary evidence

First sharpen the question into the behavior, version, and decision that the entry must inform. Read only against that bound.

Prefer what actually runs at the pinned version: installed binaries and their help, then source at the matching version. For standards, use the first-party specification or official documentation. Treat tutorials, blog posts, and forum answers only as leads to primary evidence. When documentation and executable code disagree, record both and describe the observed or implemented behavior.

Cite every material finding inline where it appears. A code citation names the source path and line range or symbol plus the pinned SHA; an executed finding gives the exact command and version; a specification or official-document finding gives its URL, version or date, and section. Never rely on a header-only source list.

State uncertainty rather than turning inference into fact. Record every unanswered part of the sharpened question under an unresolved-items heading, even when the section says `None`.

For a long, separable investigation, `research` may perform the reading in a background agent when available. Give it the sharpened question, pinned version, source location, citation rules, and destination; the same procedure can always be completed directly without it.

## Write the entry

Follow an existing convention in the target repository for durable reference or research notes. If none exists, choose a sensible repository-owned location and state the chosen path in the completion report. Never put the entry only in the scratch workspace.

Use this structure:

```markdown
# Reference: <source identity>

- **Source**: <canonical URL or endpoint>
- **Pinned version**: <full SHA, release or spec version, or observation timestamp>
- **Read on**: <YYYY-MM-DD>
- **Consulted for**: <the exact question>

<one line describing how the source was read or exercised>

## <question answered by these findings>

<findings with inline source locations>

## What does not transfer

<constraints that depend on the reference's own environment, or None>

## Unresolved items

<unverified questions, or None>
```

Name findings by the questions they answer rather than by areas of the source. Record behavior where documentation claims otherwise, and record reference-specific assumptions that should not be copied into the target project.

## Revisit an existing entry

Compare the current source with the recorded version. For Git, use `git ls-remote <url> HEAD`; for a specification, check its published version or revision history; for a live service, repeat the recorded observation.

If the source moved, re-read the bounded question at the new version, update the current version and read date, retain the first-read date and prior version, and record what changed. An older entry is evidence about its pinned version, not an error.

If the reference, the target project's documentation, and its code disagree, report the drift and stop. The entry supplies evidence; a person chooses the direction.
