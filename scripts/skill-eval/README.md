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

## 설명 기반 라우팅 검사

[`route.ts`](route.ts)는 "스킬 설명만 보고 어느 스킬을 고르는가"를 검사합니다. 사례 파일의 후보 스킬마다 `skills/<name>/SKILL.md`의 frontmatter `description`을 읽고, 프롬프트마다 분류 호출을 한 번 보내 스킬 이름이나 `none` 하나를 받습니다. 스킬을 로드하거나 에이전트가 실제로 스킬을 발동하는지는 관찰하지 않으며, 보고서 첫머리에도 이 범위를 적습니다.

- 사례 파일은 [`routing/`](routing/)에 둡니다. 첫 파일 [`routing/design.json`](routing/design.json)은 디자인 스킬 여덟 개(`awesome-interface`, `design-md`, `make-font`, `make-logo`, `imagegen`, `image-to-code`, `diagram-design`, `awesome-slides`) 사이의 충돌 사례를 한국어와 영어 프롬프트로 담습니다. 스킬마다 `should_fire`(그 스킬로 가야 할 프롬프트)와 `should_not_fire`(`goes_to`에 적은 다른 스킬이나 `none`으로 가야 할 프롬프트)를 둡니다. 같은 프롬프트를 여러 곳에 적으면 기대값이 모두 같아야 하며, 분류 호출은 한 번만 합니다.
- 설명은 작업 트리가 아니라 커밋(`--ref`, 기본값 `HEAD`)에서 읽고, `scripts/check-repo.ts`의 `checkFrontmatter`가 거부하는 frontmatter는 같은 메시지로 거부합니다.
- 분류 호출은 실행마다 새로 만든 빈 임시 디렉터리에서 도구, 스킬, 슬래시 명령, MCP 서버 없이 `claude -p`로 보내며, 시스템 프롬프트는 라우터 지시 한 문장으로 바꿉니다. 인자는 Claude Code 2.1.329의 `claude --help`와 실행 파일로 확인했습니다.
  - `--safe-mode`는 로그인을 유지한 채 `CLAUDE.md`, 자동 메모리, hook, 플러그인 같은 사용자 맞춤 설정을 끕니다. 따라서 전역 `CLAUDE.md`의 import가 작업 트리 텍스트를 분류 맥락에 넣지 못하고, Stop hook이 턴을 더 요청하지 못합니다.
  - `--setting-sources ""`는 사용자, 프로젝트, 로컬 설정 파일을 읽지 않게 합니다.
  - safe mode에서도 내장 플러그인은 남습니다. 그중 `AGENTS.md`를 맥락에 넣는 `cc-plugin-agents-md`는 `--settings`의 `enabledPlugins`로 끕니다. 스킬만 제공하는 내장 플러그인은 `--disable-slash-commands`로 스킬이 꺼지므로 그대로 둡니다.
  - `--max-turns 1`은 호출을 한 턴으로 제한합니다. 이 플래그는 2.1.329의 `--help`에 나오지 않지만 실행 파일이 받아들이므로, Claude Code를 올린 뒤에는 `--dry-run`으로 보낼 인자를 다시 확인합니다.
  - 한계: 관리자가 배포한 정책 설정(managed settings)과 관리 플러그인의 hook은 `--safe-mode`에서도 적용되며, 이를 끄는 플래그는 없습니다. 그래서 실제 실행은 `managed-settings.json`이나 숨김 파일이 아닌 `managed-settings.d/*.json`에 hook이나 `policyHelper`가 있으면 모델을 부르기 전에 거부합니다. 목록을 읽거나 파일을 읽거나 해석할 수 없을 때(없는 경우는 제외)도 거부합니다. `--bare`는 이것까지 줄이지만 OAuth 로그인을 읽지 않으므로 쓰지 않습니다. Team·Enterprise 로그인은 서버가 관리하는 정책(server-managed settings)으로 hook을 받을 수 있는데, 이 실행기는 그 정책을 보거나 끌 수 없습니다. 그래서 결과는 서버 관리 정책이 없는 개인 로그인에서 실행했다는 가정 아래에서만 설명 기반 점수이며, 보고서 머리의 범위 문장이 이 가정을 적습니다.
- 답은 다섯 가지로 채점합니다: `correct`(기대한 답), `wrong`(다른 후보 스킬), `none`(스킬을 기대했는데 `none`), `malformed`(후보 이름이나 `none`이 아닌 답), `failed`(호출이 답 없이 끝남). 모두 `correct`일 때만 종료 코드가 0입니다.

```bash
# 보낼 요청만 출력하고 모델을 부르지 않습니다
mise run skill-route -- --dry-run

# 실제 실행: 프롬프트마다 유료 모델 호출이 한 번 일어납니다 (var/skill-eval/route/<suite>/run-<시각>/)
mise run skill-route
mise run skill-route -- --model claude-opus-5-5 --ref HEAD~1
```

같은 출력 위치와 같은 시각(초 단위)으로 실행 디렉터리가 이미 있으면 그 실행은 시작하지 않고 실패합니다. 결과 디렉터리에는 `report.md`(기대 답별 정답 수, 한국어와 그 밖의 프롬프트별 정답 수, 기대와 다르게 간 프롬프트 표), `results.json`, 호출별 `transcripts/`가 남습니다. 이 task는 `mise run check`와 CI에 들어 있지 않습니다. 설명을 고친 전후를 비교하려면 같은 모델로 `--ref`만 바꿔 두 번 실행하고 두 `report.md`를 나란히 봅니다.

## 테스트

```bash
node --test 'scripts/skill-eval/**/*.test.ts'
```

`route.test.ts`는 임시 저장소와 가짜 에이전트로 라우팅 실행기와 채점을 검사하며, 모델을 부르지 않습니다.
