# 레포 설계와 소유권 경계

## 관리 원칙

이 레포는 사람이 작성하고 검토하는 선언적 자산을 소유합니다. 실행 중인 도구가 자체적으로 갱신하는 상태는 직접 소유하지 않습니다. 판단 기준은 파일을 누가 쓰는지와 도구가 파일을 통째로 교체할 수 있는지입니다.

- 사람이 작성하는 개인 스킬, Herdr 설정과 보조 스크립트는 레포 파일을 정본으로 삼고 사용자 설정 경로에는 심링크합니다. 체크아웃 변경이 설치된 자산에 즉시 보이는 방식입니다.
- OMP의 `~/.omp/agent/config.yml`은 `omp config set`이 쓰는 상태 파일입니다. `omp/config.apply.sh`가 공개 명령으로 선택한 값을 적용하며, `omp/config.snapshot.yml`은 공개 가능한 예시입니다. 파일을 심링크하거나 스냅샷 전체를 복원하지 않습니다.
- 같은 설정 안에서도 `modelRoles.default`는 세션이 바꿀 수 있습니다. `omp/config.apply.sh`는 이 값을 현재 세션 소유 상태로 취급하고 나머지 관리 키만 비교·적용합니다. 그렇지 않으면 정상적인 모델 전환이 설정 drift로 오인됩니다.
- `~/.agents/.skill-lock.json`은 스킬 설치 관리자가 갱신합니다. `third-party/skills.lock.json`은 공개 의존성 핀의 비교 사본이며 실제 잠금 파일을 대체하지 않습니다.
- Herdr cron의 live `jobs.yaml`은 `herdr-cron`이 교체할 수 있는 도구 소유 파일입니다. 심링크하지 않습니다. 공개 `herdr/cron/jobs.snapshot.yaml`은 `version: 1`, `jobs: []`인 빈 배포 상태이며 개인 일정의 백업이나 복원 입력이 아닙니다.
- `agy/settings.snapshot.json`은 공개 가능한 개인 정책 예시입니다. live 설정을 복원하지 않고, trusted workspace·개인 경로·자격증명을 담지 않습니다.

`install.sh`는 이 경계를 자동화합니다. 일반 파일을 심링크로 바꾸기 전에 `<경로>.bak`을 만들고, 이미 정확한 심링크가 있으면 유지합니다. 레포 밖을 가리키는 심링크나 심링크가 아닌 기존 스킬은 다른 소유자의 자산으로 보아 건너뛰고 충돌을 보고합니다. OMP 설정은 `--with-config`를 명시한 경우에만 적용합니다.

## 디렉터리와 문서

| 경로 | 소유·성격 |
| --- | --- |
| `omp/` | OMP 18.1.13 설정 적용, 공개 예시 스냅샷, 용도별 프로필, 확장, 런타임 호환 패치 |
| `herdr/` | Herdr 설정, 실행 도우미, 공개 플러그인 핀, 비용 감사, 격리된 host-sync guard |
| `herdr/scripts/harness-run.ts` | 사용자에게 보이는 명령·독립 에이전트 실행과 재사용. 상태와 로그는 저장소 밖에서 관리 |
| `herdr/cron/cost-audit.mjs` | 로컬 통계 분석과 해석 흐름. 입력과 결과는 `var/`에 유지 |
| `herdr/cron/host-sync.mjs`, `host-sync.test.mjs` | 허용 목록 기반 동기화 guard와 임시 Git 저장소 회귀 테스트 |
| `herdr/cron/jobs.snapshot.yaml` | 예약 작업이 없는 공개 배포 상태 |
| `skills/` | 이 레포가 소유하는 개인 스킬과 고지를 유지한 편입 스킬 |
| `skills/daily-report/` | GitLab/iCal 근거 수집과 초안 작성 지침. Daou Office 제출은 사용자 UI 작업 |
| `agy/` | Antigravity CLI가 이 하네스를 사용하게 하는 플러그인과 공개 예시 설정 |
| `third-party/` | 공개 관리형 자산의 핀·패치와 직접 편입한 자산의 출처 |
| `bench/` | 벤치마크 러너, 합성 과제 정의·fixture, oracle, 기준 자료, 회귀 테스트 |
| `README.md`, `README.ko.md` | 영문·한글 시작 안내. 공통 기능·조건·안전 경계를 함께 갱신 |
| `docs/index.md` | 독자와 작업별 문서 색인 |
| `docs/guides/` | 설치·사용법·소유자 운영 경계 |
| `AGENTS.md`, `docs/agents/` | 에이전트 진입점과 주제별 owner-maintenance 지침 |
| `CONTRIBUTING.md` | 외부 기여·지원·제보를 받지 않는 정책과 독립 fork 안내 |
| `docs/public-release.md` | 공개 배포의 라이선스·개인정보·의존성·이력 불변식 |
| `docs/FACTS.md` | 공개 가능한 기술 관측과 한계 |
| `docs/BENCH-SURVEY.md` | 외부 벤치마크 조사와 판정 설계 |
| `docs/PRICING.md` | 모델 단가와 캐시·장문 구간 비용 근거 |
| `var/` | 버전 관리하지 않는 로컬 생성 산출물. `.gitkeep`만 추적 |

