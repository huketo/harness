# Human-in-the-loop rules in T3 Code

This file owns how an agent in a [T3 Code](https://github.com/pingdotgg/t3code) thread asks the person, accepts an approval, finishes, and behaves in an unattended run. It applies to every provider T3 runs (Claude Code, Codex, Antigravity). An agent is in a T3 thread when the `t3-code` MCP tools (`orchestrator_capabilities`, `delegate_task`, `schedule_task`) are available to it.

An agent in a Herdr pane (`HERDR_ENV=1`) or an OMP session follows [`.omp/APPEND_SYSTEM.md`](../../.omp/APPEND_SYSTEM.md) instead. The two never mix: a T3 thread never runs `herdr-hitl`, and a Herdr pane never calls T3 tools to reach the person.

## The thread is the channel

The T3 thread is the only channel to the person. T3 Connect can push a thread's pending question, pending approval, and finished turn to a paired phone, so a question asked in the thread reaches the person whether or not they are at the desktop. Presence is never inferred and never declared by the agent.

- Ask with the provider's own question tool when it has one (Claude Code `AskUserQuestion`, Codex user-input request). T3 shows it as a pending request.
- When no question tool exists, or the decision does not block the rest of the turn, finish all independent work first and put the question in the final response of the turn.
- A provider approval prompt (a tool call that needs permission) is also delivered through the thread. Request it only for an action the task actually needs.

## When a human decision is required

Ask only after repository context, tools, tests, and available evidence cannot resolve it. Human-only decisions are destructive or irreversible actions, real design tradeoffs with no context-visible answer, credentials or values only the person has, contradictory requirements, and scope outside the assignment. Never ask for reassurance, for facts the environment answers, for style details, or for cheap reversible choices. Combine related questions into one request. Batch reversible external-write approvals once per plan when their full scope is known; keep destructive, irreversible, or direction-changing decisions separate.

For a material technical alternative with costly reversal and unresolved evidence, review it first with the `council` skill, then send its recommendation and dissent with the question so the person does not decide empty-handed.

Credentials go through T3's `request_secret`, never through chat text.

## Message contract

The person often reads on a phone.

- Write the question, its body, and choice labels in Korean. Quote an English error or identifier only as evidence, and explain it in Korean.
- Make the question self-contained: the decision first, then the current state, the necessary context, and the consequence of every choice.
- Use short paragraphs and numbered lists. Keep choice labels short; when a label needs a sentence, number the choices and explain each number in the body.
- State one recommended choice with the evidence or risk behind it, naming its number.

## Authority

Proceed only on an explicit, unambiguous answer authorizing the action. A timeout, a cancellation, a decline, ambiguous free text, a dismissed question, or a delivery failure grants no authority: take the safe path or block the affected item. Never treat silence as approval. A pending question does not stop independent work; defer only the work that strictly depends on the answer and record the blocker in the turn output.

T3's runtime mode (Auto, Full access) controls which tool calls run without a prompt. It is not authority for the effects [`authority.md`](authority.md) classifies as needing a decision; Full access removes the prompt, not the decision.

## No completion gate

Ending a run, a phase, a subtask, or a delegated task is never by itself a reason to ask. Report the outcome, the verification performed, and any remaining risk in the final response instead.

## Delegated children

A task started with `delegate_task` has no direct person. It never asks the person and never calls a question tool. When it meets a human-only decision, it writes the question, the choices, and their consequences in its result, finishes the independent work, and ends. The parent thread owns every human decision: it answers a child's pending request with `t3_pending_request_respond` only when the answer is already authorized, and otherwise asks the person under this file. A child's pending approval grants the parent no approval authority.

## Unattended runs

A run started by a T3 scheduled task, by `bench/bench.py`, or by any other scheduler has no reachable person, even though its thread pushes a notification when it ends. In such a run:

- never call a question tool, never request an approval, and never wait for an answer;
- resolve in-scope, reversible technical matters autonomously, or after a `council` review where its rules allow;
- never invent approval; when an unapproved human-only decision appears, defer the dependent work, leave the repository and runtime consistent, continue independent work, and report the blocker and evidence in the final response;
- print the job's no-op marker exactly when the job defines one and nothing changed.

A scheduled run inherits the runtime mode stored with its task. Antigravity has no Auto mode and asks for approval under any narrower mode, so an unattended Antigravity task needs Full access; scope that access in the task prompt and the guarded wrapper ([`t3/scheduled/guard.mjs`](../../t3/scheduled/guard.mjs)), not by expecting a prompt to stop it. Antigravity under T3 does not load the repository `AGENTS.md`, so the task prompt must name this file by path.
