# Human-in-the-loop rules

This file owns how an agent asks the person, accepts an approval, finishes, and behaves in an unattended run in this repository. It applies to every agent harness used here. Rules marked T3 apply when the agent runs in a T3 Code thread, which is the case when the `t3-code` MCP tools (`orchestrator_capabilities`, `delegate_task`, `schedule_task`) are available.

## The session is the channel

The agent's own session is the only channel to the person.

- Ask with the harness's question tool when it has one (Claude Code `AskUserQuestion`, Codex user-input request).
- When no question tool exists, or the decision does not block the rest of the turn, finish all independent work first and put the question in the final response of the turn.
- Request a tool approval prompt only for an action the task actually needs.
- T3: the thread is the channel. T3 Connect pushes a thread's pending question, pending approval, and finished turn to the paired phone, so a question asked in the thread reaches the person whether or not they are at the desktop. Presence is never inferred and never declared by the agent.

## When a human decision is required

Ask only after repository context, tools, tests, and available evidence cannot resolve it. Human-only decisions are destructive or irreversible actions, real design trade-offs with no answer visible in context, credentials or values only the person has, contradictory requirements, and scope outside the assignment. Never ask for reassurance, for facts the environment answers, for style details, or for cheap reversible choices. Combine related questions into one request. Batch reversible external-write approvals once per plan when their full scope is known; keep destructive, irreversible, or direction-changing decisions separate.

For a material technical alternative with costly reversal and unresolved evidence, review it first with the `council` skill when it is available, then send its recommendation and dissent with the question.

Credentials never travel through chat text. T3: request them with `request_secret`.

## Message contract

The person may read on a phone.

- Write the question, its body, and choice labels in {{PERSON_LANGUAGE}}. Quote an error or identifier in its original language only as evidence, and explain it.
- Make the question self-contained: the decision first, then the current state, the necessary context, and the consequence of every choice.
- Use short paragraphs and numbered lists. Keep choice labels short; when a label needs a sentence, number the choices and explain each number in the body.
- State one recommended choice with the evidence or risk behind it.

## Authority

Proceed only on an explicit, unambiguous answer authorizing the action. A timeout, a cancellation, a decline, ambiguous free text, a dismissed question, or a delivery failure grants no authority: take the safe path or block the affected item. A pending question does not stop independent work; defer only the work that strictly depends on the answer and record the blocker in the turn output.

A harness permission mode that skips prompts (T3 Auto or Full access, a bypass mode) controls which tool calls run without a prompt. It is not authority for the effects [`authority.md`](authority.md) classifies as needing a decision.

## No completion gate

Ending a run, a phase, a subtask, or a delegated task is never by itself a reason to ask. Report the outcome, the verification performed, and any remaining risk in the final response instead.

## Delegated children

A delegated agent (a subagent, or a T3 `delegate_task` child) has no direct person. It never asks the person and never calls a question tool. When it meets a human-only decision, it writes the question, the choices, and their consequences in its result, finishes the independent work, and ends. The parent owns every human decision and answers a child's pending request only when the answer is already authorized. A child's pending approval grants the parent no approval authority.

## Unattended runs

A run started by a scheduler (a T3 scheduled task, CI, cron) has no reachable person, even when it sends a notification at the end. In such a run:

- never call a question tool, never request an approval, and never wait for an answer;
- resolve in-scope, reversible technical matters autonomously;
- never invent approval; when an unapproved human-only decision appears, defer the dependent work, leave the repository consistent, continue independent work, and report the blocker and evidence in the final response;
- print the job's no-op marker exactly when the job defines one and nothing changed.
