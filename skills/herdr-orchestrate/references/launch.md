# 실행 레시피

herdr 명령 조합과 실행기별 주의 사항이다. 인자 문법이 의심되면 `herdr <group>`으로 현재 바이너리를 확인한다. 응답은 JSON이며 ID와 경로는 응답에서 읽는다. 기계마다 다른 값(모델 이름, 설정 파일의 현재 값, 경로)은 적지 않고 확인 명령만 적는다.

## 워크스페이스·페인 만들기

```sh
# 슬라이스 워크트리 = 새 워크스페이스
herdr worktree create --workspace "$HERDR_WORKSPACE_ID" \
  --branch orch/<run>/<slice> --base <ref> --label <run>/<slice> --no-focus
# -> .result.workspace.workspace_id, .result.root_pane.pane_id,
#    .result.workspace.worktree.checkout_path (워크트리 경로; 이 값을 쓴다)

herdr tab rename <ws>:t1 work
herdr pane rename <ws>:p1 "worker:<slice>"

# 검증 페인: 워커 페인 아래에 같은 cwd로
herdr pane split --pane <ws>:p1 --direction down --cwd <worktree path> --no-focus
# -> .result.pane.pane_id ; 이어서 pane rename "verify:<slice>"

# 리뷰 탭
herdr tab create --workspace <ws> --cwd <worktree path> --label review --no-focus
# -> .result.root_pane.pane_id ; pane rename "review:<slice>"

herdr worktree remove --workspace <ws>          # 통합 뒤 정리
herdr worktree list --cwd "$PWD"                 # 열린 워크트리와 워크스페이스 대응
```

## omp 에이전트

```sh
herdr agent start <name> --kind omp --pane <pane> -- --approval-mode yolo [--model <계열>]
herdr agent prompt <name> "Read <절대경로>/brief.md and carry it out exactly." --wait --timeout 1800000
herdr agent read <name> --source recent-unwrapped --lines 120
```

- `--wait`는 `idle`/`done`/`blocked` 중 첫 안정 상태에서 돌아온다. omp 확장의 `screen_detection_skipped: true`는 생명주기 보고 경로를 뜻하며, 개별 요청의 산출물 완성을 증명하지 않는다. 실행 중 steering을 보냈다면 이전 생성의 종료와 인계 답변의 완료를 구분한다.
- 여러 줄 프롬프트도 받지만, 브리프는 파일로 두고 프롬프트는 한 줄로 유지한다. agy와 같은 규약을 쓰기 위해서다.
- `omp-profile`이 설치되어 있으면 `omp-profile list`로 용도를 고르고 `omp-profile selector <용도>`가 반환한 전체 `provider/model:effort`를 `--model`에 넘긴다. 없으면 `omp models`로 확인하여 전체 셀렉터와 effort를 명시한다. 리뷰어는 워커와 모델 계열이 다른 후보를 고른다. 역할 설정이나 전역 기본 모델은 바꾸지 않는다.
- `--approval-mode yolo`는 승인창을 없앤다. 워크트리 안에서만 일하는 브리프에 쓴다.
- 이미 `blocked`인 에이전트에 `prompt`를 보내면 `agent_blocked`로 거절된다. 먼저 `agent read`로 화면을 읽고 `send-keys`로 답한다.
- 제공자 오류나 `working` 정체가 반복되면 `agent get`/`agent read`로 현재 오류·진행·대기 중 입력을 확인한다. timeout만으로 세션이 복구 불가능하다고 단정하거나 같은 요청을 반복 전송하지 않는다. 인계가 필요하면 원 agent가 편집을 멈춘 사실과 남은 범위·승인·프로세스를 확보한 뒤 소유권을 옮긴다. 긴 답변이 화면에서 잘리면 임시 인계 파일을 요청한다. 생성 취소와 프로세스 종료는 다르며, 원 세션·dirty work는 보존한다.
- 제공자 전환은 실제 장애 근거와 기존 모델 승인 범위를 확인한 뒤 새 세션에서 한다. 오케스트레이터의 모델·effort를 임의로 바꾸지 않는다. 실제 모델 계열을 기록해 실행기만 다른 같은 계열을 독립된 목소리로 세지 않는다.
- `send-keys <name> ctrl+c ctrl+c`는 omp와 agy 모두를 종료한다. 종료되면 에이전트 이름이 풀리고 페인은 셸 프롬프트로 돌아온다.

## 제한 reviewer

일반 `reviewer` 역할이나 `--approval-mode yolo`는 읽기 전용 권한 경계가 아니다. 리뷰에는 Harness SDK 진입점을 사용한다. PATH의 실제 `omp` 설치에서 SDK를 해석하므로 별도 패키지 다운로드나 설치본 패치가 필요하지 않다.

```sh
bun --no-install <harness>/omp/review.ts \
  --cwd <worktree> --profile <purpose> --inspect-tools
bun --no-install <harness>/omp/review.ts \
  --cwd <worktree> --profile <purpose> \
  --brief "Read <state>/slices/<slice>/review-brief.md and review its supplied diff."
```

`--inspect-tools`는 모델을 호출하지 않는다. enabled/registered/bridge 목록은 모두 `glob`, `grep`, `read`이며 mounted tools·extensions는 비고 MCP는 꺼져 있어야 한다. bridge 목록이 존재해도 eval 도구는 등록하지 않는다. 다른 capability가 보이면 진입점이 모델 호출 전에 거부한다.