## harness-host-sync의 격리 경계

`harness-host-sync`는 사람이 작업 중인 checkout을 자동화가 판단해 고치지 않도록 `herdr/cron/host-sync.mjs`의 `prepare()`와 `finalize()`에서 경계를 강제합니다. 공개본은 runtime source를 보존하지만 일정이나 자동 게시 권한을 배포하지 않습니다.

- 원본 checkout이 예상 상태가 아니면 종료합니다. 브랜치 전환, `stash`, `reset`, rebase로 자동 복구하지 않습니다.
- 실제 후보 편집은 별도 작업공간에서만 이루어지고 코드의 허용 목록 밖 변경은 거부됩니다.
- 시작과 최종 반영 전 원본·원격 상태를 다시 확인합니다. 그 사이의 변경을 자동 병합하거나 덮어쓰지 않습니다.
- 실패하거나 차단된 후보는 사람이 판단할 수 있게 격리 상태로 남깁니다. 자동 정리나 재게시 대상으로 해석하지 않습니다.
- Git 서명과 hook을 우회하지 않습니다. 실패를 감추기 위해 서명을 끄거나 index를 초기화하지 않습니다.
- 비밀 패턴 검사는 보조 장치일 뿐이므로, 공개 후보의 스냅샷과 문서는 사람이 다시 검토합니다.

이 guard는 개인 호스트 설정을 공개본으로 자동 복사하는 도구가 아닙니다. 공개 스냅샷은 최소 예시만 포함하며, 원격 게시와 기본 브랜치 반영은 별도 소유자 결정입니다. 구체적인 직접 게시 명령은 공개 운영 절차로 배포하지 않습니다.

격리된 회귀 테스트는 다음과 같이 임시 로컬 Git 저장소만 사용합니다.

```bash
bun test herdr/cron/host-sync.test.mjs
```

테스트 성공은 실제 원격 게시 권한이나 host scheduler 상태를 입증하지 않습니다.

## Antigravity CLI 자산의 경계

`agy`는 `~/.gemini/config/` 아래의 rules, skills, plugins, hooks, MCP 설정을 읽습니다. Harness가 직접 소유하는 것은 `agy/config/plugins/harness/`와 공개 예시 스냅샷뿐입니다.

- 플러그인 소스는 `~/.gemini/config/plugins/harness`로 심링크합니다.
- hooks와 MCP 설정은 각 설치 관리자가 쓰는 상태이므로 복사하거나 심링크하지 않습니다.
- 공유 스킬 디렉터리는 `~/.agents/skills`의 정본을 사용합니다. 기계별 절대 경로를 설정 파일에 박아 넣는 사본을 만들지 않습니다.
- 개인 instruction은 사용자가 소유한 기존 `~/.claude/CLAUDE.md`를 AGY rule 슬롯에 연결합니다. 저장소의 `CLAUDE.md`와 역할이 다릅니다.
- `agy/settings.snapshot.json`은 live 파일의 정본이 아닙니다. 개인 `always-proceed` 선택을 포함하더라도 새 호스트의 안전한 기본값이나 샌드박스라고 주장하지 않습니다.

