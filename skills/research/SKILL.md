---
name: research
description: Research a topic against primary sources and record the evidence. Routine single-page API lookups stay inline.
---

For a small, bounded lookup — one doc, one API, a handful of files — do it inline; don't spend agent-spawning overhead on legwork you can finish yourself in a turn or two.

Delegate reading only when an independent investigation can proceed while the owner does other useful work, or the reading would overwhelm the working context. Otherwise investigate inline. A read-only scout returns findings and sources; the writing owner records them.

The investigator follows each material claim to its primary source: official docs, source code, specs or first-party APIs. Return the actual findings, citations and uncertainties to the writing owner; a promised filename is not a handoff.

When a source is inaccessible, say so. Analyze user-supplied original text directly and identify it as supplied text; do not present search snippets as a verified reading of the original page.

The writing owner saves one research note in the repository's existing location. Each material claim carries a path and line range, command and observed output, or URL with section/version. Distinguish source statements from inference and verify that a retrieved page is the requested document, not a redirect, default model or comments feed. If there is no established location, choose one and state it.

**Done:** the file exists on disk, every material claim in it names the primary source it came from, and the chosen save location is stated.
