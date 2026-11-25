# Method

Read this before changing `SKILL.md`. It records where the procedure comes from and why it differs from its sources. Agents running the skill do not load it.

## Evidence it started from

Measured in this repository on 2026-11-25: 36 of 48 skills had no cases, the 12 `evals/evals.json` files were read by no program, the repository check enforced only a skill's name and description, and `writing-for-agents` was a reference with no steps and no completion criterion.

## Chosen rung

Rung 3, an established method, with rung 1 added beside it. A check (`scripts/check-repo.ts`) enforces that a skill carries runnable cases; it cannot decide whether a procedure is the right one, so the rest is a procedure.

## What was taken, and from where

No text was copied; these are ideas, restated.

| Idea | Source |
| --- | --- |
| Write the failing case first, watch it fail, then write the least that passes (test-driven development, Kent Beck, *Test-Driven Development: By Example*, 2002). Applied to skills as "no skill without a failing baseline". | `obra/superpowers` at `22f0b46`, `skills/writing-skills/SKILL.md` |
| The form of the text follows the kind of failure. | same, "Match the Form to the Failure" |
| Fix it below the skill first, and a line earns its place only with evidence. | `garrytan/gstack` at `719b1f5`, `write-skill/SKILL.md.tmpl` |
| Corrections become checks before they become prose. | `cursor/plugins` `pstack/skills/correct`, already adopted here as `correct` |
| The evaluated agent must not be able to tell it is being evaluated; judge by what it did, with a judge from another model family. | `cursor/plugins` at `41e4009`, `pstack/skills/poteto-mode/playbooks/eval.md` |
| Every skill lists requests that belong to a neighbour. | `addyosmani/agent-skills` at `e997ac5`, `evals/README.md` |
| The `evals.json` case format and the with/without comparison. | Anthropic `skill-creator`, `references/schemas.md` |
| Look for the profession's known method before inventing one. | The owner's direction, 2026-11-25. None of the sources above asks for it. |

## What was changed for agents, and why

- Anthropic's loop ends when the person is satisfied after reviewing each iteration in a browser. Here the agent decides from the runs and the person sees one report, because a choice that running can settle is the agent's.
- superpowers tests with forced A/B/C choices under pressure. That measures a stated choice, so the cases here are ordinary requests in a workspace and are judged from files and transcripts.
- gstack routes with a prompt hook. Not adopted: activation on description alone has not been measured here.
- The method lookup has a table for adapting a human method, because methods carry steps that exist for human limits (schedules, memory, fatigue) and lack steps for an agent's (ending early, no memory across sessions, claims without output).

## Known limits

- The first skill changed with this procedure (`full-send`) could not follow steps 3 to 5: the fix was a script, and its steps run against a remote, a PR, and CI that the runner cannot prepare. Step 3 now names both cases and makes the script's failing-then-passing test the evidence. That paragraph rests on one use and was not run against cases.

- The runner resolves local skills in this repository only; elsewhere the comparison is done by hand.
- One run per arm is a small sample; a narrow gap needs `--runs`.
- The run workspace path contains `skill-eval`, which an evaluated agent could notice.
