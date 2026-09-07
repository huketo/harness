# Human-in-the-loop rules for this repository

This file is the project-scope `APPEND_SYSTEM.md` for the harness repository. Project scope wins
over `~/.omp/agent/APPEND_SYSTEM.md`, so this file replaces the global rules for any agent whose
working directory is this repository. It keeps the global channel resolution, human-decision
contract, message contract, and authority rules, and it drops the global terminal decision gate.

The gate is dropped here on purpose. This repository runs unattended agents: the `harness-cost-audit`
and `harness-host-sync` herdr-cron jobs and the `bench/bench.py` benchmark runner all spawn agents
that nobody is watching.
Channel resolution alone does not protect them, because the away marker is set exactly when those
agents are most likely to run: with the marker set the channel is `messenger`, the global gate fires,
and every run blocks on a question until its own timeout. That is recorded as a failed run and, after
three consecutive failures, auto-disables the cron job. It also notifies the human once per run.
Genuine blocking decisions must still be escalated; routine "may I stop now" questions must not be
asked.

## Resolve the channel before every question

A question for a human goes to exactly one of two channels, and the channel is resolved per question,
never once per session:

```sh
herdr-hitl channel
```

- `terminal` — the person is at this interface. Ask with the harness's own `ask` tool, or put the question in the response when a plain question is enough. Never invoke `herdr-hitl`.
- `messenger` — nobody is watching this interface. Ask with `herdr-hitl ask` under the message contract below.

The away marker behind that word is the person's declaration, not a guess. Do not infer presence from
anything else, and never run `herdr-hitl away` or `herdr-hitl here` yourself. `herdr-hitl ask` and
`herdr-hitl notify` enforce the same decision: on the `terminal` channel they deliver nothing and
exit `5`.

## When a human decision is required

Ask only after repository context, tools, tests, and available evidence cannot resolve it. Human-only decisions are destructive or irreversible actions, real design tradeoffs with no context-visible answer, credentials or values only the person has, contradictory requirements, and scope outside the assignment. Never ask for reassurance, for facts the environment answers, for style details, or for cheap reversible choices. Combine related questions into one request. Batch reversible external-write approvals once per plan when their full scope is known; keep destructive, irreversible, or direction-changing decisions separate.

## Message contract

This applies to both channels; the layout rules matter most on the messenger channel, where the person reads on a phone.

- Write the title, body, and visible choice labels in Korean. Quote an English error or identifier only as evidence, and explain it in Korean.
- Make the body self-contained. State the decision first, then the current state, the necessary context, and the consequence of every choice. Attachments verify the message; they never replace omitted context.
- Lay the source out for the Telegram HTML transport: short Korean section labels, blank lines, short paragraphs, numbered lists. Do not rely on Markdown headings or emphasis, and do not write raw HTML tags. Use a fenced code block only for actual code or an error excerpt.
- State one recommended choice with the evidence or risk behind it. If choice cards are numbered, name the same number in the recommendation. `--primary` and `--danger` are visual hints, not a substitute for the recommendation.
- Keep choice cards short. If a label needs a sentence to be understood, label the cards `1`, `2`, `3` and explain each number in the body.
- On the messenger channel always allow free text with `--free`, never `--free=false`, set a deliberate `--timeout`, and give `--agent` a useful run label.

## Authority

Proceed only on an explicit, unambiguous answer authorizing the action. A timeout, a defaulted timeout, a cancellation, a decline, ambiguous free text, a delivery failure, or a command failure grants no authority: take the safe path or block the affected todo. Never treat silence as approval. Record progress in agent todos and block the exact item that is waiting.

`herdr-hitl` exit `5` means the resolved channel is the terminal and nothing was sent. Ask at this interface instead; it is neither approval nor a failure to retry.

## No terminal decision gate

There is no terminal decision gate in this repository, on either channel. Do not ask the human for
permission to finish. Ending a run, a phase, a subtask, or a delegated slice is never by itself a
reason to invoke `herdr-hitl` or to ask at this interface. Report the outcome, the verification
performed, and any remaining risk in the final response instead.

## Unattended runs

An agent started by `herdr-cron`, by `bench/bench.py`, or by any other scheduler has no reachable
human, whatever `herdr-hitl channel` reports. In such a run, never invoke `herdr-hitl` at all. When a
genuine human-only decision appears, stop the affected work, leave the repository in a consistent
state, and report the blocker and the evidence in the run output so the human finds it in the run log.
