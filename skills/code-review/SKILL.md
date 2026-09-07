---
name: code-review
description: Review the changes since a fixed point (commit, branch, tag, or merge-base), the uncommitted working tree, or both — along two axes — Standards (does the code follow this repo's documented coding standards?) and Spec (does the code match what the user asked for or the originating issue/spec?). Runs both reviews in parallel sub-agents and reports them side by side. Use when the user wants to review a branch, a PR, work-in-progress changes, or asks to "review since X".
---

Two-axis review of the changes in scope — committed since a fixed point, uncommitted in the working tree, or both — along:

- **Standards** — does the code conform to this repo's documented coding standards?
- **Spec** — does the code faithfully implement the originating issue / spec?

Both axes run as **parallel sub-agents** so they don't pollute each other's context, then this skill aggregates their findings.

## Process

### 1. Pin the scope

Two independent things make up scope, and either or both can be in play:

- **Committed scope** — changes since a fixed point. Use the user's explicit ref or the MR's target branch. Otherwise infer the target from repository conventions and branch metadata; ask only if materially different candidates remain. A repository's default branch need not be its development target.
- **Uncommitted scope ("WIP")** — tracked changes and relevant untracked files when the user asks for WIP or current local work. A PR or committed-ref review excludes unrelated dirty work. State the selected scope before dispatch.

Capture the diff commands once:

- Committed: `git diff <fixed-point>...HEAD` (three-dot, so the comparison is against the merge-base) and `git log <fixed-point>..HEAD --oneline`.
- Uncommitted tracked files: `git diff HEAD` (staged plus unstaged changes). Include relevant untracked files from `git status --porcelain --untracked-files=all` by reading their content separately; `git diff HEAD` does not include them.

Resolve any fixed point and capture the selected diff plus relevant untracked content once. An empty scope is a valid no-changes result, not a reason to dispatch reviewers. Give both reviewers the same immutable snapshot and list the exact scope in the report; do not let moving worktrees change what each axis sees.

### 2. Identify the spec source

Look for the originating spec, in this order:

1. **The user's own request in this conversation.** If they told you directly what to build or fix, that request *is* the spec — quote it verbatim for the Spec sub-agent rather than searching for a document that doesn't exist.
2. Issue references in the commit messages (`#123`, `Closes #45`, GitLab `!67`, etc.) — fetch with whatever tracker access is already available (`gh issue view`, `glab issue view`, an MCP issue resource, a tracker workflow the repo documents under `docs/agents/`). If none is configured, ask the user for the issue link or text.
3. A path the user passed as an argument.
4. A spec file under `docs/`, `specs/`, or `.scratch/` matching the branch name or feature.
5. If nothing is found, ask the user where the spec is. If they say there isn't one, the **Spec** sub-agent will skip and report "no spec available".

### 3. Identify the standards sources

Anything in the repo that documents how code should be written, such as `CODING_STANDARDS.md` or `CONTRIBUTING.md`.

On top of whatever the repo documents, the Standards axis always carries the **smell baseline** below — a fixed set of Fowler code smells (_Refactoring_, ch.3) that applies even when a repo documents nothing. Two rules bind it:

- **The repo overrides.** A documented repo standard always wins; where it endorses something the baseline would flag, suppress the smell.
- **Always a judgement call.** Each smell is a labelled heuristic ("possible Feature Envy"), never a hard violation — and, like any standard here, skip anything tooling already enforces.

Each smell reads *what it is* → *how to fix*; match it against the diff:

- **Mysterious Name** — a function, variable, or type whose name doesn't reveal what it does or holds. → rename it; if no honest name comes, the design's murky.
- **Duplicated Code** — the same logic shape appears in more than one hunk or file in the change. → extract the shared shape, call it from both.
- **Feature Envy** — a method that reaches into another object's data more than its own. → move the method onto the data it envies.
- **Data Clumps** — the same few fields or params keep travelling together (a type wanting to be born). → bundle them into one type, pass that.
- **Primitive Obsession** — a primitive or string standing in for a domain concept that deserves its own type. → give the concept its own small type.
- **Repeated Switches** — the same `switch`/`if`-cascade on the same type recurs across the change. → replace with polymorphism, or one map both sites share.
- **Shotgun Surgery** — one logical change forces scattered edits across many files in the diff. → gather what changes together into one module.
- **Divergent Change** — one file or module is edited for several unrelated reasons. → split so each module changes for one reason.
- **Speculative Generality** — abstraction, parameters, or hooks added for needs the spec doesn't have. → delete it; inline back until a real need shows.
- **Message Chains** — long `a.b().c().d()` navigation the caller shouldn't depend on. → hide the walk behind one method on the first object.
- **Middle Man** — a class or function that mostly just delegates onward. → cut it, call the real target direct.
- **Refused Bequest** — a subclass or implementer that ignores or overrides most of what it inherits. → drop the inheritance, use composition.

### 4. Spawn both sub-agents in parallel

Dispatch both reviewers in one batch using the harness's available review/subagent capability. Give each the same captured changes and its own brief; skip builds, formatters, linters and tests in these read-only reviews. If subagents are unavailable, run the axes directly and disclose the lack of independent contexts.

**Standards sub-agent prompt** — include:

- The diff command(s) and commit list for whichever scope(s) are in play (committed, uncommitted, or both).
- The list of standards-source files you found in step 3, **plus the smell baseline from step 3** pasted in full — the sub-agent has no other access to it.
- The brief: "Report — per file/hunk where relevant — (a) every place the diff violates a documented standard: cite the standard (file + the rule); and (b) any baseline smell you spot: name it and quote the hunk. Distinguish hard violations from judgement calls — documented-standard breaches can be hard, but baseline smells are always judgement calls, and a documented repo standard overrides the baseline. Skip anything tooling enforces. Under 400 words."

**Spec sub-agent prompt** — include:

- The diff command(s) for whichever scope(s) are in play, and the commit list if a committed scope is in play.
- The path or fetched contents of the spec.
- The brief: "Report: (a) requirements the spec asked for that are missing or partial; (b) behaviour in the diff that wasn't asked for (scope creep); (c) requirements that look implemented but where the implementation looks wrong. Quote the spec line for each finding. Under 400 words."

If the spec is missing, skip the Spec sub-agent and note this in the final report.

### 5. Aggregate

Present the two reports under `## Standards` and `## Spec` headings, verbatim or lightly cleaned. Do **not** merge or rerank findings — the two axes are deliberately separate (see _Why two axes_).

End with a one-line summary: total findings per axis, and the worst issue _within each axis_ (if any). Don't pick a single winner across axes — that's the reranking the separation exists to prevent.

## Why two axes

A change can pass one axis and fail the other:

- Code that follows every standard but implements the wrong thing → **Standards pass, Spec fail.**
- Code that does exactly what the issue asked but breaks the project's conventions → **Spec pass, Standards fail.**

Reporting them separately stops one axis from masking the other.
