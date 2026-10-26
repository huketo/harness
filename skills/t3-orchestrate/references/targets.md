# 실행 대상과 T3 도구 레시피

용도별 제공자·모델 대응과 T3 Orchestration 도구 조합이다. 아래 표는 2026-10-26의 `orchestrator_capabilities` 카탈로그로 확인한 시작점이다. 실행마다 `orchestrator_capabilities`를 다시 호출하고, 표와 다르면 카탈로그를 따른 뒤 `run.md`에 실제 선택을 적는다. 다른 모델은 `search` 인자로 찾는다.

## 용도별 대상

`target`에는 `providerInstanceId`, `model`, `options`를 모두 명시한다. 옵션 ID와 값은 카탈로그가 광고한 것만 쓴다. Antigravity 모델은 effort가 모델 ID에 들어 있어 옵션이 없다.

| 용도 | providerInstanceId | model | options |
| --- | --- | --- | --- |
| `orchestrate`, `frontend`, `opus-code` | `claudeAgent` | `claude-opus-5-5` | `{effort: "high"}` |
| `opus-general` | `claudeAgent` | `claude-opus-5-5` | `{effort: "medium"}` |
| `hard-code`, `best` | `claudeAgent` | `claude-opus-5-5` | `{effort: "xhigh"}` |
| `sonnet-code` | `claudeAgent` | `claude-sonnet-5-5` | `{effort: "medium"}` |
| `economical` | `claudeAgent` | `claude-haiku-5-5` | `{effort: "high"}` |
| `code` | `codex` | `gpt-6.1-sol` | `{reasoningEffort: "medium"}` |
| `general` | `codex` | `gpt-6.1-sol` | `{reasoningEffort: "low"}` |
| `agy-work`, `mechanical`, `search`, `media` | `antigravity` | `gemini-3.8-flash-high` | 없음 |
| `automation` | `antigravity` | `gemini-4-argon-low`(판단이 필요하면 `-medium`, `-high`) | 없음 |
| `agy-review`, `agy-hard` | `antigravity` | `gemini-4-argon-high` | 없음 |

- `fallback`(AGY의 Claude Opus)에 해당하는 T3 대상은 없다. T3의 Antigravity 카탈로그에 Claude 모델이 없기 때문이다. Claude 예산이 바닥났을 때 다른 계정의 Claude 인스턴스를 쓰는 것은 그 계정의 한도를 소비하므로 사람이 그 인스턴스를 지정했을 때만 한다.
- 모델 계열은 실행기가 아니라 모델로 센다. `claudeAgent`와 다른 계정의 Claude 인스턴스는 같은 Claude 계열이다. 독립 리뷰와 카운슬에서 서로 다른 목소리로 세지 않는다.
- 결과의 `providerInstanceId`, `model`, `options`가 요청과 같은지 확인한다. 다르면 능력 불일치로 기록하고 그 결과를 해당 용도의 근거로 쓰지 않는다.

## 실행 모드

자식은 부모의 실행 모드를 상속한다. 상속한 모드를 대상 제공자가 지원하지 않으면 그 제공자가 지원하는 가장 넓은 모드로 내려간다. Antigravity에는 Auto 모드가 없으므로 Auto 스레드에서 상속하면 승인 대기 모드가 되어 첫 도구 호출에서 멈춘다. Antigravity 자식에는 `runtimeMode: "full-access"`를 명시하며, 이것은 부모 스레드가 Full access일 때만 허용된다. 부모가 Full access가 아니면 Antigravity 대신 Claude나 Codex 대상을 고른다.

`approval-required`와 `auto-accept-edits`는 읽기 전용 스위치가 아니다. 자식이 승인을 기다리며 멈출 뿐이다. 범위 제한은 브리프와 워크트리 격리로 하고, 읽기 전용 리뷰는 아래 제한 리뷰어로 한다.

## 워커 위임

```text
delegate_task(
  task: <brief.md 본문 전체>,
  title: "<run>/<slice>",
  role: "implementation",
  isolation: "worktree",
  mode: "async",
  target: {providerInstanceId, model, options},
  clientRequestId: "<run>-<slice>-w<n>"
)
```

