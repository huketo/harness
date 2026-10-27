# 레포 설계와 소유권 경계

## 관리 원칙

이 레포는 사람이 작성하고 검토하는 선언적 자산을 소유합니다. 실행 중인 도구가 자체적으로 갱신하는 상태는 직접 소유하지 않습니다. 판단 기준은 파일을 누가 쓰는지와 도구가 파일을 통째로 교체할 수 있는지입니다.

- 사람이 작성하는 개인 스킬과 Codex 실행 정책(`codex/harness.rules`)은 레포 파일을 정본으로 삼고 사용자 설정 경로에는 심링크합니다. 체크아웃 변경이 설치된 자산에 즉시 보이는 방식입니다.
- `~/.agents/.skill-lock.json`은 스킬 설치 관리자가 갱신합니다. `third-party/skills.lock.json`은 공개 의존성 핀의 비교 사본이며 실제 잠금 파일을 대체하지 않습니다.
- `agy/settings.snapshot.json`은 공개 가능한 개인 정책 예시입니다. live 설정을 복원하지 않고, trusted workspace·개인 경로·자격증명을 담지 않습니다.
- Claude Code와 AGY 플러그인은 `plugin/`이 정본이고, 설치 대상은 `plugin/build.mjs`가 만든 산출물입니다. Claude Code는 산출물 디렉터리를 마켓플레이스로 읽고, AGY는 `agy plugin install`로 사본을 만듭니다. 두 CLI의 설정 파일(`~/.claude/settings.json`, `~/.gemini/antigravity-cli/settings.json`)은 도구 소유이므로 `plugin/install.mjs`는 `plugin/guardrails.json`의 거부 규칙을 합집합으로 더하기만 하고 다른 값을 바꾸지 않습니다.
- T3 Code 예약 작업의 실제 상태는 T3 상태 DB가 소유합니다. `t3/scheduled/jobs.json`은 가드가 읽는 작업 정의이며 공개본에서는 빈 목록입니다. 가드의 실행 기록은 `${XDG_STATE_HOME:-~/.local/state}/harness-t3-jobs/`에 둡니다.
- `full-send` 허용 목록(`${XDG_CONFIG_HOME:-~/.config}/harness/full-send-repos`)은 사람이 쓰는 사용자 설정입니다. 저장소는 이 파일을 만들거나 배포하지 않습니다.

`install.sh`는 이 경계를 자동화합니다. 일반 파일을 심링크로 바꾸기 전에 `<경로>.bak`을 만들고, 이미 정확한 심링크가 있으면 유지합니다. 레포 밖을 가리키는 심링크나 심링크가 아닌 기존 스킬은 다른 소유자의 자산으로 보아 건너뛰고 충돌을 보고합니다.

## 디렉터리와 문서

| 경로 | 소유·성격 |
| --- | --- |
| `t3/scheduled/host-sync.mjs`, `host-sync.test.mjs` | 허용 목록 기반 동기화 guard와 임시 Git 저장소 회귀 테스트 |
| `t3/scheduled/guard.mjs`, `guard.test.mjs`, `jobs.json` | T3 예약 작업에 없는 시간 초과·일일 실행 횟수·연속 실패 중지·월간 실행일을 강제하는 가드와 회귀 테스트. `jobs.json`은 빈 공개 배포 상태 |
| `plugin/` | Claude Code·AGY 플러그인의 단일 정본(머지 가드 훅, 읽기 전용 리뷰어 agent, AGY 규칙), 산출물 빌더 `build.mjs`, 설치 계획기 `install.mjs`, 설정에 합칠 거부 규칙 `guardrails.json`. 배포 형태의 결정은 [AGENT-CONFIG](AGENT-CONFIG.md)가 소유 |
| `codex/` | T3 밖에서 쓰는 읽기 전용 Codex 리뷰어 `review.ts`와 테스트, `~/.codex/rules/harness.rules`로 연결하는 실행 정책(머지 명령은 사람의 승인) |
| `skills/` | 이 레포가 소유하는 개인 스킬과 고지를 유지한 편입 스킬 |
| `skills/daily-report/` | GitLab/iCal 근거 수집과 초안 작성 지침. Daou Office 제출은 사용자 UI 작업 |
| `agy/` | Antigravity CLI 설정의 공개 예시 스냅샷(`settings.snapshot.json`) |
| `third-party/` | 공개 관리형 자산의 핀·패치와 직접 편입한 자산의 출처 |
| `archived/` | 은퇴한 Herdr 에이전트 런타임 통합, OMP 설정·확장, 벤치마크 러너의 동결 보관본. 아무것도 설치하거나 실행하지 않으며 새 기능을 여기에 추가하지 않음 |
| `README.md`, `README.ko.md` | 영문·한글 시작 안내. 공통 기능·조건·안전 경계를 함께 갱신 |
| `docs/index.md` | 독자와 작업별 문서 색인 |
| `docs/guides/` | 설치·사용법·소유자 운영 경계 |
| `AGENTS.md`, `docs/agents/` | 에이전트 진입점과 주제별 owner-maintenance 지침 |
| `CONTRIBUTING.md` | 외부 기여·지원·제보를 받지 않는 정책과 독립 fork 안내 |
| `docs/public-release.md` | 공개 배포의 라이선스·개인정보·의존성·이력 불변식 |
| `docs/FACTS.md` | 공개 가능한 기술 관측과 한계 |
| `docs/AGENT-CONFIG.md` | Claude Code·Codex·AGY 설정 표면, T3 도달 범위, 플러그인 배포 형태, 머지 가드와 가드레일 결정 |
| `docs/PRICING.md` | 모델 단가와 캐시·장문 구간 비용 근거 |
| `var/` | 버전 관리하지 않는 로컬 생성 산출물. `.gitkeep`만 추적 |

