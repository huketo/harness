---
name: t3-terminal
description: T3 Code 스레드에서 사람이 지켜보거나 직접 개입해야 하는 터미널 작업을 Herdr pane으로 열고 제어할 때 사용. dev server·watcher를 사람과 함께 지켜보기, 비밀번호·OTP·대화형 프롬프트·TUI·ssh처럼 사람이 입력해야 하는 명령이 대상. 한 번에 끝나는 명령이나 사람이 볼 필요 없는 백그라운드 실행은 제외. t3-code MCP 도구와 실행 중인 Herdr 서버 필요.
---

# T3 터미널

Herdr를 에이전트 멀티플렉서가 아니라 터미널 멀티플렉서로만 쓴다. 이 스레드가 Herdr 소켓 API로 workspace·tab·pane을 만들고 명령을 보내며, 사람은 자기 터미널에서 `herdr`로 접속해 같은 화면을 보고 필요하면 직접 입력한다.

## 쓰는 경우와 쓰지 않는 경우

쓴다:

- 사람이 출력을 함께 봐야 하는 장기 실행: dev server, watcher, 로그 tail, 배포 진행.
- 사람이 입력해야 하는 명령: 비밀번호·OTP·SSO 프롬프트, `ssh`, 대화형 설치기, REPL, TUI.
- 사람이 이어받아 조작할 셸을 준비해 두는 경우.

쓰지 않는다:

- 한 번 실행하고 끝나는 명령: Bash 도구로 실행한다. 종료 코드와 출력을 바로 받는다.
- 사람이 볼 필요 없는 장기 실행: Bash 도구의 백그라운드 실행이나 Monitor를 쓴다.
- pane 안에서 코딩 에이전트를 띄우는 일: `herdr agent` 명령은 쓰지 않는다. 병렬 위임은 `t3-orchestrate`나 `delegate_task`가 맡는다.
- 사람이 없는 예약 실행: 지켜볼 사람이 없으므로 이 스킬을 쓰지 않는다.

## 시작 전 확인

1. `orchestrator_capabilities`가 있는지 확인한다. 없으면 T3 스레드 밖이라고 말하고 멈춘다.
2. `herdr status`에서 `server: status: running`과 `endpoint_compatible: yes`를 확인한다. 서버가 없으면 직접 띄우지 말고, 사람에게 자기 터미널에서 `herdr`를 실행해 달라고 요청한다.
3. 명령 문법은 설치된 바이너리가 정본이다. 그룹 도움말은 `herdr pane --help`처럼 `--help`를 붙여 확인한다. 인자를 빼고 실행하면 기본값으로 실행되는 명령(`workspace create` 등)이 있으므로 탐색 목적으로 그렇게 실행하지 않는다.

상류 `herdr` 스킬은 `HERDR_ENV=1`인 pane 안에서만 동작하도록 막혀 있다. T3 스레드는 Herdr 밖에서 소켓으로 접속하므로 이 스킬의 규칙만 따른다.

## 배치와 식별

- 프로젝트(worktree) 하나에 workspace 하나를 쓴다. label은 `t3:<프로젝트나 브랜치>`로 짓는다. 먼저 `herdr workspace list`에서 같은 label을 찾아 재사용하고, 없을 때만 `herdr workspace create --cwd <작업 경로> --label <label> --no-focus`로 만든다.
- 작업 하나에 tab 하나를 쓴다. `herdr tab create --workspace <id> --cwd <작업 경로> --label <짧은 작업 이름> --no-focus`로 만들고, 한 화면에 둘 이상이 필요하면 `herdr pane split <pane> --direction right|down --cwd <경로> --no-focus`로 나눈다.
- ID는 생성 응답의 JSON에서 읽는다. `workspace create`는 `.result.workspace.workspace_id`, `.result.tab.tab_id`, `.result.root_pane.pane_id`를, `tab create`는 `.result.tab`과 `.result.root_pane`을, `pane split`은 `.result.pane.pane_id`를 돌려준다. 순서나 예시로 ID를 추측하지 않는다.
- 만든 workspace·tab·pane의 ID와 label을 턴 출력에 적어 둔다. 다음 턴에서는 `herdr tab list --workspace <id>`와 label로 다시 찾는다.
- 사람에게 위치를 알릴 때는 ID가 아니라 "Herdr의 `<workspace label>` workspace, `<tab label>` tab"처럼 label로 알린다.