`harness-run`은 프로필에 선언한 모델 ID를 실행 인자로 전달하므로 전역 기본 모델을 바꾸지 않습니다. 비대화형 실행에서는 작업 디렉터리, 모델, 종료 코드, 구조화 결과를 각각 확인합니다. 성공 상태만으로 도구가 의도한 작업공간을 사용했거나 외부 효과가 안전했다고 판단하지 않습니다.

## 개인 스킬의 소유권

이 레포의 `skills/`가 사용자가 직접 만들고 통제하는 스킬을 소유합니다. 정본은 `skills/<스킬-이름>/SKILL.md`이며, `install.sh`가 `~/.agents/skills/<스킬-이름>`과 `~/.claude/skills/<스킬-이름>`에 심링크를 만듭니다.

현재 스킬 목록은 `skills/`에서 확인합니다. 특정 프로젝트의 비공개 용어, endpoint, 고정 보고 양식, 사내 저장소를 전제로 하지 않습니다. 공개 `daily-report` 스킬은 `glab`을 통한 GitLab 수집과 iCal/`khal` 일정 수집, 근거 있는 초안, 사용자의 수동 Daou Office UI 입력까지만 설명합니다.

외부 도구에 종속된 스킬은 해당 공개 프로젝트와 설치 관리자가 소유합니다. `third-party/skills.lock.json`은 공개 의존성의 비교 핀만 보존하며, 설치 디렉터리 사본을 두 번째 정본으로 만들지 않습니다.

### 상류 스킬을 개인 정본으로 편입하기

직접 통제가 필요한 스킬을 편입할 때에는 상류 라이선스를 먼저 확인하고 원저작자 고지를 유지합니다. 관리형 사본과 편입 정본을 동시에 활성화하지 않습니다. 출처, 선택한 버전, 보존한 라이선스는 `third-party/adopted-skills.json`과 구성요소 옆의 고지에 기록합니다.

이후 수정은 `skills/`의 정본에서 수행합니다. `mattpocock/skills`에서 선택한 14개는 정본으로 유지하고, `third-party/adopted-skills.json`의 제거 목록에 있는 나머지 13개는 설치·배포 대상에서 제외합니다. 실제 평가 출력, 임시 작업공간, 모델 응답은 `var/`에 두며 배포하지 않습니다.

`awesome-interface`는 Jakub Krehel의 MIT 스킬을 재구성한 단일 진입점입니다. 여섯 전문 영역과 리뷰·변경 리뷰·스트레스·대안·설명 절차는 내부 참조 문서로 유지합니다. `third-party/adopted-skills.json`의 최상위 출처·날짜는 최초 편입 묶음의 기록이며, 이 스킬은 개별 항목의 출처·revision·입력 해시·로컬 변경 기록을 사용합니다. 라이선스가 확인되지 않은 `oklch-skill`의 고유 콘텐츠는 포함하지 않았습니다.