- `isolation: "worktree"`는 부모의 현재 로컬 커밋에서 새 체크아웃을 만든다. 커밋하지 않은 변경은 복사되지 않으므로, 브리프가 기대는 계약·스크립트는 위임 전에 커밋한다.
- 브리프는 파일 경로가 아니라 `task` 본문으로 보낸다. 자식이 아는 것을 위임 기록 한곳에 남기고, 상태 디렉터리 쓰기를 오케스트레이터 한 명으로 제한하기 위해서다. 자식은 상태 디렉터리의 diff 같은 입력을 절대 경로로 읽을 수 있다. 오케스트레이터는 같은 본문을 `<state>/slices/<slice>/brief.md`에 남긴다.
- Antigravity 자식은 T3 아래에서 저장소 `AGENTS.md`와 사용자 규칙을 로드하지 않고 작업 디렉터리도 워크트리가 아닐 수 있다. Antigravity 브리프에는 필요한 저장소 규칙을 직접 적고 모든 경로를 절대 경로로 준다.
- `clientRequestId`는 회차마다 다르게, 같은 회차의 재시도에서는 같게 둔다. 돌아온 `taskId`와 `childThreadId`를 `run.md`에 적는다.
- 웨이브는 위임 호출을 한 응답에 나란히 보낸다. 그다음 턴을 끝낸다. 비동기 자식의 완료는 알림으로 이 스레드를 깨우므로 `task_status` 반복 호출이나 감시 루프를 만들지 않는다. 턴 안에서 결과가 꼭 필요할 때만 `task_status`를 한 번 읽는다.
- `task_status`의 `workState`가 `result_available`이고 `summary`의 마지막 줄이 `REPORT_DONE`일 때만 보고가 완료된 것이다. `waiting_for_children`은 완료가 아니다. `summary`를 `<state>/slices/<slice>/report.md`로 저장한다.
- 자식의 브랜치와 워크트리 경로는 보고의 "브랜치" 절과 `t3_worktree_list`로 확인한다. 추측하지 않는다. 자식 워크트리는 같은 저장소의 워크트리(`~/.t3/worktrees/<repo>/t3-<id>`)이므로 브랜치 이름으로 바로 머지된다.
- `hasPendingQuestion`이나 `pendingApproval`이 보이면 `t3_pending_request_read`로 원문을 읽는다. 이미 승인된 범위의 답만 `t3_pending_request_respond`로 보낸다. 자식의 승인 요청은 부모에게 승인 권한을 주지 않는다. 사람의 결정이 필요하면 저장소의 HITL 규칙대로 묻는다.
- 막힌 자식을 멈출 때는 `task_cancel`을 쓴다. 원 워크트리와 커밋은 보존한다.

## 재리뷰와 후속 회차

같은 자식 스레드에 `t3_thread_send`로 이어 보내지 않는다. 회차마다 `delegate_task`를 새로 호출하고, 원래 브리프, 이전 판정의 확인된 항목, 워커의 응답, 남은 반론을 프롬프트에 모두 넣는다. 고치는 회차의 워커는 이전 회차의 브랜치를 기준으로 시작해야 하므로, 오케스트레이터가 그 브랜치를 자기 워크트리로 가져와 커밋한 뒤 위임하거나 브리프에 기준 브랜치를 명시한다.

## 제한 리뷰어

T3에는 읽기 전용 실행 모드가 없다. 리뷰어 선택, `codex/review.ts` 실행 명령, 다른 제공자의 워크트리 위임과 사후 `tree-unchanged.sh` 확인은 `review-loop` 스킬과 그 `references/review.md`의 "실행 권한"이 소유한다. `codex/review.ts`는 바깥에서 `timeout`을 두고 돌리며, 시간 초과는 리뷰 실패로 센다. `--model`을 생략하면 `codex debug models`에서 현재 Sol을 고르고, 지정하면 정확한 slug만 받는다.

## 다른 T3 도구

- `t3_thread_launch`: 사람이 별도 스레드나 PR 스택을 요청했을 때 독립 최상위 스레드를 만든다. 슬라이스 워커에는 쓰지 않는다. `workspaceStrategy`를 명시하고(`{type: "worktree", baseRef, branch, startFromOrigin: false}`), 돌아온 `threadId`를 보관한다. 재시도 키가 없으므로 응답을 잃었으면 `t3_thread_list`로 먼저 확인한다.
- `t3_thread_fork`/`t3_thread_merge_back`: 오케스트레이터 자신의 맥락에서 대안 접근을 따로 시험하고, 채택한 결과의 맥락만 원래 스레드로 되돌릴 때 쓴다. 코드 통합은 git으로 한다.
- `t3_worktree_list`/`t3_worktree_status`: 자식 워크트리의 경로·브랜치·변경 상태를 읽는다.
