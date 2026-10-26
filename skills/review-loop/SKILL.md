---
name: review-loop
description: 변경 하나를 작성자와 다른 모델 계열의 읽기 전용 리뷰어로 회차를 반복하며 검토할 때 사용한다. "review loop", "sol loop", MR·PR을 올리기 전 독립 리뷰, t3-orchestrate의 슬라이스 검수에 쓴다. 기준점 이후 변경의 표준·명세 점검만 원하면 code-review를 쓴다.
---

# Review loop

변경 하나를 독립 리뷰어에게 보여 주고, 지적을 근거로 판정하고, 고친 뒤 다시 보여 준다. 목표는 리뷰어를 달래는 것이 아니라 의도한 경우를 맞게 만드는 최소 변경이다. 리뷰가 범위를 키우면 밀어낸다. 리뷰 기준, 등급, 브리프 양식은 [references/review.md](references/review.md)가 소유한다.

## 1. 범위

1. `git status --short`로 작업 트리를 확인한다. 관련 없는 변경은 stash하거나 버리거나 리뷰에 섞지 않는다. 변경 경로가 깨끗하게 분리되지 않으면 멈추고 사람에게 묻는다.
2. 기준을 정한다. `git fetch origin` 뒤 MR·PR이면 그 대상 브랜치(`glab mr view <iid> -F json`의 `target_branch`, `gh pr view <n> --json baseRefName`)와의 merge-base, 로컬 변경이면 기본 브랜치와의 merge-base다. 원격이 없으면 사람이 지정한 기준이나 `HEAD`를 쓴다.
3. 모든 회차에서 같은 diff 명령 하나를 쓴다(기준부터 작업 트리까지, 추적되지 않은 파일 포함). 의도와 범위 밖을 1~2문장으로 적는다.
4. 변경을 덮는 검사를 돌린다. 이 변경이 깨뜨린 코드를 리뷰에 보내지 않는다. 없거나 원래 실패하던 검사는 브리프에 적는다.

상태 디렉터리는 `${XDG_STATE_HOME:-$HOME/.local/state}/review-loop/<slug>/`이며 `mkdir -m 700 -p`로 만든다. `t3-orchestrate` 안에서는 그 슬라이스 디렉터리를 쓴다. 여기에 diff, 브리프, 회차별 응답, 원장을 남긴다.

## 2. 등급과 예산

`scripts/review-tier.sh <repo> <base>`의 출력을 `review-tier.txt`로 저장한다. `none`이면 독립 리뷰 없이 생략 사유를 원장에 적고 끝낸다. `logic`은 3회, `security`는 5회가 상한이며, 데이터 손실이나 상태·동시성 변경은 근거를 적고 5회를 쓴다. 사람이 회차 수를 정하면 그것을 따른다.

1회차는 전체를 본다. 이후 회차는 바뀐 코드와 열린 지적만 본다. 회차가 `nit`만 돌려주면 일찍 멈춘다. 거절한 `nit`과 주석·문서·서식만 고친 수정에는 새 회차를 열지 않는다.

## 3. 리뷰어

리뷰어는 하나다. 사람이 리뷰어(제공자 인스턴스와 모델)를 지정하면 그대로 쓴다. 지정이 없으면 Codex의 현재 Sol 모델이다.

- **Codex(기본)**: `codex/review.ts`가 `codex debug models`에서 현재 Sol을 고르고 읽기 전용 샌드박스에서 실행한다. 다른 모델은 `--model <정확한 slug>`, effort는 `--effort`로 준다.

  ```sh
  bun --no-install <harness>/codex/review.ts --cwd <repo> --inspect-tools
  timeout 1200 bun --no-install <harness>/codex/review.ts --cwd <repo> \
    --brief "Read <state>/review-brief-<n>.md and carry it out exactly." > <state>/review-<n>.md
  ```