## 명령 실행과 결과 확인

```bash
herdr pane run <pane> '<명령>; echo "__T3_EXIT=$?"'
herdr pane wait-output <pane> --regex '__T3_EXIT=[0-9]+' --source recent-unwrapped --timeout 120000
herdr pane read <pane> --source recent-unwrapped --lines 120
```

- 새로 만든 pane은 셸이 준비되기까지 몇 초가 걸린다. 그 사이에 보낸 `pane run`은 셸이 준비된 뒤에 실행되므로, 실행 여부는 보낸 직후가 아니라 `wait-output`으로 확인한다.
- `pane run`은 명령 문자열과 Enter를 한 번에 보낸다. 종료 코드는 위처럼 표식을 붙여 출력에서 읽는다. 표식 정규식은 `$?`가 펼쳐진 숫자만 맞추므로 화면에 남은 명령 줄과 겹치지 않는다.
- 끝나지 않는 명령(dev server 등)은 표식 대신 준비 완료 문구를 `--match`나 `--regex`로 기다린다. `--timeout`을 항상 지정한다. 지정하지 않으면 무기한 기다린다.
- 명령이 아직 실행 중인지는 `herdr pane process-info --pane <pane>`의 `foreground_processes`가 셸인지로 판단한다.
- 실행 중인 명령을 멈출 때는 `herdr pane send-keys <pane> ctrl+c`를 쓴다. 대화형 화면 조작도 `send-keys`의 논리 키 이름(`esc`, `enter`, `up` 등)으로 한다.
- 색이 근거일 때만 `--format ansi`로 읽는다.

## 사람에게 넘길 때

1. 넘기기 전에 pane이 사람이 입력할 지점(프롬프트, 확인 화면)에 도달했는지 `pane read`로 확인한다.
2. 사람에게 무엇을 해야 하는지와 위치를 [`docs/agents/hitl.md`](../../docs/agents/hitl.md)의 규칙대로 묻는다. 질문 도구가 있으면 그것으로 묻고, 선택지에 "완료했습니다"를 둔다.
3. 사람이 입력하는 동안 같은 pane에 `send-text`·`send-keys`·`run`을 보내지 않는다. 입력이 섞이면 되돌릴 수 없다.
4. 사람이 완료를 알리면 `pane read`로 결과를 확인하고 이어서 진행한다. 화면에서 비밀값이 보이면 출력이나 보고에 옮기지 않는다.

비밀번호, 토큰, OTP 같은 비밀값은 에이전트가 `send-text`로 입력하지 않는다. 그런 입력은 사람이 pane에서 직접 한다.

## 안전 규칙

- 이 스레드가 만든 workspace·tab·pane만 조작한다. 사람이나 다른 스레드의 pane에는 읽기 외의 명령을 보내지 않는다.
- 사람의 화면을 바꾸지 않는다. 생성에는 항상 `--no-focus`를 붙이고 `workspace focus`, `tab focus`, `pane focus`, `--focus`는 사람이 요청할 때만 쓴다.
- pane으로 보낸 명령은 Bash 도구의 권한 검사와 merge-guard hook을 거치지 않는다. 그래서 Bash 도구로 직접 실행할 수 없거나 승인이 필요한 명령(merge, push, 원격 쓰기, 삭제, 설정 변경)은 pane으로 우회하지 않는다. 그런 명령은 Bash 도구로 실행하거나 사람이 pane에서 직접 실행하게 한다.
- `herdr server stop`, `herdr session` 정리, 플러그인·integration 설치는 하지 않는다.
- `workspace close --group`은 쓰지 않는다.

## 정리

작업이 끝나면 이 스레드가 만든 tab을 `herdr tab close <tab>`으로 닫는다. tab을 닫으면 그 안에서 실행 중인 프로세스도 함께 종료되므로, 정상 종료 절차가 필요한 프로세스는 먼저 `ctrl+c`로 멈추고 셸이 프롬프트로 돌아온 것을 확인한 뒤에 닫는다. 사람이 그 tab을 계속 쓰고 있거나 dev server를 남겨 두라고 했다면 닫지 않고, 최종 응답에 위치와 남겨 둔 이유를 적는다. 빈 workspace는 이 스레드가 만든 경우에만 `herdr workspace close <id>`로 닫는다.
