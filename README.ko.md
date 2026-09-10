# Harness

[English](README.md) · [한국어](README.ko.md)

**공유 스킬, 모델 프로필, 보이는 실행, 실제 과제 평가를 버전 관리하는 개인용 코딩 에이전트 워크스테이션 설정입니다.**

Harness는 기존 [Oh My Pi](https://github.com/can1357/oh-my-pi)(OMP), [Herdr](https://github.com/herdrdev/herdr), Antigravity CLI(`agy`) 환경을 연결합니다. OMP에는 `profiles`와 `herdr` 확장만 설치합니다. Harness는 독립 에이전트나 호스팅 서비스, 이 도구들의 대체품이 아니라 개인 설정과 확장을 공개하는 쇼케이스입니다.

[설치](docs/guides/installation.md) · [문서](docs/index.md) · [사용법](docs/guides/usage.md) · [벤치마크](bench/README.md) · [재사용 정책](CONTRIBUTING.md) · [MIT 라이선스](LICENSE)

## 추가되는 기능

| 기능 | 제공 내용 |
| --- | --- |
| 공유 스킬 | 저장소 소유 지침을 OMP·Claude Code·AGY에 연결합니다. 편입 자료의 원저작자 고지는 유지합니다. |
| 모델 프로필 | `/profile`과 `omp-profile`로 용도별 모델·effort를 선택합니다. `/effort` 변경은 한 세션에만 적용할 수 있습니다. |
| 세션 계정 pin | OMP 내장 `/session pin`으로 현재 세션의 계정을 직접 선택합니다. Harness는 계정 선택을 여러 세션에 동기화하지 않습니다. |
| 컨텍스트 압축 | 별도 OMP 빌드나 런타임 패치 없이 여섯 가지 정책 키로 OMP 내장 압축을 관리합니다. |
| 보이는 실행 | `harness-run`으로 Herdr의 명령이나 독립 에이전트를 실행하고 다시 조회합니다. 기존 task 서브에이전트를 옮기는 기능은 아닙니다. |
| 실제 과제 평가 | 재생 가능한 fixture, 보호된 채점 자료, 비용 계산, 라우팅 제안을 제공합니다. 보편적인 모델 순위표는 아닙니다. |
| 개인 운영 | 비용 감사, 보호된 호스트 동기화, 사람이 검토하는 일일보고 초안 흐름을 제공합니다. 호스팅 서비스가 아닙니다. |

## 권장 환경

유지하는 쇼케이스 대상은 **Bash와 GNU 호환 유틸리티를 갖춘 Linux 또는 WSL2, `omp`로 실행할 수 있는 표준 OMP 설치본, Bun 1.3.14**입니다. 설정 검사와 벤치마크에는 Python 3가 필요합니다. 현재 설치기는 기존 `~/.claude/CLAUDE.md`를 요구합니다. 기반 도구의 설치·인증은 별도로 준비합니다. 네이티브 Windows와 macOS는 유지하는 설치 대상이 아닙니다. 앞으로 나올 OMP나 Bun 버전의 호환성은 검토 없이 가정하지 않습니다.

```bash
git clone https://github.com/huketo/harness.git
cd harness
bash install.sh --dry-run
```

[설치 안내](docs/guides/installation.md), 소스, 워크스테이션 변경 계획을 검토한 뒤 진행합니다.

```bash
bash install.sh
bash omp/config.apply.sh --check
```

**설치는 워크스테이션을 변경합니다.** 공유 자산을 연결하고, 교체 가능한 기존 설정 파일을 백업하며, 이 체크아웃이 소유한 기존 `harness-accounts`와 `harness-native-compaction` 링크만 제거합니다. 다른 곳을 가리키거나 예상과 다른 항목은 충돌로 남기고 제거하지 않습니다. Dry-run은 변경 없이 계획만 보여 줍니다. 설치기는 인증 정보, 저장된 선호 상태, 세션 transcript, 백업을 변경하지 않습니다. 기존 Harness native-compaction 상태의 replay와 portable 이전은 더 이상 제공하지 않으므로, 보존된 기존 세션이 재개된다고 보장할 수 없습니다. 설치 후 이미 로드된 모든 OMP 프로세스를 다시 시작합니다.

설정 검사는 값을 바꾸지 않으며 종료 코드 `1`은 차이가 있다는 뜻입니다. 내용을 확인한 뒤 저장소의 개인용 OMP 기본값을 적용하려면 명시적으로 실행합니다.

```bash
bash install.sh --with-config
```

모델 라우팅, fallback, 스킬 탐색, 내장 압축 정책, Auto QA 동의 설정 등이 적용됩니다. 확장 연결만 하려면 필요하지 않습니다. 설치기는 AGY 설정과 cron 작업을 복원하지 않습니다.

## 일상적인 사용

OMP 안에서:

```text
/session pin
/profile code
/effort high
/compact
```

- `/session pin`은 OMP 내장 수동 계정 선택기입니다. 선택은 현재 세션에만 적용되며 Harness는 계정 선택을 여러 세션에 동기화하지 않습니다.
- `/effort high`는 현재 세션·모델만 변경합니다. `--profile`을 붙이면 공용 모델 프로필 상태를 명시적으로 변경합니다.
- `/compact`는 표준 OMP 압축을 사용합니다. 관리 정책은 `enabled: true`, `methodOrder: remote → handoff → soft`, `keepRecentTokens: 40000`, `thresholdPercent: 75`, `thresholdTokens: -1`, `handoffSaveToDisk: true`로 설정합니다. [내장 압축 흐름](docs/guides/usage.md#내장-자동-압축)을 참고하세요.

터미널에서는 `~/.local/bin`을 `PATH`에 포함한 뒤 실행합니다.

```bash
omp-profile list
omp-profile show code
harness-run --help
```

오래 걸리거나 사람이 관찰·조작할 필요가 있는 실행에 Herdr를 사용합니다. 짧은 조회·빌드·테스트는 평소 도구로 실행합니다. 유한 명령(finite command)은 exit artifact와 로그를 확보한 뒤 자신이 생성한 탭이나 페인의 소유권을 확인하고 자동으로 닫으며, `PAGER=cat` 환경변수를 설정하여 페이저 정지를 방지합니다. 백그라운드 명령(`--detach`)은 명시적인 `--name`이 필수이며 탭이 닫히지 않고 유지됩니다. 완료된 단일-pane 명령 탭은 `harness-run prune --workspace current --dry-run` 또는 `--apply` 명령으로 안전하게 정리할 수 있습니다. 개발 서버 명령이 있는 프로젝트에서는 다음처럼 사용할 수 있습니다.

```bash
harness-run command --name dev --detach -- bun run dev
harness-run read dev
```

`/delegation`으로 현재 세션의 위임 상태를 확인하고, `agy`로 대화형 AGY 우선 위임, `native`로 내장 위임 복귀, `off`로 새 위임 중지, `model`로 AGY 기본 모델 선택을 관리합니다. 모드를 바꿔도 기존 작업자는 유지합니다. 일반 시작값은 native이며 `bun omp/herdr-trial.ts`는 AGY 모드로 시작하는 선택적 launcher입니다. OMP 코어 재빌드나 공용 설정 변경은 필요하지 않습니다. [동작과 제약](docs/guides/usage.md#세션별-위임-모드)을 확인합니다.

Detached 핸들은 준비 완료의 증거가 아닙니다. 출력과 서비스를 확인한 뒤 사용합니다. 독립 에이전트에는 명시적인 브리프가 필요하며, 내장 task 에이전트는 OMP Agent Hub에 남습니다. `harness-herdr` 확장은 OMP 내장 `ask` 도구를 게이트합니다. 호출마다 `herdr-hitl channel`을 먼저 실행하고 채널이 `terminal`일 때만 통과시킵니다. [상세 사용법과 상태 경계](docs/guides/usage.md)를 참고하세요.

## 기본값 변경 전에 평가하기

모델을 호출하지 않고 설정된 벤치마크 조합을 확인합니다.

```bash
python3 bench/bench.py run --dry-run
```

실제 실행에는 모델 인증이 필요하며 비용이 발생할 수 있습니다. 결과와 수집한 작업 자료는 커밋하지 않고 무시되는 `var/` 아래에 둡니다. [벤치마크 명령과 해석](bench/README.md), [벤치마크 조사](docs/BENCH-SURVEY.md), [과금 근거](docs/PRICING.md)를 참고하세요. 기록된 측정값은 날짜가 있는 개인 관측이며 성능 보장이 아닙니다.

## 설정과 안전 경계

- **자산별 정본 하나:** 사람이 관리하는 자산은 심링크하고, 도구가 관리하는 상태는 해당 도구에 둡니다. 배포된 스냅샷은 검토용 예시이며 호스트 백업이나 복원 지침이 아닙니다.
- **자격증명은 로컬에 유지:** API 키, OAuth 상태, 비공개 캘린더 URL, 메신저 토큰, 세션 로그, 보고서 입력은 버전 관리 밖에 둡니다. `.gitignore`는 비밀 탐지기가 아니며 과거 이력을 지우지 않습니다.
- **외부 영향 검토:** cron 활성화, 메시지 전송, 플러그인 업데이트, 원격 쓰기, Git 게시는 유지관리자가 의도적으로 실행해야 합니다. 배포된 스냅샷을 그대로 활성화하지 않습니다.
- **샌드박스가 아님:** 권한 정책과 파일 도구 deny 규칙은 임의 셸 접근을 격리하지 않습니다. 허용적인 워크스테이션 설정은 개인의 위험 선택이지 보안 기본값이 아닙니다.
- **링크는 즉시 반영:** 이 체크아웃을 수정하거나 갱신하면 설치된 자산도 바로 바뀝니다. 자동 제거기는 없으며, 링크 제거만으로 되돌릴 수 없는 변경은 [수동 복원 범위](docs/guides/installation.md#updating-and-undoing)에 설명합니다.

## 디렉터리 안내

| 경로 | 역할 |
| --- | --- |
| [`omp/`](omp/) | `profiles`·`herdr` 확장, 모델 프로필, 프롬프트, 선언적 설정. |
| [`herdr/`](herdr/) | 터미널 통합, 보조 명령, 플러그인 핀, 비용 감사, 보호된 호스트 동기화. |
| [`skills/`](skills/) | 개인 스킬과 원저작자 고지를 유지한 편입 스킬. |
| [`agy/`](agy/) | AGY 플러그인과 예시 설정 스냅샷. |
| [`bench/`](bench/) | 벤치마크 러너, 과제, fixture, 기준 자료, oracle. |
| [`third-party/`](third-party/) | 외부 자산 출처, 잠금 사본, 패치. |
| [`docs/`](docs/index.md) | 설치, 사용법, 소유권, 근거, 유지관리 지침. |
| `var/` | 무시되는 로컬 보고서와 생성 상태. `.gitkeep`만 추적합니다. |

## 라이선스, 재사용, 유지관리

Harness는 [MIT 라이선스](LICENSE)로 배포합니다. 서드파티와 편입 구성요소의 저작권 고지와 라이선스 조건은 그대로 적용되며, [adopted-skills.json](third-party/adopted-skills.json)에 출처를 기록합니다.

이 저장소는 소유자만 유지하는 개인 쇼케이스입니다. 버그 제보, 기능 요청, pull request를 포함한 기여, 지원 요청, 취약점 제보를 받지 않습니다. MIT 라이선스에 따라 fork·수정·재배포할 수 있지만 유지관리 서비스나 답변은 제공하지 않습니다. 전체 정책은 [CONTRIBUTING.md](CONTRIBUTING.md)를 확인하세요.

코딩 에이전트는 [AGENTS.md](AGENTS.md)를 진입점으로 사용합니다. 언어 전환, 기능 개요, 빠른 시작, 상세 문서 연결 구성은 [oh-my-hermes](https://github.com/rlaope/oh-my-hermes)의 구조를 참고했습니다. 브랜드·그림·구현·제품 주장은 복사하지 않았습니다.
