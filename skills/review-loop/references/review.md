# 리뷰 기준과 리뷰어 브리프

리뷰는 변경이 의도를 만족하는지와 구체적인 결함이 남았는지를 확인한다. 리뷰어는 새 컨텍스트에서 diff를 보고 시작하고, 작성자와 다른 모델 계열이다. 모델 다양성은 정확성을 보장하지 않으므로 판정에는 확인 가능한 근거가 필요하다. `review-loop`, `council`, `t3-orchestrate`가 이 파일을 공유한다.

## 위험 등급과 회차 예산

독립 리뷰를 할지와 최대 회차는 변경이 닿는 경계가 정한다.

| 등급 | 대상 | 독립 리뷰 |
| --- | --- | --- |
| `none` | 보안 규칙에 걸리지 않는 문서, 주석, 테스트만 바꾼 변경 | 없음. 작성자 자기 점검과 CI |
| `logic` | 일반 로직, 설정 값 변경, 에이전트 지시 문서(`SKILL.md`, `AGENTS.md`, `CLAUDE.md`, `skills/*/references/`, `ROLE.md`·`CORE.md`) | 최대 3회 |
| `security` | 비밀값, 인증, egress, 승인, merge·deploy 권한, sudoers, 네트워크 정책, OAuth | 최대 5회 |

`scripts/review-tier.sh <repo> <base>`가 diff의 경로와 변경 줄을 [`scripts/review-tiers.tsv`](../scripts/review-tiers.tsv)의 규칙으로 분류하고 첫 줄에 `tier=<등급> rounds=<회차>`를 출력한다. 분류는 위로만 틀린다: 보안 경로·내용 규칙을 먼저, 지시 문서를 다음에, `none` 규칙을 마지막에 보고, 어디에도 맞지 않으면 `logic`이다. 저장소는 루트의 `.review-tiers.tsv`로 규칙을 덧붙인다. 두 파일의 `security` 규칙을 다른 모든 규칙보다 먼저 보므로 저장소 규칙이 하네스의 보안 규칙을 가리지 못하고, 나머지 규칙은 저장소 규칙이 앞선다. 이 파일은 리뷰 기준(merge-base)에서 읽으므로 변경이 자기 등급을 낮추지 못한다. 분류가 틀려 낮춰야 하면 예외를 두지 않고 규칙 파일을 고친다. 회귀 사례는 `scripts/review-tier.test.sh`다.

분류기는 하한이다. 데이터 손실, 상태·동시성 변경처럼 키워드로 잡히지 않는 경계는 작성자가 근거를 적고 `security` 예산(5회)을 쓴다. 리뷰어가 놓친 보안 경계를 찾으면 응답 머리에 `TIER: security`를 쓰고, `scripts/review-escalate.sh <review-tier.txt> <review.md...>`가 그 줄로 등급을 올린다. 등급은 내려가지 않으며 이후 회차는 올라간 예산을 따른다.

## 리뷰어에게 주는 것과 주지 않는 것

준다: 미리 저장한 diff와 커밋 목록, 의도·계약·수용 기준·범위 밖, 실행한 검사와 결과, 저장소 관례 문서 경로, 아래 기준 전체. 리뷰어에게 셸로 diff를 다시 만들게 하지 않는다.

주지 않는다(첫 판정이 끝날 때까지): 작성자의 자기 평가와 보고, 이전 회차 리뷰. 2회차부터는 원장(ledger)과 직전 회차 이후의 변경을 준다.

## 실행 권한

읽기 전용은 프롬프트가 아니라 실행기의 권한으로 보장하고, 그럴 수 없으면 사후에 증명한다.

- Claude 리뷰어: 하네스 플러그인의 `harness:reviewer` 하위 agent. `tools`가 읽기·검색 도구만 허용하므로 도구 수준에서 읽기 전용이다. Claude Code는 부모가 `bypassPermissions`·`auto`일 때 하위 agent의 `permissionMode`를 무시하므로, 경계는 모드가 아니라 도구 목록이다.
- T3 안의 Codex와 그 밖의 제공자: T3에 읽기 전용 실행 모드가 없으므로 `delegate_task`를 `isolation: "worktree"`로 실행하고, 위임 직전의 `scripts/tree-unchanged.sh snapshot`과 끝난 뒤의 `check`로 자식 워크트리와 공유 git 제어 파일(`config`, 훅, `info/`)이 그대로인지 확인한다. 자식 워크트리는 저장소의 `.git`을 공유하므로, 설정이나 훅을 바꾸면 이후 git 명령에서 코드가 실행될 수 있기 때문이다. 실패하면 그 회차의 판정을 쓰지 않고 리뷰 실패로 센다. 이 확인은 로컬 체크아웃만 증명하며 원격 쓰기(푸시, 댓글)가 없었다는 증거가 아니다. 브리프의 금지 문장과 결과 대조로 보완한다.
- T3 밖의 Codex 리뷰어: `codex/review.ts`. OS 샌드박스가 읽기 전용이고 네트워크·MCP·하위 agent가 꺼져 있다. 시작 전 `--inspect-tools`가 모델 호출 없이 이 경계를 확인하고, 경계가 넓어져 있으면 모델 호출 전에 거부한다.

리뷰 결과는 stdout이나 작업 결과로 돌아오고 오케스트레이터가 상태 디렉터리에 저장한다. 실패한 프로세스, 시간 초과, 빈 출력은 승인이 아니다.