- **Claude(이 스레드가 Claude Code일 때)**: 하네스 플러그인의 `harness:reviewer` 하위 agent를 쓴다. 도구가 `Read`, `Grep`, `Glob`뿐이라 쓰기와 명령 실행이 도구 수준에서 막힌다. 모델은 이 스레드의 모델을 따르므로, 다른 Claude 모델을 지정받았으면 아래 `delegate_task` 경로를 쓴다. 회차마다 새 하위 agent를 띄우고 브리프 파일 경로를 준다.
- **다른 제공자**: T3 안에서는 `orchestrator_capabilities`로 지정 모델을 확인하고 `delegate_task`(`role: "review"`, `isolation: "worktree"`, `mode: "async"`, `target`에 제공자·모델·옵션)로 실행한다. 회차마다 새 `delegate_task`를 부르고 `clientRequestId`를 `<slug>-review-r<n>`처럼 회차마다 다르게 둔다. `childThreadId`는 저장소일 뿐 다음 회차의 대상이 아니다. `t3_thread_send`, `create_threads`, `t3_thread_launch`로 리뷰를 이어 가지 않는다. 워크트리 자식은 부모의 로컬 커밋에서 시작하므로, 커밋하지 않은 변경은 저장한 diff로만 전달된다는 점을 브리프에 적는다. 위임 직전에 `scripts/tree-unchanged.sh snapshot <이 워크트리> > <state>/git-before-r<n>.txt`를 남기고, 결과가 오면 `scripts/tree-unchanged.sh check <자식 워크트리> <시작 SHA> <state>/git-before-r<n>.txt`를 먼저 돌린다. Antigravity 자식에는 `runtimeMode: "full-access"`가 필요하고 하네스 규칙을 받지 못하므로 브리프에 규칙을 직접 적는다(`t3-orchestrate`의 `references/targets.md`).
- **T3 밖**: Codex 경로는 그대로 쓴다. Herdr 페인에서는 `herdr-orchestrate`의 `omp/review.ts` 제한 reviewer도 쓸 수 있다. 다른 제공자는 그 하네스의 하위 agent로 실행하고, 읽기 전용이 프롬프트 지시뿐이라는 사실을 원장에 적는다.

리뷰어는 작성자와 다른 모델 계열이어야 한다. 작성자가 Codex라서 기본값이 같은 계열이 되면 다른 계열의 플래그십을 고르고 그 사실과 이유를 원장에 적는다. 지정된 리뷰어에 닿을 경로가 없으면 막힌 사실을 보고한다. 다른 모델로 몰래 바꾸지 않는다.

리뷰가 도는 동안 범위 안의 파일을 고치지 않는다. 비동기 자식은 완료 알림을 기다리고 폴링하거나 두 번째 리뷰어를 띄우지 않는다. 시간 초과, 오류, 무응답은 승인이 아니다. 실패하면 취소하고 멈췄는지 확인한 뒤 원장을 넣어 다시 시작한다.

## 4. 지적에 답하기

각 지적의 전제를 코드에서 직접 확인하고 심각도를 다시 매긴다.

- 동의: 가장 작은 수정을 한다. 새 잠금·캐시·헬퍼·옵션보다 삭제나 축소를 우선한다. 일어난 경우를 고친다. 의도가 필요로 할 때만 수정 없이 실패하는 테스트 하나를 더한다.
- 반대: `file:line`, 테스트, 출력으로 이유를 적는다.
- 범위 밖이나 `nit`: 한 줄로 거절하고 후속 작업으로 남긴다. `convention:` 표기는 사람이나 `council`이 정할 결정 후보로 올린다.

원장(`ledger.md`)을 갱신한다. 행은 `id | 회차 | 심각도(재판정) | 결과 fixed/disagree/declined/open | 근거 | 사용량(리뷰어가 돌려줄 때만)`이다. 사용량은 추측하지 않는다.

검사를 다시 돌리고 `git diff --shortstat <base>`를 기록한다. 리뷰 때문에 diff가 커졌으면 먼저 줄인다. 루프를 끝내려고 동의하지 않는다.

## 5. 다음 회차

예산이 남아 있고, `blocker`나 `should`가 열려 있거나, 동작 코드가 바뀌었거나, 지난 승인이 현재 동작 diff를 덮지 못할 때만 연다. 브리프에는 1회차 브리프, 원장(`fixed:`/`disagree:`/`declined:`와 근거), 같은 기준 diff, 직전 회차 이후의 변경을 넣는다.

## 6. 종료

- **합의**: 현재 동작 diff에 `VERDICT: APPROVE`가 나왔고, 열린 `blocker`·`should`가 없고, 작성자에게도 남은 우려가 없다.
- **교착**: 같은 항목이 두 번의 답 뒤에도 다투어지거나 예산이 끝났다. 양쪽 입장을 각 2~3줄로 보여 주고 사람이 정한다. 예산 소진은 승인이 아니다.

루프 중에는 푸시하지 않는다. 합의 뒤 사람이 푸시·제출·MR 갱신을 요청했을 때만 올린다. MR·PR 본문에는 모델·하네스 줄 위에 한 줄을 넣는다. effort는 확인된 경우에만 적는다.

```text
Reviewed with review-loop: <N> rounds with <model>[ on <effort>]. Verdict: approved
```

보고에는 회차 수, 리뷰어(제공자·모델·옵션), 리뷰로 바뀐 것, 전후 diff 크기, 고친 지적과 거절한 지적과 그 이유, 사용량(없으면 없다고), 푸시 여부를 적는다.
