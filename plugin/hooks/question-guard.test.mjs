// Contract tests for plugin/hooks/question-guard.mjs. The first question is the one an agent really asked.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { join } from "node:path";
import { test } from "node:test";
import { decide, identifiers } from "./question-guard.mjs";

const GUARD = join(import.meta.dirname, "question-guard.mjs");

const asked = {
	questions: [
		{
			header: "카드 이동",
			question:
				"`docsa tui`의 칸반에서 카드를 다른 열로 옮기면 그 concept의 lifecycle status를 실제로 수정하도록 할까요?\n\n1번을 고르면 frontmatter의 `status` 값만 바꾼 새 revision을 직접 저장 경로(ADR 0019, `saveConcepts`)로 저장합니다.",
			options: [
				{ label: "2. 읽기 전용 (Recommended)", description: "이번 PR은 표·칸반·열기만 제공합니다." },
				{ label: "1. 이동 시 status 수정", description: "frontmatter의 status 바이트만 바꿔 새 revision으로 저장합니다." },
			],
		},
	],
};

const plain = {
	questions: [
		{
			header: "카드 이동",
			question:
				"칸반에서 카드를 옆 열로 옮기면 그 문서의 상태가 실제로 바뀌게 할까요? 바뀌게 하면 키 한 번으로 모두에게 보이는 변경이 생기고, 같은 순간에 다른 사람이 저장한 내용을 덮어쓸 수 있습니다.",
			options: [
				{ label: "보기만 한다", description: "상태는 지금처럼 웹 편집기에서 바꿉니다.", preview: "draft | stable\n[faq]  |\n`saveConcepts`" },
				{ label: "옮기면 바뀐다", description: "옮긴 뒤 확인을 한 번 묻습니다." },
			],
		},
	],
};

const run = (payload) => spawnSync(process.execPath, [GUARD], { input: JSON.stringify(payload), encoding: "utf8" });

test("a question that names implementation identifiers goes back to the agent with those names", () => {
	const decision = decide(asked);
	assert.equal(decision.action, "deny");
	assert.match(decision.reason, /ADR 0019, saveConcepts/);
});

test("a question in the person's words is asked, and an option preview may show anything", () => {
	assert.deepEqual(decide(plain), { action: "allow" });
});

test("identifiers are code names, source files, ADR numbers, and calls; commands and plain words are not", () => {
	assert.deepEqual(identifiers("save_concepts in internal/api/api.go calls render() per ADR-0020"), ["save_concepts", "internal/api/api.go", "render()", "ADR-0020"]);
	assert.deepEqual(identifiers("`docsa tui` 명령과 status, PR #150, GitHub, v2.1.2"), []);
});

test("the hook denies through Claude Code's PreToolUse output and stays silent otherwise", () => {
	const denied = run({ tool_name: "AskUserQuestion", tool_input: asked });
	assert.equal(denied.status, 0);
	assert.equal(JSON.parse(denied.stdout).hookSpecificOutput.permissionDecision, "deny");
	assert.equal(run({ tool_name: "AskUserQuestion", tool_input: plain }).stdout, "");
	assert.equal(run({ tool_name: "Bash", tool_input: { command: "saveConcepts" } }).stdout, "");
});
