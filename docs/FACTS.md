# 하네스 통합 레포의 확인된 사실

이 문서는 공개 가능한 기술 관측과 그 한계를 기록합니다. 날짜가 있는 관측은 다른 버전이나 호스트의 성능 보장이 아닙니다. 퇴역한 에이전트 런타임과 벤치마크 러너에만 해당하던 기록은 지웠으며, 그 소스는 [`archived/`](../archived/)에 보존되어 있습니다.

## 1. 도구 가용성

- 현재 설치·설정의 정본은 [설치 안내](guides/installation.md)입니다.
- Bun 1.3.14가 Bun 테스트, Codex 리뷰어, T3 예약 작업 guard, host-sync의 기준 환경입니다.
- Python 3 표준 라이브러리는 cost-audit 분석기와 collector에 사용됩니다. `sqlite3`나 `jq` CLI가 모든 실행 환경에 있다고 가정하지 않습니다.
- 네이티브 Windows와 macOS는 설치 대상으로 확인하지 않았습니다. WSL2의 BrowserSkill 연결 검증은 전체 Windows 설치 지원과 별개입니다.

## 2. 로컬 데이터 원천과 개인정보 경계

Claude Code의 `~/.claude/projects`와 Codex의 `~/.codex/sessions`에 있는 세션 JSONL에는 대화, 도구 인자와 결과, 모델 변경, 압축 상태, usage가 저장됩니다. Subagent 기록은 별도 파일로 나뉠 수 있습니다. cost-audit 분석기는 이 로그를 읽어 main·subagent usage를 구분하지만, 로그 원문은 공개 산출물이 아닙니다.

프롬프트 본문을 제외한 집계라도 작업 폴더, 모델 사용 패턴, 시간대, 비용을 통해 개인 활동을 드러낼 수 있습니다. 원본 row나 folder별 집계를 공개 문서·fixture로 복사하지 않습니다.

## 3. 공개 하네스 자산과 통합 관측

- `skills/`는 personal/adopted skill source이고, `third-party/adopted-skills.json`은 provenance를 기록합니다. 외부 manager-owned skills는 public pins만 `third-party/skills.lock.json`에 남깁니다.
- `t3/scheduled/jobs.json`은 의도적으로 비어 있습니다. Guard와 host-sync source가 존재한다는 사실은 scheduled job이 installed 또는 enabled라는 뜻이 아닙니다.
- `agy/settings.snapshot.json`의 permissive policy는 personal example입니다. File-tool permission rules는 arbitrary shell access를 막는 sandbox가 아닙니다.

### BrowserSkill on WSL2

2026-09-21에 Linux x64 `bsk 0.3.0`과 Windows Chrome 152의 BrowserSkill extension 0.3.0을 확인했습니다. WSL loopback의 기본 port 52800에서 daemon protocol 1.3과 extension protocol 1.3이 연결됐고, `bsk doctor --json`은 manager-owned `codex`·`claude-code` skill을 포함해 `fail`이나 `warn` 없이 통과했습니다.

CLI session은 `https://example.com`을 열어 “Example Domain”과 documentation-use 설명을 관찰한 뒤 중지됐습니다. 이는 해당 WSL2/Windows Chrome 조합의 local connection과 skill discovery를 확인한 결과이며 다른 network mode나 future release의 보장이 아닙니다.

### AGY print mode

AGY의 print mode는 process cwd와 별도의 workspace를 선택할 수 있으므로 automation은 작업 directory를 명시해야 합니다. Model UI display name과 `--model` ID의 형식도 같다고 가정하지 않습니다.

## 4. awesome-interface 편입과 검증 (2026-09-09)