`--model <provider/id>`와 `--thinking <effort>`는 이번 reviewer에만 적용하는 명시적 override다. 모델은 정확한 provider/id가 일치해야 하며 축약·오타를 다른 모델로 대체하지 않는다. 그 외에는 프로필의 저장된 선택을 따른다. effort 선택자가 없는 프로필을 OMP 모델로 전환할 때는 `--thinking`도 지정한다. native 압축 순서는 이 프로세스의 읽기 전용 설정에서 `remote/handoff/soft`로 제한하며, 전역 설정과 계정·압축 확장을 변경하지 않는다. 파일·artifact 읽기는 유지한다.

stdout의 최종 판정은 오케스트레이터가 review 파일로 저장한다. 실패한 프로세스나 빈 출력을 완료로 세지 않는다. 이 경로는 모델 도구의 capability 경계이며 OS 파일 읽기 sandbox나 자격증명 격리를 뜻하지 않는다.

## agy 에이전트

```sh
herdr agent start <name> --kind agy --pane <pane> -- --model <agy-model-id> --add-dir <state>
herdr agent prompt <name> "Read <절대경로>/brief.md and carry it out exactly; write the result to <절대경로>/report.md." --wait --timeout 900000
```

- 프롬프트는 반드시 한 줄이다. 줄바꿈이 있으면 제출되지 않고 `agent_prompt_stalled`로 끝난다.
- 모델은 `omp-profile show search`·`media`·`fallback` 또는 `agy models`로 확인한 ID를 `--model`로 명시한다. `settings.json`의 UI 표시 이름과 CLI 모델 ID는 구분한다. `fallback`의 Claude와 OMP의 Claude는 실행기가 달라도 같은 계열이다.
- 승인창 없이 돌려면 같은 파일의 `toolPermission`이 `always-proceed`여야 한다. 기본값 `request-review`면 첫 명령에서 `blocked`가 된다. 띄우기 전에 값을 확인한다.
- 워크스페이스는 페인의 cwd다. 그 밖의 파일(상태 디렉터리)은 `--add-dir`로 열어야 파일 도구가 읽는다.
- Herdr는 agy의 상태를 화면으로 감지하므로 `done`이 완료의 증거가 아니다. 대화형 작업의 완료 판정은 `report.md`의 마지막 줄 `REPORT_DONE`으로 한다. 사람이 없는 실행은 `harness-run --help`의 AGY print 경로를 사용하여 프로세스 종료와 JSON 성공 상태를 모두 확인한다.
- agy는 대체 화면을 쓰므로 긴 답변은 `agent read --lines`를 늘려도 복구되지 않는다. 산출물은 항상 파일로 받는다.
- 응답이 끝난 뒤 CLI 경험 설문(`[1] Good ... [0] Skip`)이 뜰 수 있다. 다음 프롬프트 전에 `herdr agent send-keys <name> 0`으로 닫는다.
- 조사 브리프 양식(정확한 URL 요구, 미확인 허용)은 brief.md의 스카우트 브리프를 따른다.

## 명령 실행 페인

```sh
herdr pane run <pane> "<명령> ; echo EXIT=\$?"
herdr pane wait-output <pane> --match "EXIT=" --timeout 600000
herdr pane read <pane> --source recent-unwrapped --lines 200
```

`wait-output`은 이미 있는 출력에도 즉시 매치한다. 같은 페인에서 명령을 반복하면 매치 문자열에 회차 번호를 넣는다(`EXIT1=`, `EXIT2=`).

오래 걸리거나 사람이 확인·조작해야 하는 명령에만 `harness-run command -- <실행 파일> <인자...>`를 사용한다. 짧은 조회·변환·검증은 직접 실행하며, 빌드·테스트라는 이유만으로 페인을 만들지 않는다. 기존 워크트리 페인에서 실행해야 하면 그 페인을 명시한다. 실제 대기·읽기 인자는 `harness-run --help`로 확인한다. Herdr 경로는 실행별 종료 상태와 로그를 남기고 완료 후에도 페인을 보존한다. 재사용할 독립 에이전트는 `harness-run agent --profile <용도> --name <이름>`으로 띄운다.

## 여러 에이전트 기다리기

`agent prompt --wait`는 한 에이전트만 막는다. 웨이브를 띄울 때는 프롬프트를 `--wait` 없이 차례로 보내고, 그다음 에이전트마다 `agent wait`를 순서대로 부른다. 앞 에이전트를 기다리는 동안 나머지는 계속 일하므로 전체 대기 시간은 가장 오래 걸리는 하나의 시간이다.

```sh
for a in <run>-work-a <run>-work-b <run>-work-c; do
  herdr agent wait "$a" --timeout 1800000 | jq -c '{name: .result.agent.name, status: .result.agent.agent_status}'
done
```

`sleep`을 넣은 셸 루프, `agent list`·`pane read`·`wc`·`ps`를 반복하는 폴링은 쓰지 않는다. 상태 변화는 `agent wait`가 알려 준다. `agent list`는 웨이브 전체를 한 번 훑어볼 때만 쓴다.

`agent wait`가 돌아오면 상태별로 처리한다. `idle`/`done`이면 이번 요청의 `report.md`와 마지막 `REPORT_DONE`까지 확인한 뒤 슬라이스 루프로 넘긴다. `blocked`면 `agent read`로 원인을 본다. timeout은 승인·완료·종료의 증거가 아니다. 읽기에서 실제 진행이 확인되면 다시 기다리고, 같은 지점의 정체가 확인되면 원인 조사나 안전한 인계를 선택한다. `unknown`은 완료의 증거가 아니다.

CLI 읽기는 `done`을 `idle`로 바꾸지 않는다. 사이드바에 `done`이 쌓이는 것은 정상이다.

