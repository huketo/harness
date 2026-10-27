---
name: council
description: 서로 다른 모델 계열의 플래그십 셋에게 같은 변경·설계·계획을 읽기 전용으로 검토받고, 모두가 만족할 때까지 고치며 회차를 반복할 때 사용한다. "council", 여러 모델의 교차 검토, 되돌리기 비용이 큰 설계나 근거가 갈리는 선택지 검토에 쓴다. 단일 리뷰어 반복은 review-loop을 쓴다.
---

# Council

여러 계열의 위원이 같은 대상을 각자의 관점으로 검토하고, 이 스레드가 지적을 근거로 판정해 고친 뒤 다시 보여 준다. 표결이 아니다. 목적은 대상을 더 낫게 만드는 것이고, 결론은 위원 수가 아니라 확인된 근거가 정한다. 범위를 지키는 책임은 이 스레드에 있다.

## 1. 위원

기본 위원은 계열마다 플래그십 하나씩 셋이다. T3에서는 `orchestrator_capabilities`로 지금 카탈로그의 모델을 확인하고 고른다. 모델 ID를 외워서 쓰지 않는다.

| 계열 | 고르는 방법 | 실행 경로 |
| --- | --- | --- |
| Claude | `claudeAgent`의 최신 Opus, `effort: "high"` | `delegate_task`, 워크트리 격리 |
| OpenAI | `codex`에서 `-sol`로 끝나는 모델, `reasoningEffort: "high"` | `delegate_task`, 워크트리 격리 |
| Gemini | `antigravity`의 최신 플래그십 high 변형 | `delegate_task`, 워크트리 격리, `runtimeMode: "full-access"` |

- 사람이 지시나 `AGENTS.md`·`CLAUDE.md`에서 위원(제공자 인스턴스와 모델)을 정하면 그대로 쓴다.
- 계열은 실행기가 아니라 모델로 센다. `claudeAgent`와 다른 계정의 Claude 인스턴스는 같은 Claude 계열이므로 한 자리다.
- 위원에 닿을 수 없으면(카탈로그에 없음, 인증 실패, 부모가 Full access가 아니라 Antigravity를 띄울 수 없음) 그 사실을 바로 보고한다. 다른 모델로 몰래 바꾸지 않는다. 두 계열 이상이 남으면 사람에게 알린 상태로 계속하고 표에 `unavailable`로 남긴다. 한 계열만 남으면 멈춘다.
- T3 밖에서는 Codex 위원을 `review-loop`의 T3 밖 Codex 명령(`codex/review.ts`, `--effort high`)으로 실행하고, 나머지는 그 하네스의 하위 agent로 실행한다. 이때 읽기 전용은 프롬프트 지시뿐이라는 사실을 기록한다.

## 2. 대상과 브리프

1. 대상을 정한다: 기준 SHA부터의 diff, 설계 문서, 계획, 선택지 목록 가운데 하나다. 코드 변경이면 `review-loop`의 1절과 같은 방법으로 기준·diff·의도·범위 밖·검사 결과를 정하고, 위험 등급은 `review-loop`의 `scripts/review-tier.sh`로 기록한다.
2. 상태 디렉터리 `${XDG_STATE_HOME:-$HOME/.local/state}/council/<slug>/`를 `mkdir -m 700 -p`로 만들고 diff와 브리프를 저장한다. `t3-orchestrate` 안에서는 그 실행 디렉터리 아래 `council/<slug>/`를 쓴다.
3. [references/member-brief.md](references/member-brief.md)의 양식으로 위원 브리프를 쓴다. 세 위원에게 같은 본문을 준다. 첫 회차에는 서로의 존재와 이 스레드의 선호를 알리지 않는다.

## 3. 회차

