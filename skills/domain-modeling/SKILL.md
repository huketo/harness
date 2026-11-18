---
name: domain-modeling
description: Record a settled domain term in the glossary or a settled architectural decision as an ADR, in this project's formats. Use when a term or decision has just been resolved, or another skill needs to write one.
---

# Domain Modeling

Write a domain term or an architectural decision down at the moment it is settled, in the place and format the other skills read. Reading the glossary for vocabulary needs no skill; this one is for changing it.

## Where the files live

A repository with one context keeps `GLOSSARY.md` at the root and decisions in `docs/adr/`. When a root `GLOSSARY-MAP.md` exists, the repository has several contexts: the map names each context's own `GLOSSARY.md`, context-specific decisions sit in that context's `docs/adr/`, and system-wide ones stay in the root `docs/adr/`.

If only the legacy `CONTEXT.md` or `CONTEXT-MAP.md` exists, read it as the same document, and propose `git mv` to the new name before editing it. Create a file only when there is something to write in it.

## Glossary

Add or correct the term in `GLOSSARY.md` as soon as it is resolved, in the format of [GLOSSARY-FORMAT.md](./GLOSSARY-FORMAT.md). When a new term conflicts with an existing entry, settle which meaning stands before writing. The glossary holds domain terms and nothing else: no implementation details, specifications, or decisions.

## ADR

Record a decision only when all three hold:

1. **Hard to reverse** — changing it later has a real cost.
2. **Surprising without context** — a later reader would ask why it was done this way.
3. **A real trade-off** — there were genuine alternatives, and one was chosen for stated reasons.

Use the format in [ADR-FORMAT.md](./ADR-FORMAT.md).