`awesome-interface`는 한 개의 `SKILL.md`, 여섯 전문 영역, 다섯 작업 절차, 공통 리뷰 양식으로 구성됩니다. [Jakub Krehel의 skills](https://github.com/jakubkrehel/skills/tree/267330e1adfc66a718fb65fa6918c1f06d0a689e)와 [make-interfaces-feel-better](https://github.com/jakubkrehel/make-interfaces-feel-better/tree/35545ea1512ad59fa463e6b1f95ca9c052981fe6)의 MIT 자료를 선별·재구성했습니다. 라이선스를 확인하지 못한 `oklch-skill`의 고유 콘텐츠는 복사하지 않았습니다. 입력 revision·해시·고지와 변경 경계는 `third-party/adopted-skills.json`의 개별 항목에 있습니다.

`openai-codex/gpt-6-astra:low`로 합성 입력 10개와 기존 설치본 비교 3개를 실행했습니다. 후보의 문구 수정은 writing만, 버튼 이름 수정은 accessibility와 writing을 읽었고, 전체 검토는 여섯 영역을 모두 읽었습니다. 수정 도구가 제공된 리뷰 사례도 fixture를 변경하지 않았습니다. backend 타입 설명과 문자열 배열 요청은 UI 스킬이나 특수 모드를 호출하지 않았습니다. 변경 리뷰는 이름 제거를 HIGH 회귀로 분류했습니다. 스트레스·대안·설명 사례는 요청된 계획·근거 경계를 확인했으며, 실제 대안 앱 생성이나 외부 사이트 분석까지 검증한 것은 아닙니다.

초기 이름·설명 문자열은 나머지 설치 스킬을 동일하게 유지한 조건에서 8,790자에서 8,241자로 줄었습니다. 표시 항목은 36개에서 30개로 줄었으며 이 중 UI 영역은 7개에서 1개로 바뀌었습니다. 각 사례 1회뿐이고 작은 요청의 라우터 읽기 비용도 있어, 전체 토큰·비용·호출 정확도가 개선됐다고 주장하지 않습니다. 최초 평가 실행은 discovery 함수에 스킬의 부모 디렉터리 대신 스킬 디렉터리를 넘겨 후보를 찾지 못했습니다. 해당 결과를 제외하고, 실제 후보 노출을 검사하도록 고친 평가기로 위 13개 실행을 다시 수행했습니다.

합성 fixture의 후보 출력은 Chromium에서 별도로 확인했습니다. 320px에서 이름이 있는 닫기 버튼과 가시적 포커스, Tab·Enter 활성화, 넘침 없음을 확인했고, 데스크톱에서 수정된 복구 문구와 키보드 저장 활성화를 확인했습니다. 자동화 click helper는 보이는 버튼에서도 timeout이 발생해 키보드 경로로 검증했습니다. 스크린리더 발화·200% 확대·포인터 자동화 성공을 주장하지 않습니다.

독립적인 Claude 계열 제한 리뷰어가 세 구현 슬라이스를 검토했고 blocking은 없었습니다. 확인된 보완 사항인 색상 외 상태 단서, 규칙 중복, 대안 preview의 수명, 스트레스 증거 보존은 통합 시 반영했습니다. 구조 검사에서는 단일 스킬 진입점, 105개 로컬 Markdown 링크, 두 MIT 출처와 10개 평가 입력이 확인됐습니다. 평가 입력은 `skills/awesome-interface/evals/`에 있으며 실제 응답·비교 화면·캡처는 배포하지 않습니다.

## 5. 스킬 description 축소와 git-commit 편입 (2026-09-09)

4절 이후 설치 스킬 전체를 단일 진입점·내부 라우팅 후보로 다시 조사했습니다. 추가 통합 후보는 소유권(관리형·CLI 제공)이나 작업 단위 차이로 채택하지 않았고, 라우팅보다 description 길이가 더 큰 상시 비용이었습니다.

`daily-report`, `code-review`, `diagnosing-bugs`, `tdd`, `writing-for-agents`의 description을 트리거 조건만 남기도록 줄였고 본문은 바꾸지 않았습니다. `diagnosing-bugs`와 `tdd`는 "원인 미상"과 "원인이 테스트 환경으로 확인됨"으로 간헐 실패 트리거를 나눴고, `writing-for-agents`는 `skill-creator`와 겹치던 "creating or editing skills"를 제거했습니다. `git-commit`은 [github/awesome-copilot](https://github.com/github/awesome-copilot/tree/7568a482ce2df38f8965ab5336a3220db796a4ba)(MIT)에서 편입하고 `third-party/adopted-skills.json`에 이전 등록·입력 해시·로컬 변경을 기록했습니다.

같은 로더로 같은 설치 목록을 읽은 조건에서 가시 이름·설명 문자 수는 8,241자에서 6,554자로 줄었습니다(항목 30개 동일). 라우팅 프로브는 `openai-codex/gpt-6-astra:low`, 도구 read/glob/grep, 빈 합성 작업 디렉터리에서 긍정 13·부정 7 프롬프트를 각 1회 실행했고 기준선과 후보 모두 20/20 통과했습니다. 각 사례 1회이므로 호출 정확도의 통계적 개선이나 전체 토큰·비용 절감을 주장하지 않습니다. 제한 SDK 리뷰어(다른 모델 계열) 1회차에서 blocking은 없었고 nit 4건을 반영했습니다.

## 6. T3 Code와 에이전트 설정 표면 (2026-10-26)

T3 Code v0.1.2 데스크톱 앱(WSL 백엔드), Claude Code 2.1.310, Codex CLI 0.164.0, Antigravity CLI(`agy`) 1.4.7과 공개 T3 Code 소스로 확인한 관측입니다. 실험은 임시 `HOME`·`CODEX_HOME`·`CLAUDE_CONFIG_DIR`에서 했고, 모델 요청은 닫힌 로컬 포트로 보냈으며, 끝난 뒤 지웠습니다. 결정과 권장 값은 [AGENT-CONFIG](AGENT-CONFIG.md)가 소유합니다. 버전이 바뀌면 다시 확인해야 합니다.

### 제공자별 로드 경계

- Codex: `codex debug prompt-input "hi"`(모델 호출 없음)의 스킬 목록 루트가 `~/.agents/skills`였고, 작업 디렉터리의 `AGENTS.md`도 들어 있었습니다. T3는 사용자 `CODEX_HOME`의 설정·훅·플러그인·규칙을 공유하고 모델·권한 설정만 턴마다 덮어씁니다(`provider/Drivers/CodexHomeLayout.ts`, `orchestration-v2/Adapters/CodexAdapterV2.ts`).
- Claude Code: T3가 띄운 `claude` 프로세스의 인자에 `--setting-sources`가 없었고 어댑터도 `settingSources`를 넘기지 않습니다(`orchestration-v2/Adapters/ClaudeAdapterV2.ts`). SDK 기본값은 user·project·local이므로 사용자 훅, 권한 규칙, 플러그인, agent, `CLAUDE.md`가 T3 세션에 적용됩니다.
- Antigravity: T3는 agy CLI가 아니라 고정된 ACP 서버를 T3 전용 `GEMINI_HOME`에서 실행합니다(`provider/antigravityRelease.ts`). 그 디렉터리의 `config/`에는 `skills → ~/.gemini/config/skills` 링크만 있고, ACP 서버는 `config/skills`, `config/hooks.json`, `config/mcp_config.json`을 읽으며 규칙과 플러그인 항목이 없습니다. Flash 자식에게 고유한 제목을 인용하게 하자 호스트 `~/.gemini/config/rules/AGENTS.md`와 워크트리 `AGENTS.md`는 보이지 않았고 스킬 목록은 보였습니다. 프로필에 `config/rules` 링크를 임시로 둔 뒤에도 규칙은 보이지 않았습니다.
- 예약 작업: `schedule_task`에는 모델 인자가 없고, 작업은 만든 스레드의 모델 선택과 실행 모드를 저장합니다. 스레드에 묶지 않은 작업은 실행마다 새 스레드와 `origin`의 기본 브랜치에서 만든 새 워크트리를 씁니다. `fixed_time`은 환경 시간대로 계산하고 10분 넘게 늦은 실행은 건너뜁니다. 작업에는 시간 초과, 일일 실행 횟수, 연속 실패 시 중지가 없습니다.
- T3 Usage 화면은 LiteLLM 단가 문서를 `~/.t3/userdata/usage-model-rates.json`에 내려받고 `~/.claude/projects`와 `~/.codex/sessions`를 스캔합니다.

### 플러그인과 훅

- agy: 임시 `HOME`에서 `agy plugin list --json`은 사본으로 둔 플러그인 디렉터리를 보여 주었지만 저장소를 가리키는 디렉터리 심링크는 보여 주지 않았습니다. `plugin.json`과 `rules/`만 심링크인 실제 디렉터리는 보였습니다. `agy plugin install <dir>`은 같은 이름을 덮어쓰고 `uninstall`은 사본을 지웁니다.
- Codex 훅: 로컬 마켓플레이스 플러그인과 사용자 `hooks.json`에 같은 `SessionStart` 훅을 두었을 때 두 훅 모두 실행되지 않았습니다. 0.164.0은 `config.toml`의 `[hooks.state."<키>"] trusted_hash`(플러그인은 `trusted_content_hash`도)가 없는 훅을 건너뜁니다. 신뢰 항목을 넣은 별도 실험에서는 두 훅이 실행되었습니다.
- Codex 실행 정책: `codex execpolicy check`에 기본 규칙 파일과 `codex/harness.rules`를 함께 주자 `glab mr` 아래의 머지 하위 명령은 `prompt`, `glab mr view 5`는 `allow`였습니다. 기본 규칙에는 `prefix_rule(["glab","mr"], allow)`가 있었습니다. Codex는 `rules/`의 모든 `*.rules`를 읽고, 더 엄격한 결정이 우선하며, `approval_policy = "never"`에서 `prompt`를 거부로 바꿉니다.
- Claude Code 플러그인: 임시 `CLAUDE_CONFIG_DIR`에서 `plugin/build.mjs` 산출물을 디렉터리 마켓플레이스로 등록하고 설치하자 `claude plugin list --json`이 `readFromFolder`로 산출물 경로를 보고했고 agent 1개(`reviewer`)와 PreToolUse 훅 1개가 보였습니다. 버전을 올리지 않고 폴더를 고치면 다음 세션부터 반영됩니다.
- GitLab MR 감시: T3는 GitLab MR을 `glab` REST로 2분마다 읽고, head 파이프라인 하나를 `Pipeline` 검사로 보며, 시스템 note를 이벤트에서 빼므로 승인은 스레드를 깨우지 않습니다(`packages/source-control-gitlab/src/shared/definition.ts`, `gitLabMergeRequestJson.ts`). 기존 GitLab MR 하나에 연결·감시·해제가 동작했고, 감시가 실제 이벤트로 스레드를 깨우는 것은 관찰하지 않았습니다.