1. 세 위원을 한 응답에서 나란히 시작한다. `delegate_task`는 `role: "review"`, `mode: "async"`, `isolation: "worktree"`, `clientRequestId: "<slug>-council-<계열>-r<n>"`이고 회차마다 새로 부른다. `t3_thread_send`로 이어 보내지 않는다. 위원을 셸 백그라운드 프로세스로 돌리지 않는다.
2. 턴을 끝내고 완료 알림을 기다린다. 위임 직전에 `review-loop`의 `scripts/tree-unchanged.sh snapshot`으로 공유 git 상태를 남기고, 결과가 오면 각 위원의 워크트리를 `tree-unchanged.sh check <워크트리> <시작 SHA> <스냅숏>`으로 확인한다. 실패하거나, 응답이 양식을 따르지 않거나, 시간이 초과되면 그 위원의 이번 회차는 `no score`다. 점수를 추측하지 않는다.
3. 응답을 `member-<계열>-r<n>.md`로 저장한다.

## 4. 판정과 수정

1. 위원의 응답을 읽기 전에 지적을 표로 모은다: `id | 위원 | 심각도 | 주장 | 근거 | 확인 결과`. 근거는 직접 열거나 실행해서 확인/미확인/반증으로 적는다. 미확인 근거는 무게가 없다. 잘 쓴 문장이나 여러 위원의 일치는 근거가 아니다. 한 위원만 낸 지적이라도 확인되면 받아들인다.
2. 지적에는 `review-loop`의 4절(동의하면 최소 수정, 반대하면 근거, 범위 밖과 `nit`은 거절하고 후속으로)을 그대로 적용한다. 심각도는 이 스레드가 다시 매긴다.
3. 범위 지키기: 회차가 거듭될수록 위원은 새 요구를 더한다. 의도에 없는 기능, 드문 경우의 방어, 추가 호환, 작은 성능은 거절하고 `ledger.md`에 후속으로 남긴다. 회차마다 `git diff --shortstat <base>`를 기록하고, 리뷰 때문에 diff가 커졌으면 먼저 줄인다.
4. 고친 것이 있으면 새 회차를 연다. 2회차부터 브리프에는 원장(`fixed:`/`disagree:`/`declined:`와 근거)과 직전 회차 이후의 변경을 넣고, 열린 지적과 바뀐 부분만 보라고 적는다.

## 5. 종료

- **만족**: 모든 위원이 현재 대상에 `VERDICT: SATISFIED`를 냈고, 열린 `blocker`·`should`가 없다.
- **교착**: 같은 지적이 두 번의 답 뒤에도 다투어지거나 5회차가 끝났다. 위원별 입장과 이 스레드의 입장을 각 2~3줄로 보여 주고 사람이 정한다. 이것은 만족이 아니다.

## 6. 결과 기록

결과가 MR·PR로 끝나면 본문의 모델·하네스 줄 바로 위에 아래 절을 넣는다. MR이 열려 있으면 현재 본문을 읽어 그 절만 바꾼 뒤 본문을 고친다(GitLab `glab mr update <iid> -y -d "$(cat <file>)"`, GitHub `gh pr edit <n> --body-file <file>`). 이 결과를 댓글로 올리지 않는다. MR이 없으면 같은 표를 최종 응답에만 쓴다.

```markdown
## Council review

Rounds: 2

| Member | Round 1 | Round 2 |
| --- | --- | --- |
| Claude Opus 5.5 | 7/10 | 9/10 |
| GPT-6.1-Sol | 8/10 | 10/10 |
| Gemini 4 Argon (High) | no score | 9/10 |
```

위원 이름은 카탈로그가 보여 주는 이름을 쓴다. 점수가 없으면 `no score`, 닿지 못한 위원은 `unavailable`이라고 쓴다.

최종 응답에는 회차 수, 위원별 실제 제공자·모델·옵션, 점수 표, 받아들인 지적과 거절한 지적과 이유, 남은 이견, 범위 변화(diff 크기 전후)를 적는다.

## 사람 개입

질문과 승인은 저장소의 T3 HITL 규칙(이 하네스에서는 `docs/agents/hitl.md`)을 따른다. 위원은 사람에게 묻지 않는다. 무인 실행이면 교착을 질문하지 않고 최종 응답에 남긴다. 카운슬의 권고는 새 권한을 주지 않는다.
