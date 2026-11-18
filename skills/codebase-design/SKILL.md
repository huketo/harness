---
name: codebase-design
description: Sketch a module's types, signatures, and dependency direction before writing code that crosses a function boundary, and name the check that will enforce the shape. Not needed for edits that keep those contracts.
---

# Codebase Design

Settle the shape before the code: sketch it, pick it, and name what will keep it. A shape that nothing enforces is copied wrong by the next agent, which reads only the file it opened and imitates the nearest example.

## 1. Trace

List every system the change touches: its callers, the owner of each piece of state it reads or writes, and each I/O boundary it crosses. Read the ADRs under `docs/adr/` for the area and the glossary the root `AGENTS.md` names; an ADR is a decision this sketch does not reopen silently.

**Done:** every caller and state owner is named with a `path:line`.

## 2. Sketch two shapes

Write two different shapes as types, signatures, and module boundaries, with no function bodies. Show how a caller uses each one. For a large or contested interface, run [DESIGN-IT-TWICE.md](DESIGN-IT-TWICE.md) instead of sketching alone.

**Done:** two sketches that differ in where state lives or which way a dependency points, not only in names.

## 3. Pick

Choose the shape where:

- each piece of state has one owner;
- each task has one supported way, and the old way is deleted in the same change, with its callers migrated;
- callers need to know the least to use it correctly (a **deep** module);
- an invalid state cannot be written as a value.

When workarounds for the current shape keep repeating, redesign it as if the new requirement had been there from the start instead of adding another patch.

## 4. Name the enforcement

For every boundary the chosen shape draws, name the check that fails when it is crossed: a type, an import restriction, a test at the module's interface. When the repository has no such check, add it with the `correct` skill's rungs, or record the rule as `unenforced` in the `Rules and enforcement` table of `AGENTS.md`.

**Done:** each boundary in the sketch has a named check or an `unenforced` row.

## Structural defaults

Use these when the repository's ADRs and existing conventions are silent. An existing convention wins over a default; change it through an ADR, not through one module.

- **Functional core, imperative shell.** Logic lives in pure functions that take values and return values. I/O lives in a thin outer layer that calls the core.
- **Ports and adapters.** Dependencies point inward: the core declares the type it needs, and the outer layer passes an implementation in. [DEEPENING.md](DEEPENING.md) classifies dependencies and says when a port is warranted.
- **One public entry per feature.** A feature is a directory with one entry file. Code outside the feature imports the entry and nothing else.
- **Parse at the boundary.** External input (CLI, config, network, files) is parsed once into a typed value where it enters. Code inside trusts the type and does not re-validate.
- **States as sum types.** Model alternatives as a discriminated union and let the compiler demand that every branch is handled.

## Vocabulary

Use these terms in a sketch; keep the repository's own identifiers and domain terms otherwise.

- **Module** — anything with an interface and an implementation: a function, a class, a package, a slice.
- **Interface** — everything a caller must know to use the module correctly: types, invariants, ordering, error modes, required configuration.
- **Seam** — the place where a module's interface lives, where behavior can change without editing there.
- **Adapter** — a concrete thing that satisfies an interface at a seam. One adapter is a hypothetical seam; two make it real.
- **Depth** — how much behavior sits behind how small an interface. **Leverage** is what callers gain from depth; **locality** is what maintainers gain, because a change lands in one place.
- **Deletion test** — imagine deleting the module. If the complexity vanishes, it was a pass-through; if it reappears in every caller, the module earns its place.
