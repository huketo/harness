# Harness

[English](README.md) · [한국어](README.ko.md)

**공유 스킬, T3 Code 통합, 가드레일, 보호된 자동화를 버전 관리하는 개인용 코딩 에이전트 워크스테이션 설정입니다.**

Harness는 에이전트를 Claude Code, Codex CLI, Antigravity CLI(`agy`) 기반의 스레드로 실행하는 기존 [T3 Code](https://github.com/pingdotgg/t3code) 워크스테이션을 구성합니다. Harness는 독립 에이전트나 호스팅 서비스, 이 도구들의 대체품이 아니라 개인 설정과 확장을 공개하는 쇼케이스입니다. [Herdr](https://github.com/herdrdev/herdr)는 사람이 지켜보는 터미널 작업을 위한 일반 터미널 멀티플렉서로만 남아 있습니다. 은퇴한 Herdr 에이전트 런타임, Oh My Pi, 벤치마크 소스는 [`archived/`](archived/)에 동결해 두었으며, 어떤 설치나 실행도 이 소스를 사용하지 않습니다.

[설치](docs/guides/installation.md) · [문서](docs/index.md) · [사용법](docs/guides/usage.md) · [재사용 정책](CONTRIBUTING.md) · [MIT 라이선스](LICENSE)

## 추가되는 기능

| 기능 | 제공 내용 |
| --- | --- |
| 공유 스킬 | 저장소 소유 지침을 Claude Code·Codex·AGY에 연결합니다. 편입 자료의 원저작자 고지는 유지합니다. |
| UI 디자인 작업 | 일반 UI 제작·검토, 이미지 기반 웹 구현, UI·브랜드 참조 이미지 생성, 선택적 설계 문서를 네 스킬로 구분합니다. 이미지·문서 생성은 필수 단계가 아닙니다. [사용법](docs/guides/usage.md)을 참고하세요. |
| T3 Code 경로 | `t3-orchestrate`, `review-loop`, `council`이 T3의 오케스트레이션 도구로 작업을 위임합니다. `t3-handoff`는 인계 문서를 첫 메시지로 받는 새 스레드에서 작업을 이어 갑니다. [T3 사람 개입 규칙](docs/agents/hitl.md)이 질문을 스레드로 보내고, `codex/review.ts`가 Codex의 읽기 전용 샌드박스에서 독립 리뷰를 실행하며, `t3/scheduled/guard.mjs`가 예약 작업에 시간 초과와 실행 횟수 제한을 더합니다. |
| 지켜보는 터미널 작업 | `t3-terminal`이 개발 서버, 대화형 프롬프트, REPL, ssh, TUI처럼 사람이 지켜보거나 직접 입력해야 하는 작업을 Herdr의 workspace·tab·pane에 엽니다. 백그라운드 프로세스를 대신하지는 않습니다. |
| MR 수명주기와 작업 모드 | tstack에서 편입한 GitLab MR·GitHub PR 스킬(`file-mr`, `babysit-mr`, `leaving-mr-comments`, `takeover`, `modernize`)과 사람이 고르는 `full-send`·`full-stop` 모드를 제공합니다. Claude Code·AGY용 `plugin/` 산출물의 머지 가드 훅과 Codex용 `codex/harness.rules`가 모드가 허락하지 않는 머지를 막으며, `full-send`는 사람이 허용 목록에 적은 저장소에서만 머지합니다. [AGENT-CONFIG](docs/AGENT-CONFIG.md)를 참고하세요. |
| 개인 운영 | Claude Code·Codex 세션의 비용 감사, 보호된 호스트 동기화, 사람이 검토하는 일일보고 초안 흐름을 제공합니다. 호스팅 서비스가 아닙니다. |

## 권장 환경

유지하는 쇼케이스 대상은 **Bash와 GNU 호환 유틸리티를 갖춘 Linux 또는 WSL2와 Bun 1.3.14**입니다. 전체 설치의 플러그인 단계에는 Node.js가 필요하고, Bun은 예약 작업 가드, 호스트 동기화, Codex 리뷰어를 실행하며, Python 3는 비용 감사 분석기와 스킬 수집기를 실행합니다. 현재 설치기는 기존 `~/.claude/CLAUDE.md`를 요구합니다. T3 Code, Claude Code, Codex CLI, AGY의 설치·인증은 별도로 준비합니다. 네이티브 Windows와 macOS는 유지하는 설치 대상이 아닙니다. 앞으로 나올 에이전트 CLI나 Bun 버전의 호환성은 검토 없이 가정하지 않습니다.

```bash
git clone https://github.com/huketo/harness.git
cd harness
bash install.sh --dry-run
```

[설치 안내](docs/guides/installation.md), 소스, 워크스테이션 변경 계획을 검토한 뒤 진행합니다.

```bash
bash install.sh
```

**설치는 워크스테이션을 변경합니다.** 공유 자산을 연결하고, 교체 가능한 기존 설정 파일을 백업하며, Claude Code와 AGY가 `PATH`에 있으면 `harness` 플러그인을 설치하고 두 도구의 설정 파일에 자격증명 읽기 거부 규칙을 더하며, Codex 실행 정책 파일을 연결합니다. 다른 곳을 가리키거나 예상과 다른 항목은 충돌로 남기고 제거하지 않습니다. Dry-run은 변경 없이 계획만 보여 줍니다. 현재 스킬을 불러오도록 설치 후 새 에이전트 세션을 엽니다. 이전 버전의 설치기가 `archived/`로 옮긴 구성 요소에 만든 링크는 제거하지 않으므로 [수동 복원 범위](docs/guides/installation.md#updating-and-undoing)를 확인합니다. 설치기는 AGY 설정과 T3 예약 작업을 복원하지 않습니다.

공유 워크스테이션에서는 `bash install.sh --skills-only`로 스킬만 연결하고 도구 설정과 명령은 유지할 수 있습니다. 체크아웃 경로를 고정하고 `bash /path/to/harness/update.sh --skills-only`를 실행하면 깨끗한 `main`을 fast-forward한 뒤 다시 설치합니다. 설치 링크에는 변경이 즉시 반영되므로 먼저 업데이트를 검토합니다. [설치와 갱신 경계](docs/guides/installation.md)를 참고하세요.

## 일상적인 사용

에이전트는 T3 Code 스레드로 실행합니다. 스레드에서 `t3-orchestrate`는 독립 작업을 워크트리 자식에게 나누고, `review-loop`와 `council`은 다른 모델 계열의 읽기 전용 리뷰를 실행하며, MR 스킬(`file-mr`, `babysit-mr`, `takeover`, `modernize`)은 GitLab MR과 GitHub PR을 처리합니다. 질문과 승인은 [사람 개입 규칙](docs/agents/hitl.md)에 따라 스레드에서 주고받습니다.

사람이 지켜보거나 직접 입력해야 하는 터미널 작업은 `t3-terminal`로 보냅니다. 자신의 터미널에서 `herdr`를 실행해 그 화면에 붙으면 진행을 확인하거나 직접 입력할 수 있습니다. 짧은 조회·빌드·테스트와 백그라운드 프로세스는 평소 도구로 실행합니다.

모델을 호출하지 않고 독립 Codex 리뷰어의 경계를 확인합니다.

```bash
bun --no-install codex/review.ts --cwd <worktree> --inspect-tools
```

[상세 사용법과 상태 경계](docs/guides/usage.md)를 참고하세요. 날짜가 있는 측정값은 [FACTS](docs/FACTS.md)에, 과금 근거는 [PRICING](docs/PRICING.md)에 있으며, 둘 다 관측일 뿐 성능 보장이 아닙니다.

## 설정과 안전 경계

- **자산별 정본 하나:** 사람이 관리하는 자산은 심링크하고, 도구가 관리하는 상태는 해당 도구에 둡니다. 배포된 스냅샷은 검토용 예시이며 호스트 백업이나 복원 지침이 아닙니다.
- **자격증명은 로컬에 유지:** API 키, OAuth 상태, 비공개 캘린더 URL, 메신저 토큰, 세션 로그, 보고서 입력은 버전 관리 밖에 둡니다. `.gitignore`는 비밀 탐지기가 아니며 과거 이력을 지우지 않습니다.
- **외부 영향 검토:** T3 예약 작업 활성화, 메시지 전송, 플러그인 업데이트, 원격 쓰기, 머지, Git 게시는 유지관리자가 의도적으로 실행해야 합니다. 머지 가드는 실수로 머지하는 것을 막는 장치이지 권한 체계가 아닙니다. 배포된 스냅샷을 그대로 활성화하지 않습니다.
- **샌드박스가 아님:** 권한 정책과 파일 도구 deny 규칙은 임의 셸 접근을 격리하지 않습니다. 허용적인 워크스테이션 설정은 개인의 위험 선택이지 보안 기본값이 아닙니다.
- **링크는 즉시 반영:** 이 체크아웃을 수정하거나 갱신하면 설치된 자산도 바로 바뀝니다. 자동 제거기는 없으며, 링크 제거만으로 되돌릴 수 없는 변경은 [수동 복원 범위](docs/guides/installation.md#updating-and-undoing)에 설명합니다.

## 디렉터리 안내

| 경로 | 역할 |
| --- | --- |
| [`skills/`](skills/) | 개인 스킬과 원저작자 고지를 유지한 편입 스킬. |
| [`plugin/`](plugin/) | Claude Code·AGY 플러그인의 단일 정본. 머지 가드, 읽기 전용 리뷰어 agent, AGY 규칙, 빌더, 설치기, 거부 규칙. |
| [`codex/`](codex/) | 읽기 전용 Codex 리뷰어와 머지 전에 승인을 묻게 하는 Codex 실행 정책. |
| [`t3/`](t3/) | T3 Code 예약 작업 가드와 보호된 호스트 동기화. 배포한 작업 목록은 비어 있습니다. |
| [`agy/`](agy/) | AGY 예시 설정 스냅샷. |
| [`third-party/`](third-party/) | 외부 자산 출처, 잠금 사본, 패치. |
| [`docs/`](docs/index.md) | 설치, 사용법, 소유권, 근거, 유지관리 지침. |
| [`archived/`](archived/) | 은퇴한 소스(Herdr 에이전트 런타임, OMP, 벤치마크 러너)의 동결 보관본. 설치·실행·테스트 대상이 아닙니다. |
| `var/` | 무시되는 로컬 보고서와 생성 상태. `.gitkeep`만 추적합니다. |

## 라이선스, 재사용, 유지관리

Harness는 [MIT 라이선스](LICENSE)로 배포합니다. 서드파티와 편입 구성요소의 저작권 고지와 라이선스 조건은 그대로 적용되며, [adopted-skills.json](third-party/adopted-skills.json)에 출처를 기록합니다.

이 저장소는 소유자만 유지하는 개인 쇼케이스입니다. 버그 제보, 기능 요청, pull request를 포함한 기여, 지원 요청, 취약점 제보를 받지 않습니다. MIT 라이선스에 따라 fork·수정·재배포할 수 있지만 유지관리 서비스나 답변은 제공하지 않습니다. 전체 정책은 [CONTRIBUTING.md](CONTRIBUTING.md)를 확인하세요.

코딩 에이전트는 [AGENTS.md](AGENTS.md)를 진입점으로 사용합니다. 언어 전환, 기능 개요, 빠른 시작, 상세 문서 연결 구성은 [oh-my-hermes](https://github.com/rlaope/oh-my-hermes)의 구조를 참고했습니다. 브랜드·그림·구현·제품 주장은 복사하지 않았습니다.
