# 에이전트 설정과 패키징 결정

[문서 색인](index.md) · [English README](../README.md) · [한국어 README](../README.ko.md)

이 문서는 Claude Code 2.1.310, Codex CLI 0.164.0, Antigravity CLI(`agy`) 1.4.7의 설정·커스터마이즈 표면 가운데 Harness가 무엇을 어떤 형태로 배포하는지 정하고, 각 항목이 [T3 Code](https://github.com/pingdotgg/t3code) 안에서도 적용되는지 적습니다. 조사일은 2026-10-26이며, 근거는 공식 문서·변경 이력·설치된 바이너리와 그 `--help`, 공개 T3 Code 소스입니다. 문서와 바이너리가 다르면 바이너리를 따랐습니다. 관측 경위는 [FACTS 15절](FACTS.md#15-t3-code와-에이전트-설정-표면-2026-10-26)에 있습니다.

## 1. 배포 형태의 결정

스킬은 세 에이전트가 공통으로 읽는 기본 배포 단위입니다(`install.sh`가 `~/.agents/skills`와 `~/.claude/skills`에 연결합니다). 스킬로 표현할 수 없거나 에이전트별 제어가 필요한 것만 플러그인, 실행 정책, 설정 병합으로 배포합니다. 정본은 [`plugin/`](../plugin/) 하나이고, `plugin/build.mjs`가 에이전트별 산출물을 `${XDG_STATE_HOME:-~/.local/state}/harness/plugins/<host>/`에 만들며, `plugin/install.mjs`가 설치합니다.

| 항목 | 형태 | 이유 |
| --- | --- | --- |
| MR 수명주기(`file-mr`, `babysit-mr`, `leaving-mr-comments`, `takeover`, `modernize`), `review-loop`, `council`, `t3-orchestrate` | 스킬 | 세 에이전트가 같은 절차를 읽어야 하고, 다른 스킬이 이 스킬들을 부릅니다. |
| 작업 모드 `full-send`, `full-stop` | 사용자 호출 스킬(Claude `disable-model-invocation`, Codex `allow_implicit_invocation: false`) | 세 CLI 모두 스킬을 `/이름`이나 `$이름`으로 부릅니다. Claude 플러그인 명령은 `/harness:full-send`처럼 이름이 바뀌고, agy와 Codex 플러그인은 명령을 싣지 못합니다. |
| 머지 가드 | Claude·agy 플러그인 PreToolUse 훅, Codex `codex/harness.rules` | 아래 2절. 모드에 따라 판정이 달라지는 부분은 훅만 표현할 수 있습니다. |
| 읽기 전용 Claude 리뷰어 | Claude 플러그인 agent `harness:reviewer`(`tools: Read, Grep, Glob`) | 하위 agent의 `permissionMode`는 부모가 `bypassPermissions`·`auto`이면 무시되므로, 읽기 전용은 도구 목록으로만 강제됩니다. |
| agy 전역 규칙(`plugin/rules/AGENTS.md`) | agy 플러그인 `rules/` | 규칙을 플러그인으로 묶어 `agy plugin disable`로 끌 수 있게 합니다. |
| 자격 증명 읽기 금지 | `plugin/guardrails.json` → Claude·agy 설정의 `permissions.deny`에 합집합으로 추가 | 플러그인은 권한 규칙을 싣지 못합니다(Claude 플러그인 `settings`는 `agent`, `subagentStatusLine`만 받습니다). |
| Codex 플러그인 | 만들지 않음 | Codex 플러그인은 규칙·지침을 싣지 못하고, 플러그인 훅은 `config.toml`에 훅별 `trusted_hash`와 번들 `trusted_content_hash`를 기록해야 실행됩니다. 설치기가 그 해시를 계산해 사용자 설정에 쓰는 것은 코드를 묵시적으로 신뢰하는 일이므로, 같은 목적을 신뢰 절차 없이 이루는 실행 정책 파일을 씁니다. |

산출물 경로는 해시 없이 고정합니다. Claude Code는 디렉터리 마켓플레이스를 폴더에서 바로 읽으므로 다시 빌드하면 다음 세션부터 반영되고, agy는 `agy plugin install`이 사본을 만들므로 설치기가 차이가 있을 때만 다시 설치합니다. agy 1.4.7은 심링크한 플러그인 디렉터리를 건너뛰므로, 이전 설치기가 만든 `~/.gemini/config/plugins/harness` 심링크는 로드되지 않으며 설치기가 그 링크를 사본으로 바꿉니다.

## 2. 머지 가드와 작업 모드

작업 모드는 사람이 작업이나 스레드마다 고르는 층입니다. 모드를 고르지 않으면 [`hitl.md`](agents/hitl.md)와 [`authority.md`](agents/authority.md)가 그대로 적용되며, 머지는 사람이 그 머지를 명시적으로 결정해야 합니다.

| 모드 | 머지 가드의 판정 |
| --- | --- |
| 없음 | 막습니다. 사람이 특정 MR의 머지를 요청한 뒤 `harness-mode allow-merge <번호>`를 기록하면, 30분 안에 그 번호를 명시한 머지 명령 하나만 통과합니다. |
| `full-stop` | 항상 막습니다. |
| `full-send` | 머지 대상 저장소가 허용 목록에 있을 때만 통과합니다. 허용 목록에 없는 저장소에서는 `harness-mode`가 모드를 `full-stop`으로 낮춥니다. 대상 저장소를 명령에서 읽을 수 없는 GraphQL 머지는 막습니다. |
| 모든 모드 | `--admin`, 명령 연결·치환·`eval`, `GH_REPO`·`GH_HOST`·`GITLAB_HOST`·`--hostname` 같은 대상 변경, 서로 다른 저장소를 가리키는 인자는 항상 막습니다. |

허용 목록은 `${XDG_CONFIG_HOME:-~/.config}/harness/full-send-repos`이며 사람이 씁니다. 한 줄에 `<host>/<path>`(예: `github.com/<owner>/<repo>`) 하나나, 그 아래 모든 저장소를 뜻하는 `<host>/<owner>/*`를 적고 `#` 뒤는 주석입니다. 파일이 없거나 비어 있으면 `full-send`는 머지하지 않습니다. `skills/full-send/scripts/harness-mode`와 `plugin/hooks/merge-guard.mjs`가 같은 파일을 같은 정규화(스킴·사용자·포트·`.git` 제거, 소문자)로 읽으며, `plugin/hooks/merge-guard.test.mjs`가 두 쪽의 판정이 같은지 확인합니다. 머지 가드는 실행 시점에 허용 목록을 다시 읽으므로, 모드를 기록한 뒤 목록에서 지운 저장소도 막힙니다.

모드는 워크트리의 git 디렉터리(`harness-mode` 파일)에 기록됩니다. 에이전트도 이 파일과 허용 목록을 쓸 수 있으므로 이것은 실수로 머지하는 것을 막는 장치이지 권한 체계가 아닙니다.

| 에이전트 | 장치 | T3에서 | 실패 시 |
| --- | --- | --- | --- |
| Claude Code | 플러그인 `hooks/hooks.json`, `matcher: "Bash"`, `onFailure: "block"` | 적용됩니다. T3는 `settingSources`를 넘기지 않아 사용자 설정·플러그인·훅이 모두 로드됩니다. | 막습니다. 판독할 수 없는 입력도 머지 단어가 있으면 막고, 훅 내부 오류도 거부로 끝납니다. |
| agy CLI | 플러그인 루트 `hooks.json`, `matcher: "run_command"` | 적용되지 않습니다. T3는 agy CLI가 아닌 ACP 서버를 실행하며, 그 서버는 플러그인을 로드하지 않습니다. | CLI의 실패 동작은 문서에 없습니다. |
| Codex | `~/.codex/rules/harness.rules`의 `prefix_rule(..., decision="prompt")` | 적용됩니다. T3는 사용자 `CODEX_HOME`을 공유합니다. | 승인을 물을 수 있는 정책에서는 사람에게 묻고, `approval_policy = "never"`(T3 Full access)에서는 거부됩니다. 다른 규칙 파일의 넓은 `allow`보다 우선합니다. |
| T3 Antigravity | 없음 | 해당 없음 | 남은 위험입니다. ACP 서버는 프로필의 `config/hooks.json`을 읽고 PreToolUse 실패 시 막지만, 그 파일에 훅을 두면 `node` 경로 문제로 모든 명령이 막힐 수 있어 배포하지 않습니다. |

## 3. 설정 권장

아래는 Harness가 설치로 적용하는 항목과, 사용자가 자기 상태 파일에서 정할 권장입니다. 설치기는 "적용" 항목만 바꾸며 사용자 상태 파일의 다른 값을 편집하지 않습니다.

| 에이전트 | 설정 | 권장 | 근거 | T3 | 상태 |
| --- | --- | --- | --- | --- | --- |
| Claude Code | `permissions.deny`의 자격 증명 읽기 | `Read(~/.ssh/**)`, `Read(~/.aws/**)`, `Read(~/.claude/.credentials.json)`, `Read(~/.config/gh/**)`, `Read(~/.config/glab-cli/**)`, herdr-hitl 설정, agy OAuth 토큰, `Read(~/.t3/userdata/providers/**)` | deny는 `bypassPermissions`에서도 막습니다 | 예 | 적용 |
| Claude Code | PreToolUse 머지 가드 | 플러그인 훅, `onFailure: "block"` | 종료 코드 1, 시간 초과, 충돌은 기본적으로 통과(fail open)합니다 | 예 | 적용 |
| Claude Code | 읽기 전용 리뷰어 | `tools: Read, Grep, Glob` | 부모가 bypass·auto이면 하위 agent의 `permissionMode`가 무시됩니다 | 예 | 적용 |
| Claude Code | 머지 `ask` 규칙 | 쓰지 않음 | ask 규칙은 bypass에서도 사람에게 묻기 때문에 무인 `full-send`가 멈춥니다. 훅이 모드를 판단합니다 | 예 | 결정 |
| Claude Code | `sandbox.enabled` | 네트워크 허용 목록을 채운 뒤 켜기 | 빈 허용 목록은 `gh`·`glab`·`bun`을 깨뜨립니다 | 예 | 사용자 결정 |
| Claude Code | OpenTelemetry | 켜면 루프백 수집기만, 계정 속성 제거, console 내보내기 금지(T3의 stdout stream-json과 섞임) | `user.email`은 끌 수 없습니다 | 예(설정 `env`) | 사용자 결정 |
| Codex | 실행 정책 | `harness.rules`로 `gh pr merge`, `glab mr merge`를 `prompt` | `rules/`의 모든 `*.rules`를 읽고 더 엄격한 결정이 우선합니다. `codex execpolicy check`로 확인합니다 | 예 | 적용 |
| Codex | 플러그인·사용자 훅 | 머지 가드는 정책 파일로 대체 | 신뢰 해시가 없는 훅은 건너뜁니다 | 예 | 결정(1절) |
| Codex | `projects.*.trust_level` | 의도한 저장소로 좁히기 | 홈 디렉터리 전체를 신뢰하면 모든 하위 저장소의 설정이 적용됩니다 | 예 | 사용자 결정 |
| Codex | `sandbox_mode`, `approval_policy`, `network_access` | 단독 CLI는 workspace-write, on-request, `network_access=false` 명시 | 설정 스키마 | 부분(T3가 턴마다 덮어씀) | 사용자 결정 |
| Codex | `analytics.enabled`, `otel.metrics_exporter` | `analytics.enabled=false`, 메트릭은 none이나 루프백 OTLP | 메트릭 기본값이 외부 전송입니다 | 예 | 사용자 결정 |
| Codex | 사용자 정의 역할 | 읽기 전용 샌드박스는 역할로 만들 수 없으므로 리뷰어는 `codex/review.ts` | 역할은 샌드박스를 좁히지 못합니다 | 부분 | 결정 |
| agy | 플러그인 설치 | `agy plugin install`로 만든 사본 | 1.4.7은 심링크한 플러그인 디렉터리를 건너뜁니다 | 아니요 | 적용 |
| agy | 플러그인 머지 가드 | 루트 `hooks.json` | `agy plugin validate --strict` 통과 | 아니요 | 적용 |
| agy | `permissions.deny` | `~/.config/gh`, `~/.config/glab-cli`, `~/.claude/.credentials.json`, `~/.t3/userdata/providers` 읽기 금지 | `action(target)` 문법, Deny > Ask > Allow | 아니요(ACP 설정에는 권한 항목이 없음) | 적용 |
| agy | `toolPermission`, `trustedWorkspaces` | 대화형은 `auto`나 `proceed-in-sandbox`, `$HOME`·`/tmp`를 신뢰 목록에서 빼기 | 권한 문서 | 아니요 | 사용자 결정 |

## 4. T3 Antigravity 세션이 받는 것

T3는 agy CLI가 아니라 고정된 ACP 서버를 T3 전용 `GEMINI_HOME`으로 실행합니다. 이 서버는 `config/skills`, `config/hooks.json`, `config/mcp_config.json`만 읽고 규칙과 플러그인을 로드하지 않습니다. 따라서 Antigravity 자식과 카운슬 위원에게는 필요한 규칙을 브리프에 직접 적습니다(`council`의 `references/member-brief.md`, `t3-orchestrate`의 `references/targets.md`). 무인 Antigravity 예약 작업도 프롬프트에 [`hitl.md`](agents/hitl.md)의 경로를 직접 적어야 합니다.

## 5. 가드레일 결정 기록

| 결정 | 방향 | 적용 |
| --- | --- | --- |
| Claude·agy 설정에 자격 증명 읽기 금지 추가(`plugin/guardrails.json`) | 강화 | 설치 시 합집합 추가, 처음 한 번 `.harness-bak` 백업 |
| Codex에서 `gh pr merge`, `glab mr merge`를 `prompt`로 | 강화 | `install.sh`가 `~/.codex/rules/harness.rules`를 연결 |
| 모드 없는 머지 차단, `full-stop` 머지 차단, `--admin` 차단 | 강화 | Claude·agy 플러그인 훅 |
| `full-send`의 머지 허용 | 사람이 쓴 허용 목록의 저장소로 한정하며, 목록이 없으면 허용하지 않음 | 훅이 저장소와 명령 대상을 실행 시점에 확인 |
| 권한을 넓히는 변경 | 없음 | — |

설정 파일에서 규칙을 빼는 변경과 위 표의 "사용자 결정" 항목은 사람이 정합니다.