## 판정 기준

각 항목은 통과/지적 중 하나로 답한다. 지적에는 `file:line`과 근거를 붙인다.

### A. 의도와 수용 기준

0. 의도를 먼저 본다. 변경이 의도가 필요로 하는 일을 하는가, 그 이상을 하지 않는가. 줄 단위 검토는 그다음이다.
1. 수용 기준 각 항목이 diff로 충족되는가. 코드에서 읽어 판단하고, 실행 증거가 부족하면 필요한 명령과 기대 관측을 제시한다.
2. 계약 문장이 그대로 구현되었는가(이름, 시그니처, 스키마).
3. 의도에 없는 변경이 있는가. 범위 밖에 적힌 것이 들어 있으면 `blocker`다. 요청 없이 더한 복잡성(추가 검증, 추상화, 이름 붙은 실패가 없는 방어 코드)은 지적 대상이다.

### B. 통상성

새 인프라·외부 연동·낯선 아키텍처를 도입할 때는 기존 코드와 적합한 표준 라이브러리·서비스를 먼저 비교한다. 대안이 더 낫다는 주장은 실제 비용·복잡도·위험으로 설명하며, 관례와 다르다는 사실만으로 결함이라고 판정하지 않는다. 저장소의 기존 관례 자체가 비표준이면 그 관례를 따른 변경은 고칠 대상이 아니다. `nit`으로 적고 주장 앞에 `convention:`을 붙인다. 이것은 수정 지시가 아니라 결정 후보다.

### C. AI slop 표지

다음은 살펴볼 단서이지 자동 결함 판정표가 아니다. 이번 변경에서 실제로 불필요하거나 위험하다는 근거가 있을 때만 지적한다.

- 호출자가 하나인 래퍼, 한 줄을 감싼 헬퍼, 나중을 위한 추상화나 매개변수
- 불가능한 상태를 막는 방어 코드, 광범위한 예외 잡기, 요청 없는 폴백과 기본값
- 코드가 이미 말하는 것을 반복하는 주석, 변경 이력을 서술하는 주석
- 삭제 대신 남긴 별칭, 호환 shim, `deprecated` 경로
- 구현을 그대로 베낀 테스트, 모의 객체가 실제 동작을 대체한 테스트
- 요청 없는 설정 항목, 기능 플래그, 텔레메트리, 재시도
- 문서와 메시지의 마케팅 어조, 이모지
- 같은 파일에 이미 있는 관례 옆에 세운 두 번째 관례

### D. 정확성

논리 오류, 경합, 자원 누수, 잘못된 경계 조건, 오류 처리 누락, 깨진 호출자. 지적에는 재현 시나리오나 반례를 붙인다.

## 심각도

- `blocker`: 의도한 경우가 틀렸다. 수용 기준 미충족, 계약 위반, 범위 밖 구현, 또는 실제 사용에서 도달하는 결함이다. 결함에는 촉발 조건(누가 무엇을 할 때), 소비자가 보는 결과, 현재 규모를 적는다.
- `should`: 의도 안에서 호출자가 실제로 겪을 버그, 또는 이 diff가 더한 요청 없는 복잡성과 slop(삭제나 축소가 수정이다).
- `nit`: 나머지 전부다. 다른 경로, 드문 경우, 작은 성능, 추가 호환, 현재 규모 밖의 가정, 이름과 서식, `convention:` 표기가 여기에 속한다. 도구가 강제하는 서식은 적지 않는다.

라벨은 리뷰어가 붙이지만 판정은 작성자가 다시 한다. 다른 경로, 드문 경우, 작은 비용은 어떤 라벨로 왔든 `nit`이다.

## 리뷰어 브리프

자식은 대화 기록을 받지 않으므로 브리프가 아는 전부다. 상태 디렉터리의 `review-brief-<n>.md`로 저장하고, `delegate_task`에는 본문 전체를 `task`로, T3 밖의 `codex/review.ts`에는 `--brief "Read <절대 경로> and carry it out exactly."`로 보낸다.

```markdown
# <slug> review round <n>

Review only. Do not edit files, commit, push, comment on MRs or PRs, ask a person, or start subagents.
You see this change for the first time; the author's explanation is not included.

## Input
- Repository (absolute): <path>   Base: <sha>   Head: <sha or "working tree">
- Risk tier: <review-tier.sh first line>
- Diff: <absolute path to saved diff>; commits: <absolute path>. Read surrounding code as needed.
- Intent: <1-2 sentences>   Out of scope: <list>
- Acceptance criteria and contract: <verbatim>
- Checks already run: <command → result; missing or pre-failing checks>
- Repository conventions: <paths>. Read only the sections the diff touches.
(round 2+) - Ledger: <ledger rows with fixed:/disagree:/declined: and evidence>
(round 2+) - Changed since last round: <absolute path to incremental diff>. Review open ids and changed code only; mark each old id `resolved` or `still open: <reason>`.

## Criteria
<paste sections A-D and the severity definitions of references/review.md verbatim>
Hold the change to the smallest version that meets the intent. Flag code, tests, or guards the intent does not need.

## Reply format (exactly)
VERDICT: APPROVE or CHANGES
TIER: security        (only when the change touches a security boundary the tier above missed)
S1 [blocker|should|nit] <file>:<line> <claim>. Fix: <suggestion>
S2 ...
(stable ids across rounds; no findings → only the VERDICT line)
REVIEW_DONE
```