`git-commit`은 [github/awesome-copilot](https://github.com/github/awesome-copilot/tree/7568a482ce2df38f8965ab5336a3220db796a4ba)의 MIT 스킬을 2026-09-09에 편입했습니다. 본문은 그대로 두고 description만 트리거 조건으로 줄였습니다. 같은 날 `daily-report`, `code-review`, `diagnosing-bugs`, `tdd`, `writing-for-agents`의 description도 줄였습니다. description은 시스템 프롬프트에 항상 실리는 유일한 부분이므로 절차 설명은 본문에 두고, 이웃 스킬과 겹치는 트리거는 한쪽에만 둡니다. 근거는 `docs/FACTS.md` 11절에 있습니다.

## 서드파티 스킬과 Herdr 플러그인

설치 관리자가 내려받은 스킬과 플러그인 checkout은 이 레포가 소유하지 않습니다. 관리형 디렉터리를 복사하면 상류 업데이트와 로컬 사본이 갈라지므로, 공개 핀과 필요한 패치만 보존합니다.

패치는 상류 저장소, 기준 ref, 적용 조건, 필요한 라이선스 고지를 함께 기록합니다. 업데이트 후에는 기준이 여전히 적용되는지 확인하고 해당 구성요소의 테스트를 실행합니다. Herdr 플러그인도 공개 저장소와 핀만 manifest에 기록하며 바이너리나 관리형 checkout을 복제하지 않습니다.

## 버전 관리에서 제외하는 것

다음 자산은 커밋하지 않습니다.

1. 토큰, 비밀번호, API 키, OAuth 상태, private feed URL 등 회수나 교체가 필요한 값.
2. 실제 보고 내용, 개인 일정, 사용자·직원 식별자, 개인 이메일, private issue나 MR 본문.
3. 세션 기록, 캐시, 로그, cron 실행 이력, 데이터베이스, 감사 입력, 원시 benchmark 결과.
4. 홈 절대 경로, trusted workspace, host-specific 상태처럼 공개 예제로 일반화할 수 없는 값.
5. 도구가 소유하고 덮어쓰는 파일. 필요한 경우에도 최소 공개 핀이나 선언적 적용 스크립트만 보존합니다.

`var/`에는 로컬 산출물을 둘 수 있지만 추적 대상이 아닙니다. `.gitignore`는 공개 승인이나 비밀 검사를 대신하지 않습니다. 예제와 fixture는 실제 데이터를 가공하는 대신 처음부터 합성으로 작성합니다.

## 프로젝트 범위 시스템 프롬프트 재정의

`.omp/APPEND_SYSTEM.md`는 이 레포에서 작업하는 에이전트에게 적용되는 프로젝트 범위 시스템 프롬프트 추가분입니다. OMP는 프로젝트 범위 파일을 사용자 범위보다 우선하므로, 필요한 전역 규칙이 자동 상속된다고 가정하지 않습니다.

이 파일은 사람 질문, 외부 효과, 무인 실행의 권한 경계를 정의합니다. 벤치마크 runner는 임시 fixture 작업공간에서 실행되므로 프로젝트 파일 탐색에 기대지 않고 필요한 system prompt를 명시적으로 전달합니다. 두 장치는 적용 범위가 다릅니다.

## 앞으로 추가할 자산의 위치

- OMP 확장은 `omp/extensions/<이름>/`, 용도·모델·effort 정책은 `omp/profiles.json`과 `omp/profiles.ts`, 짧은 모델 차이는 `omp/prompts/`에 둡니다.
- 이 레포가 정본인 Herdr 소스는 `herdr/` 아래에 두고, 별도 공개 저장소가 정본인 플러그인은 `herdr/plugins.manifest.json`의 핀만 갱신합니다.
- 새 개인 스킬은 `skills/<스킬-이름>/SKILL.md`에 두고 공개 환경에서 의미가 통하는 이름과 입력 계약을 사용합니다.
- 합성 fixture·oracle·기준 자료는 `bench/`의 기존 구분을 따릅니다. 실제 업무 자료에서 추출한 corpus는 공개 저장소에 추가하지 않습니다.
- 생성 보고서, 실행 데이터, 임시 측정값은 자산 종류와 관계없이 `var/` 아래에 둡니다.

새 자산은 정본과 작성 주체를 먼저 정한 뒤 배치합니다. 사람이 유지하는 선언은 심링크하고, 도구가 쓰는 상태는 공개 적용 명령이나 최소 핀으로 재현한다는 원칙을 유지합니다.

모델 용도 프로필은 OMP의 `--profile`과 다릅니다. OMP `--profile`은 인증·세션·캐시를 분리하는 실행 환경이고, Harness 용도 프로필은 같은 환경 안에서 모델과 effort를 선택합니다. `/effort`의 기본 변경은 현재 OMP 대화에만 보존하며, `--profile`을 명시한 변경과 `omp-profile effort set`만 공유 프로필 상태를 수정합니다.