## harness-host-sync의 격리 경계

`harness-host-sync`는 사람이 작업 중인 checkout을 자동화가 판단해 고치지 않도록 `t3/scheduled/host-sync.mjs`의 `prepare()`와 `finalize()`에서 경계를 강제합니다. 공개본은 runtime source를 보존하지만 일정이나 자동 게시 권한을 배포하지 않습니다.

- 원본 checkout이 예상 상태가 아니면 종료합니다. 브랜치 전환, `stash`, `reset`, rebase로 자동 복구하지 않습니다.
- 실제 후보 편집은 별도 작업공간에서만 이루어지고 코드의 허용 목록 밖 변경은 거부됩니다.
- 시작과 최종 반영 전 원본·원격 상태를 다시 확인합니다. 그 사이의 변경을 자동 병합하거나 덮어쓰지 않습니다.
- 실패하거나 차단된 후보는 사람이 판단할 수 있게 격리 상태로 남깁니다. 자동 정리나 재게시 대상으로 해석하지 않습니다.
- Git 서명과 hook을 우회하지 않습니다. 실패를 감추기 위해 서명을 끄거나 index를 초기화하지 않습니다.
- 비밀 패턴 검사는 보조 장치일 뿐이므로, 공개 후보의 스냅샷과 문서는 사람이 다시 검토합니다.

이 guard는 개인 호스트 설정을 공개본으로 자동 복사하는 도구가 아닙니다. 공개 스냅샷은 최소 예시만 포함하며, 원격 게시와 기본 브랜치 반영은 별도 소유자 결정입니다. 구체적인 직접 게시 명령은 공개 운영 절차로 배포하지 않습니다.

격리된 회귀 테스트는 다음과 같이 임시 로컬 Git 저장소만 사용합니다.

```bash
bun test t3/scheduled/host-sync.test.mjs
```

테스트 성공은 실제 원격 게시 권한이나 host scheduler 상태를 입증하지 않습니다.

## Antigravity CLI 자산의 경계

`agy`는 `~/.gemini/config/` 아래의 rules, skills, plugins, hooks, MCP 설정을 읽습니다. Harness가 내용을 소유하는 것은 플러그인 하나와 공개 예시 스냅샷뿐입니다.

