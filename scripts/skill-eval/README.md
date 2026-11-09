# skill-eval

스킬 하나를 기준선(스킬 없음)과 다른 스킬들에 견주어 같은 과제로 반복 비교하는 실행기와 채점기입니다. 스위트 형식, 산출물 배치, 채점 결과 형식은 [`lib/schema.ts`](lib/schema.ts)가 소유합니다. 첫 스위트는 `awesome-interface`와 `emilkowalski/skills`의 스킬 16개를 비교하는 [`skills/awesome-interface/evals/compare/`](../../skills/awesome-interface/evals/compare/)이며, 사례 설계와 심은 결함은 그 디렉터리의 `CASES.md`에 있습니다.

## 준비

- `claude`(평가받는 에이전트), `codex`(판정자), `uv`(Playwright 렌더)가 PATH에 있어야 합니다. Chromium은 `uv run --with playwright`가 쓰는 Playwright 캐시에 있어야 합니다.
- 평가받는 세션은 현재 사용자의 Claude Code 설정(전역 `CLAUDE.md`, 플러그인, 거부 규칙)을 그대로 씁니다. 이 환경은 모든 arm에 같게 적용됩니다. effort는 `--effort`로 명시해야 `meta.json`에 실제 값이 남습니다.
- 평가받는 세션은 `bypassPermissions`로 `/tmp/skill-eval/` 아래 작업공간에서 실행됩니다. 실행 비용은 Opus 기준으로 세션 하나에 약 $0.1~$1.1입니다.

## 실행과 채점

```bash
# 실행 계획만 보기
node scripts/skill-eval/run.ts --suite skills/awesome-interface/evals/compare/suite.json --effort high --dry-run

# 새 iteration 실행 (var/skill-eval/<suite>/iteration-<n>/)
node scripts/skill-eval/run.ts --suite skills/awesome-interface/evals/compare/suite.json --effort high

# 채점: 기계 검사, 화면 캡처, Codex 블라인드 판정, benchmark.md, viewer.html
node scripts/skill-eval/grade.ts --iteration-dir var/skill-eval/awesome-interface-compare/iteration-<n>
```

- 일부만 돌리려면 `--case <id,...>`, `--arm <key,...>`를 씁니다. 중단된 iteration은 `--iteration <n>`으로 이어 가며, 이미 끝난 run은 건너뜁니다.
- 결과는 `benchmark.md`(arm별 요약, `ai` 기준 비교, case별 표, 한계)와 `viewer.html`(case별로 arm의 화면·응답·diff·판정을 나란히 보기)에서 봅니다. `var/`는 버전 관리하지 않습니다.

## 스킬을 고친 뒤 다시 비교하기

1. 스킬 변경을 커밋합니다. 로컬 스킬은 작업 트리가 아니라 커밋에서 읽습니다.
2. 새 iteration을 실행합니다. 판정은 한 iteration 안의 arm들만 비교하므로, 바뀐 arm과 비교할 arm을 함께 실행합니다. 예: `--arm none,ai --ref ai=<새 커밋>`. 고치기 전과 후의 스킬을 같은 판정 안에서 비교하려면 스위트에 `ref`를 고정한 arm(예: `"ai-prev": {"skills": [{"source": "local", "path": "skills/awesome-interface", "ref": "<이전 커밋>"}]}`)을 추가하고 `version`을 올립니다.
3. 이전 iteration과 같은 `--effort`, 같은 모델로 실행하고, 두 iteration의 `benchmark.md`를 나란히 봅니다. 판정은 한 번의 단일 판정이므로, 작은 차이는 `--runs`를 늘려 다시 확인합니다.

스위트를 바꾸면 `version`을 올리고 새 iteration에서 실행합니다. 이어 가는 iteration은 처음 실행한 `suite.json`과 다르면 실행을 거부합니다.

## 테스트

```bash
node --test 'scripts/skill-eval/**/*.test.ts'
```
