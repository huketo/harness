# Writing and documentation ownership

Write for the reader who performs the next action. Keep each rule, fact, command, and decision in one owning location, then link to it from shorter entry points.

## Document map

{{DOCUMENT_MAP}}

Prefer extending the document that owns a topic over creating a parallel explanation.

## Language

{{DOC_LANGUAGE_RULE}} Quote commands, paths, identifiers, and error messages exactly as they appear.

## Instructions

Before creating or changing `AGENTS.md`, `CLAUDE.md`, a skill, or another agent-consumed instruction, load the `writing-for-agents` skill when it is available. The canonical instruction file (normally root `AGENTS.md`) is a short router: durable repository-wide boundaries and trigger-rich pointers, not command catalogs or narrated architecture. The other of `AGENTS.md` and `CLAUDE.md` points to it (`CLAUDE.md` holds `@AGENTS.md`). Add new rules only to the canonical file, and leave content already in the other file in place until a person moves it.

A topic rule has one owner. Other files link to it without paraphrasing it. Keep investigation diaries and change history out of instructions; git holds the history.

## Domain documents

The glossary named in the root `AGENTS.md` holds domain terms and nothing else: no implementation details, specs, or decisions. The `domain-modeling` skill maintains it in the format of its `GLOSSARY-FORMAT.md`. Decisions go to `docs/adr/` as numbered records; see [`../adr/README.md`](../adr/README.md).

## Evidence and sensitive material

Cite repository evidence as `path:line` and say what it proves. Record exact commands and relevant outcomes for runtime evidence, including the environment and the limits of the interpretation.

Tracked files must not contain credentials, tokens, private URLs, session transcripts, internal logs or databases, or personal identifiers beyond what a maintained claim requires. Repository visibility and `.gitignore` are not secret-storage controls. Use synthetic examples where an example is needed.

## Third-party text

Before copying or adapting external text or code, verify its license and keep the notices it requires next to the copied material. Distinguish local changes from upstream material.

## Comments and tone

Inline comments explain a non-obvious invariant, ownership seam, or failure the code prevents. Keep change history, investigation diaries, and obvious syntax out of comments. Use direct, factual language, and claim no more than the evidence exercised.