- 플러그인의 정본은 `plugin/`이며, `plugin/build.mjs`가 만든 산출물을 `plugin/install.mjs`가 `agy plugin install`로 `~/.gemini/config/plugins/harness`에 복사합니다. AGY 1.4.7은 심링크한 플러그인 디렉터리를 건너뛰므로 저장소 디렉터리를 심링크하지 않으며, 이전 설치기가 만든 checkout 소유 심링크는 사본으로 바꿉니다([FACTS 6절](FACTS.md#6-t3-code와-에이전트-설정-표면-2026-10-26)).
- hooks와 MCP 설정은 각 설치 관리자가 쓰는 상태이므로 복사하거나 심링크하지 않습니다.
- 공유 스킬 디렉터리는 `~/.agents/skills`의 정본을 사용합니다. 기계별 절대 경로를 설정 파일에 박아 넣는 사본을 만들지 않습니다.
- 개인 instruction은 사용자가 소유한 기존 `~/.claude/CLAUDE.md`를 AGY rule 슬롯에 연결합니다. 저장소의 `CLAUDE.md`와 역할이 다릅니다.
- `agy/settings.snapshot.json`은 live 파일의 정본이 아닙니다. 개인 `always-proceed` 선택을 포함하더라도 새 호스트의 안전한 기본값이나 샌드박스라고 주장하지 않습니다.

비대화형 실행에서는 작업 디렉터리, 모델, 종료 코드, 구조화 결과를 각각 확인합니다. 성공 상태만으로 도구가 의도한 작업공간을 사용했거나 외부 효과가 안전했다고 판단하지 않습니다.

## 개인 스킬의 소유권

이 레포의 `skills/`가 사용자가 직접 만들고 통제하는 스킬을 소유합니다. 정본은 `skills/<스킬-이름>/SKILL.md`이며, `install.sh`가 `~/.agents/skills/<스킬-이름>`과 `~/.claude/skills/<스킬-이름>`에 심링크를 만듭니다.

현재 스킬 목록은 `skills/`에서 확인합니다. `t3-orchestrate`, `t3-handoff`, `t3-terminal`은 CLI 자체가 아니라 T3와 터미널 도구를 엮어 쓰는 작업 방식이므로 이 레포가 소유합니다. 은퇴한 오케스트레이션 스킬은 [`archived/skills/`](../archived/skills/)에 보관하며 설치하지 않습니다. 특정 프로젝트의 비공개 용어, endpoint, 고정 보고 양식, 사내 저장소를 전제로 하지 않습니다. 공개 `daily-report` 스킬은 `glab`을 통한 GitLab 수집과 iCal/`khal` 일정 수집, 근거 있는 초안, 사용자의 수동 Daou Office UI 입력까지만 설명합니다.

외부 도구에 종속된 스킬은 해당 공개 프로젝트와 설치 관리자가 소유합니다. `browser-skill`은 Tencent의 `bsk install-skill`이 설치하고 갱신하며 이 저장소에 사본을 두지 않습니다. `third-party/skills.lock.json`은 공개 의존성의 비교 핀만 보존하며, 설치 디렉터리 사본을 두 번째 정본으로 만들지 않습니다.

### 상류 스킬을 개인 정본으로 편입하기

직접 통제가 필요한 스킬을 편입할 때에는 상류 라이선스를 먼저 확인하고 원저작자 고지를 유지합니다. 관리형 사본과 편입 정본을 동시에 활성화하지 않습니다. 출처, 선택한 버전, 보존한 라이선스는 `third-party/adopted-skills.json`과 구성요소 옆의 고지에 기록합니다.

이후 수정은 `skills/`의 정본에서 수행합니다. `mattpocock/skills`에서 선택한 14개는 정본으로 유지하고, `third-party/adopted-skills.json`의 제거 목록에 있는 나머지 13개는 설치·배포 대상에서 제외합니다. 실제 평가 출력, 임시 작업공간, 모델 응답은 `var/`에 두며 배포하지 않습니다.

`awesome-interface`는 Jakub Krehel의 MIT 스킬을 재구성한 단일 진입점입니다. 여섯 전문 영역과 리뷰·변경 리뷰·스트레스·대안·설명 절차는 내부 참조 문서로 유지합니다. `third-party/adopted-skills.json`의 최상위 출처·날짜는 최초 편입 묶음의 기록이며, 이 스킬은 개별 항목의 출처·revision·입력 해시·로컬 변경 기록을 사용합니다. 라이선스가 확인되지 않은 `oklch-skill`의 고유 콘텐츠는 포함하지 않았습니다.

2026-09-15에는 [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill)의 MIT 자료를 선별 편입했습니다. `awesome-interface`에는 시각 방향·보존형 리디자인 참조만 추가하고, `image-to-code`·`imagegen`·`design-md`를 별도 진입점으로 둡니다. 이미지 생성의 웹·모바일·브랜드 분기는 일반 참조 문서이며 추가 등록하지 않습니다. theme/output/stitch 이름의 스킬이나 필수 생성 파이프라인은 도입하지 않습니다. 각 항목의 고정 revision과 입력 해시는 `third-party/adopted-skills.json`이 소유하고, 기존 UI 라이선스와 새 `LICENSE.taste-skill` 고지를 함께 유지합니다. 새 스킬은 각 디렉터리의 `LICENSE`를 사용합니다.

2026-09-16에는 [emilkowalski/skills](https://github.com/emilkowalski/skills/tree/85e8e2363b713506e1d5b6e07a0eb2da66be1bc3)의 MIT 자료 중 웹 모션·애니메이션·제스처 지침만 `awesome-interface`에 선별 편입했습니다. 일반 모션은 `references/ui.md`, 드래그·스와이프·관성·스냅은 필요할 때만 읽는 `references/gestures.md`가 다룹니다. React·Motion·Base UI를 필수로 삼지 않으며 기존 의존성과 컴포넌트 API를 우선합니다. 별도 스킬, 모바일 웹 초기 설정, 네이티브 API, 감사·프로토타입 절차는 추가하지 않았습니다. 입력 revision·해시는 `third-party/adopted-skills.json`, 원저작자의 MIT 고지는 `LICENSE.emilkowalski`에 보존합니다.

2026-10-21에는 [toss/apps-in-toss-harness](https://github.com/toss/apps-in-toss-harness/tree/255b636812d8b3a9b048d0a700644b9cbd8532c4)의 BSD-3-Clause `ux-writing` 원칙 일부를 `awesome-interface`의 `references/writing.md`에 다시 써서 넣었습니다. 압박 없는 선택 안내, 문장당 주장 하나와 조건 항목 분리, 화면당 언어 하나, 문구를 줄일 때의 사실 대조를 다룹니다. 별도 스킬, `/ait:` 명령, `design` G6 연계, docs MCP 조회, 적용 전 필수 승인 단계, 상류 before/after 예시는 가져오지 않았습니다. 입력 revision·해시는 `third-party/adopted-skills.json`, 원저작자 고지는 `LICENSE.toss-apps-in-toss-harness`에 보존합니다.

같은 날 `writing-for-humans`에 한국어·영어·일본어 스타일 레퍼런스(`references/style-ko.md`, `style-en.md`, `style-ja.md`)를 추가했습니다. 이 파일들은 SNS·블로그 산문과 기술 문서를 다루며 `writing-for-humans`와 `marketing`의 SNS·카피 참조가 읽습니다. 화면 문구의 언어별 규칙은 `awesome-interface`의 `references/writing.md`에 둡니다. [blader/humanizer](https://github.com/blader/humanizer), [choconyam/humanizer-ko](https://github.com/choconyam/humanizer-ko), [nanaism/yomiyasu](https://github.com/nanaism/yomiyasu)의 MIT 자료에서 규칙만 골라 다시 썼고, 스크립트·설치 절차·어휘 목록은 가져오지 않았습니다. 입력 revision·해시는 `third-party/adopted-skills.json`, 원저작자 고지는 `skills/writing-for-humans/LICENSE.humanizer`, `LICENSE.humanizer-ko`, `LICENSE.yomiyasu`에 보존합니다. 비교 평가 사례는 각 스킬의 `evals/evals.json`에 있습니다.

`imagegen`의 독립 로고 분기는 워드마크·심벌·마스코트·조합형·엠블럼을 다룹니다. [s1dashu/ip-as-logo-skill](https://github.com/s1dashu/ip-as-logo-skill)의 조형 지침은 선택형 `references/logo/rounded-ip.md`에만 수용했고 `LICENSE.ip-as-logo`에 원저작자의 MIT 고지를 보존합니다. 고정 revision·입력 해시·로컬 변경은 같은 provenance 기록에 추가합니다. 별도 로고 스킬이나 상류의 고정 배치·무검수 생성 절차는 설치하지 않습니다.

2026-10-26에는 [t3dotgg/tstack](https://github.com/t3dotgg/tstack/tree/7de017b3fc9d50c03cf3ecb98fb71e0ca65a78bd)의 MIT 스킬 가운데 PR 수명주기와 작업 모드를 한국어로 다시 써서 편입했습니다. `file-pr`·`babysit-pr`·`leaving-pr-comments`·`takeover`·`modernize`는 GitLab MR과 GitHub PR을 함께 다루는 `file-mr`·`babysit-mr`·`leaving-mr-comments`·`takeover`·`modernize`가 되었고, `babysit-mr`의 `scripts/mr-wait`는 상류 `pr-wait`에 GitLab 백엔드를 더했습니다. `full-send`·`full-stop`은 사용자 호출 작업 모드이며, 머지는 사람이 쓴 허용 목록의 저장소에서만 합니다. `sol-loop`은 기존 오케스트레이션 리뷰 기준과 합쳐 `review-loop`이 되었고, 위험 등급 스크립트(`review-tier.sh`, `review-escalate.sh`, `review-tiers.tsv`)와 리뷰 기준은 당시 오케스트레이션 스킬에서 `review-loop`으로 옮겼으며 지금은 `t3-orchestrate`가 이를 씁니다. `council`은 계열별 플래그십 셋의 읽기 전용 교차 검토입니다. 특정 리뷰 봇에 묶인 처리는 "저장소에 그 봇을 소비하는 스킬이 있으면 그 스킬에 넘긴다"는 일반 규칙으로 바꿨습니다. 고정 revision·입력 해시·로컬 변경은 `third-party/adopted-skills.json`, 원저작자 고지는 각 스킬의 `LICENSE` 또는 `LICENSE.tstack`에 있습니다. `t3-orchestrate`는 tstack 자료를 쓰지 않은 하네스 소유 스킬입니다.

`git-commit`은 [github/awesome-copilot](https://github.com/github/awesome-copilot/tree/7568a482ce2df38f8965ab5336a3220db796a4ba)의 MIT 스킬을 2026-09-09에 편입했습니다. 본문은 그대로 두고 description만 트리거 조건으로 줄였습니다. 같은 날 `daily-report`, `code-review`, `diagnosing-bugs`, `tdd`, `writing-for-agents`의 description도 줄였습니다. description은 시스템 프롬프트에 항상 실리는 유일한 부분이므로 절차 설명은 본문에 두고, 이웃 스킬과 겹치는 트리거는 한쪽에만 둡니다. 근거는 `docs/FACTS.md` 5절에 있습니다.

2026-09-28에는 [openclaw/openclaw](https://github.com/openclaw/openclaw/tree/80930af448ebabc84174146b56bc106d37fab3b4/.agents/skills/test-audit)의 MIT `test-audit`을 범용 스킬로 편입했습니다. 이 스킬은 기존 테스트의 감사·정리와 테스트 전용 production seam 제거를 소유하며, 대상 프로젝트의 runner·gate·게시 흐름은 그 프로젝트의 지침·CI·매니페스트에서 찾습니다. 새 테스트의 작성 게이트는 트리거가 겹치지 않도록 `tdd`로 옮겼고, 두 스킬이 함께 쓰는 정크 패턴 목록은 `skills/test-audit/patterns.md` 한 곳에 둡니다. `tdd`는 `test-audit`이 설치되지 않아도 동작합니다. 판단 평가는 `skills/test-audit/evals/evals.json`에 있습니다.

같은 날 [unicodef1wn/lauren-poteto-rules](https://github.com/unicodef1wn/lauren-poteto-rules/tree/a6f818e107855df5603c8f36f626de4b1125e5b7)의 MIT 원칙 가운데 반복 교정을 설계·기계 검사·규칙·스킬 순의 제약으로 바꾸는 기준과 지침 변경의 평가 절차를 `writing-for-agents`에, 검증된 재현 경로 기록과 기계적 재발 방지 검토를 `diagnosing-bugs`에 다시 써서 넣었습니다. 나머지 원칙은 기존 지침과 겹치고 description이 이웃 스킬의 트리거와 충돌하므로 스킬 전체는 편입하지 않았습니다. 두 출처의 고정 revision·입력 해시·로컬 변경은 `third-party/adopted-skills.json`, 원저작자 고지는 `skills/test-audit/LICENSE`, `skills/tdd/LICENSE.openclaw`, 각 스킬의 `LICENSE.lauren-poteto-rules`에 있습니다.

2026-10-06에는 [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills/tree/dda3841f0b294e01e93b1541486beefbfab0915e)의 MIT 마케팅 스킬 50개 가운데 32개를 단일 진입점 `marketing`으로 다시 써서 편입했습니다. 상류의 50개 description은 합계 37,200자이므로 그대로 설치하지 않고, 짧은 description 하나와 영역별 참조 11개(`references/`)로 나눴습니다. 상류의 고정 컨텍스트 파일 `.agents/product-marketing.md` 대신, 대상 레포의 문서 관례에서 마케팅 컨텍스트를 찾고 출처 권위 순서와 claim ledger로 모든 제품 주장을 근거에 묶습니다. 게시·발송·예약·연락·광고 집행은 명시적 승인 전까지 초안으로만 남깁니다. 가격·이메일·광고·이탈 방지 6개는 보류하고, B2B 영업·리드 수집·SMS·ASO·이미지·영상·실존 인물 페르소나 12개와 `tools/`의 CLI·파트너 자료는 제외했습니다. 고정 revision·입력 해시·로컬 변경·제외 목록은 `third-party/adopted-skills.json`, 원저작자 고지는 `skills/marketing/LICENSE`에 있습니다. 판단 평가는 가상 제품 fixture를 쓰는 `skills/marketing/evals/evals.json`에 있습니다.

## 서드파티 스킬

설치 관리자가 내려받은 스킬과 플러그인 checkout은 이 레포가 소유하지 않습니다. 관리형 디렉터리를 복사하면 상류 업데이트와 로컬 사본이 갈라지므로, 공개 핀과 필요한 패치만 보존합니다.

패치는 상류 저장소, 기준 ref, 적용 조건, 필요한 라이선스 고지를 함께 기록합니다. 업데이트 후에는 기준이 여전히 적용되는지 확인하고 해당 구성요소의 테스트를 실행합니다.

## 버전 관리에서 제외하는 것

다음 자산은 커밋하지 않습니다.

1. 토큰, 비밀번호, API 키, OAuth 상태, private feed URL 등 회수나 교체가 필요한 값.
2. 실제 보고 내용, 개인 일정, 사용자·직원 식별자, 개인 이메일, private issue나 MR 본문.
3. 세션 기록, 캐시, 로그, 예약 작업 실행 이력, 데이터베이스, 감사 입력, 원시 benchmark 결과.
4. 홈 절대 경로, trusted workspace, host-specific 상태처럼 공개 예제로 일반화할 수 없는 값.
5. 도구가 소유하고 덮어쓰는 파일. 필요한 경우에도 최소 공개 핀이나 선언적 적용 스크립트만 보존합니다.

`var/`에는 로컬 산출물을 둘 수 있지만 추적 대상이 아닙니다. `.gitignore`는 공개 승인이나 비밀 검사를 대신하지 않습니다. 예제와 fixture는 실제 데이터를 가공하는 대신 처음부터 합성으로 작성합니다.

## 사람 개입 규칙의 위치

T3 Code 스레드에서 실행되는 Claude Code·Codex·Antigravity 세션은 `AGENTS.md`의 안내에 따라 [`docs/agents/hitl.md`](agents/hitl.md)를 사람 개입 규칙으로 읽습니다. Antigravity는 T3 아래에서 저장소 `AGENTS.md`를 로드하지 않으므로, 무인 Antigravity 작업에서는 프롬프트에 적은 명시적 경로가 유일한 연결입니다.

## 앞으로 추가할 자산의 위치

- T3 예약 작업의 정의는 `t3/scheduled/jobs.json`에, 그 실행기와 테스트는 같은 디렉터리에 둡니다. 공개본의 작업 목록은 비워 둡니다.
- 새 개인 스킬은 `skills/<스킬-이름>/SKILL.md`에 두고 공개 환경에서 의미가 통하는 이름과 입력 계약을 사용합니다.
- 실제 업무 자료에서 추출한 corpus는 공개 저장소에 추가하지 않습니다. 예제와 fixture는 처음부터 합성 자료로 작성합니다.
- 생성 보고서, 실행 데이터, 임시 측정값은 자산 종류와 관계없이 `var/` 아래에 둡니다.

새 자산은 정본과 작성 주체를 먼저 정한 뒤 배치합니다. 사람이 유지하는 선언은 심링크하고, 도구가 쓰는 상태는 공개 적용 명령이나 최소 핀으로 재현한다는 원칙을 유지합니다.
