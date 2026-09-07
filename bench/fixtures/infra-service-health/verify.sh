#!/usr/bin/env bash
# README-ops.md의 기동 조건 검증기. 외부 명령은 bash 내장과 node만 쓴다.
set -u

fail() {
  printf 'verify: FAIL %s\n' "$1" >&2
  exit 1
}

# ---------------------------------------------------------------- 상수 로드
[[ -f expected/contract.env ]] || fail 'expected/contract.env 가 없다'
# shellcheck disable=SC1091
source expected/contract.env
for name in EXPECTED_PORT EXPECTED_HEALTH_PATH EXPECTED_MAX_RESTARTS \
  STARTUP_TIMEOUT_SECONDS RESTART_TIMEOUT_SECONDS DOWN_WINDOW_SECONDS \
  LOG_FILE PID_FILE STDOUT_MARKER STDERR_MARKER; do
  [[ -n ${!name:-} ]] || fail "expected/contract.env 에 ${name} 이 없다"
done
HEALTH_URL="http://127.0.0.1:${EXPECTED_PORT}${EXPECTED_HEALTH_PATH}"
WORK_DIR=$(pwd -P)

# ------------------------------------------------------------- node 조각들
# 창 안에 헬스 경로가 200과 status=ok JSON을 주면 서버 pid를 표준 출력에 낸다.
# 요청 하나하나에 남은 기한을 AbortSignal 로 걸어 응답하지 않는 서버에서도 창을 넘기지 않는다.
IFS= read -r -d '' JS_WAIT_HEALTH <<'JS' || true
const url = process.env.TARGET_URL;
const deadline = Date.now() + Number(process.env.WINDOW_MS);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
(async () => {
  let last = "no attempt";
  for (;;) {
    const remaining = deadline - Date.now();
    if (remaining <= 0) {
      break;
    }
    const budget = Math.max(50, Math.min(remaining, 1000));
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(budget) });
      if (response.status === 200) {
        const body = await response.json();
        if (body && body.status === "ok" && Number.isInteger(body.pid)) {
          process.stdout.write(String(body.pid));
          process.exit(0);
        }
        last = `200 with unexpected body ${JSON.stringify(body)}`;
      } else {
        last = `status ${response.status}`;
      }
    } catch (error) {
      last = error.message;
    }
    await sleep(100);
  }
  process.stderr.write(`verify: 마지막 헬스 체크 실패 이유: ${last}\n`);
  process.exit(1);
})();
JS

# 창 안에 한 번이라도 TCP 접속이 되면 0, 창 내내 닫혀 있으면 1.
IFS= read -r -d '' JS_PROBE <<'JS' || true
const net = require("node:net");
const port = Number(process.env.TARGET_PORT);
const deadline = Date.now() + Number(process.env.WINDOW_MS);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const probe = () =>
  new Promise((resolve) => {
    const socket = net.connect({ host: "127.0.0.1", port });
    socket.setTimeout(300);
    socket.on("connect", () => {
      socket.destroy();
      resolve(true);
    });
    socket.on("timeout", () => {
      socket.destroy();
      resolve(false);
    });
    socket.on("error", () => resolve(false));
  });
(async () => {
  for (;;) {
    if (await probe()) {
      process.exit(0);
    }
    if (Date.now() >= deadline) {
      process.exit(1);
    }
    await sleep(100);
  }
})();
JS

IFS= read -r -d '' JS_SLEEP <<'JS' || true
setTimeout(() => {}, Number(process.env.MS));
JS

port_accepts() { # $1 = 창(초). 접속되면 0
  TARGET_PORT="$EXPECTED_PORT" WINDOW_MS=$(( $1 * 1000 )) node -e "$JS_PROBE"
}

wait_health() { # $1 = 창(초). 성공하면 서버 pid를 표준 출력에 낸다
  TARGET_URL="$HEALTH_URL" WINDOW_MS=$(( $1 * 1000 )) node -e "$JS_WAIT_HEALTH"
}

snooze() { MS="$1" node -e "$JS_SLEEP"; }

# ------------------------------------------------------------ procfs 유틸
read_stat() { # $1 = pid. "<state> <ppid> <pgrp> <comm>" 을 낸다
  local raw head_removed comm state ppid pgrp
  [[ -r "/proc/$1/stat" ]] || return 1
  read -r raw 2> /dev/null < "/proc/$1/stat" || return 1
  comm=${raw#*(}
  comm=${comm%)*}
  head_removed=${raw##*") "}
  read -r state ppid pgrp _ <<< "$head_removed"
  printf '%s %s %s %s\n' "$state" "$ppid" "$pgrp" "$comm"
}

process_alive() { # $1 = pid. 살아 있고 좀비가 아니면 0
  local state rest
  read -r state rest <<< "$(read_stat "$1")" || return 1
  [[ -n $state && $state != Z ]]
}

process_cmdline() { # $1 = pid. argv를 공백으로 이어 낸다
  local arg out=""
  [[ -r "/proc/$1/cmdline" ]] || return 1
  while IFS= read -r -d '' arg; do
    out+="$arg "
  done 2> /dev/null < "/proc/$1/cmdline"
  printf '%s' "$out"
}

process_cwd() { # $1 = pid
  (cd "/proc/$1/cwd" 2> /dev/null && pwd -P)
}

group_members() { # $1 = pgid. 그룹의 살아 있는 구성원을 "<pid> <comm>" 으로 낸다
  local dir pid state ppid pgrp comm
  for dir in /proc/[0-9]*; do
    pid=${dir#/proc/}
    read -r state ppid pgrp comm <<< "$(read_stat "$pid")" || continue
    [[ $pgrp == "$1" ]] || continue
    [[ $state == Z ]] && continue
    printf '%s %s\n' "$pid" "$comm"
  done
}

# strays — 이 사본을 작업 디렉터리로 쓰는 supervisor·서비스 프로세스를 "<pid> <pgrp> <argv>" 로 낸다.
# 후보가 프로세스 그룹이나 세션을 분리해도(setsid, detached spawn) 이 검사로 잡힌다.
# argv 낱말 단위로 대조한다. 부분 문자열 대조는 프롬프트 본문을 argv에 실은 에이전트 프로세스까지 잡는다.
process_is_service() { # $1 = pid. argv에 run.sh 또는 service/server.js 가 낱말로 있으면 참
  local arg
  while IFS= read -r -d '' arg; do
    case $arg in
      run.sh | */run.sh | service/server.js | */service/server.js) return 0 ;;
    esac
  done 2> /dev/null < "/proc/$1/cmdline"
  return 1
}

strays() {
  local dir pid cmd cwd state ppid pgrp comm
  for dir in /proc/[0-9]*; do
    pid=${dir#/proc/}
    [[ $pid == "$$" ]] && continue
    process_is_service "$pid" || continue
    cwd=$(process_cwd "$pid") || continue
    [[ $cwd == "$WORK_DIR" ]] || continue
    cmd=$(process_cmdline "$pid") || continue
    read -r state ppid pgrp comm <<< "$(read_stat "$pid")" || continue
    [[ $state == Z ]] && continue
    printf '%s %s %s\n' "$pid" "$pgrp" "$cmd"
  done
}

# escaped_children — supervisor 프로세스 그룹을 벗어난 이 사본의 프로세스를 낸다.
# 판정 전용이다. 회수는 cleanup이 무조건 하고, 위반은 회수 여부와 별개로 남는다.
escaped_children() {
  local pid pgrp cmd
  while read -r pid pgrp cmd; do
    [[ $pgrp == "${SUPERVISOR_PID:-}" ]] && continue
    printf '%s(pgrp=%s: %s) ' "$pid" "$pgrp" "$cmd"
  done < <(strays)
}

cleanup() {
  local pid comm pgrp cmd
  if [[ -n ${SUPERVISOR_PID:-} ]]; then
    kill -KILL -- "-${SUPERVISOR_PID}" 2> /dev/null
    while read -r pid comm; do
      kill -KILL "$pid" 2> /dev/null
    done < <(group_members "$SUPERVISOR_PID")
  fi
  # 그룹을 벗어난 프로세스도 반드시 거둔다. 남으면 다음 실행의 고정 포트를 오염시킨다.
  while read -r pid pgrp cmd; do
    kill -KILL "$pid" 2> /dev/null
  done < <(strays)
  return 0
}

trap cleanup EXIT INT TERM

kill_service() { # $1 = 서비스 pid, $2 = 시도 번호
  local pid=$1 attempt=$2 member comm found=""
  while read -r member comm; do
    [[ $member == "$pid" ]] && found=$comm
  done < <(group_members "$SUPERVISOR_PID")
  [[ -n $found ]] ||
    fail "서비스 pid ${pid} 가 supervisor 프로세스 그룹(${SUPERVISOR_PID})에 없다. 그룹 정리로 자식을 거둘 수 없다"
  kill -KILL "$pid" 2> /dev/null || fail "서비스 pid ${pid} 를 종료할 수 없다 (시도 ${attempt})"
  local waited=0
  while process_alive "$pid" && (( waited < 30 )); do
    snooze 100
    waited=$(( waited + 1 ))
  done
  if process_alive "$pid"; then
    fail "서비스 pid ${pid} 가 SIGKILL 뒤에도 살아 있다 (시도 ${attempt})"
  fi
  return 0
}

# ------------------------------------------------------------------ 로그 유틸
log_lines() { # 로그 줄 수
  local count=0 line
  [[ -f $LOG_FILE ]] || {
    printf '0'
    return 0
  }
  while IFS= read -r line || [[ -n $line ]]; do
    count=$(( count + 1 ))
  done < "$LOG_FILE"
  printf '%s' "$count"
}

log_marker_lines() { # $1 = 찾을 표시. 그 표시가 든 로그 줄 수를 낸다
  local marker=$1 count=0 line
  [[ -f $LOG_FILE ]] || {
    printf '0'
    return 0
  }
  while IFS= read -r line || [[ -n $line ]]; do
    [[ $line == *"$marker"* ]] && count=$(( count + 1 ))
  done < "$LOG_FILE"
  printf '%s' "$count"
}

log_body() {
  [[ -f $LOG_FILE ]] || return 1
  printf '%s' "$(< "$LOG_FILE")"
}

check_pid_file() { # $1 = 기대 pid, $2 = 단계 설명
  local recorded=""
  [[ -f $PID_FILE ]] || fail "${PID_FILE} 이 없다 (${2})"
  read -r recorded 2> /dev/null < "$PID_FILE" || fail "${PID_FILE} 을 읽을 수 없다 (${2})"
  [[ $recorded == "$1" ]] ||
    fail "${PID_FILE} 의 pid가 실제 서비스와 다르다: 파일=${recorded:-<빈 값>}, 헬스 응답=${1} (${2})"
  return 0
}

check_log_after_start() { # $1 = 지금까지의 기동 횟수, $2 = 이전 본문, $3 = 이전 줄 수, $4 = 단계
  local starts=$1 before_body=$2 before_lines=$3 stage=$4
  local now_body now_lines out_lines err_lines
  now_body=$(log_body) || fail "${LOG_FILE} 이 없다 (${stage})"
  now_lines=$(log_lines)
  # 후보가 자기 검증으로 남긴 줄은 기준선으로 빼고, 이 검증이 일으킨 기동만 센다.
  out_lines=$(( $(log_marker_lines "$STDOUT_MARKER") - BASE_OUT_LINES ))
  err_lines=$(( $(log_marker_lines "$STDERR_MARKER") - BASE_ERR_LINES ))
  if [[ -n $before_body && $now_body != "$before_body"* ]]; then
    fail "${LOG_FILE} 이 덮어써졌다. 이전 실행의 줄이 남아 있지 않다 (${stage})"
  fi
  if (( now_lines <= before_lines )); then
    fail "${LOG_FILE} 에 새 줄이 붙지 않았다: 이전 ${before_lines}줄, 지금 ${now_lines}줄 (${stage})"
  fi
  if (( out_lines != starts )); then
    fail "서비스 표준 출력이 기동마다 ${LOG_FILE} 에 남지 않는다: '${STDOUT_MARKER}' 줄 ${out_lines}개, 기동 ${starts}회 (${stage})"
  fi
  if (( err_lines != starts )); then
    fail "서비스 표준 오류가 기동마다 ${LOG_FILE} 에 남지 않는다: '${STDERR_MARKER}' 줄 ${err_lines}개, 기동 ${starts}회 (${stage})"
  fi
  return 0
}

# ------------------------------------------------------------------ 0. 선점
if port_accepts 0; then
  printf 'verify: 포트 %s 를 이미 다른 프로세스가 점유하고 있다.\n' "$EXPECTED_PORT" >&2
  printf 'verify: 검증은 127.0.0.1:%s 를 독점해야 한다. 그 프로세스를 먼저 정리해야 한다.\n' "$EXPECTED_PORT" >&2
  exit 1
fi

# --------------------------------------------------------- 1. supervisor 기동
[[ -f run.sh ]] || fail 'run.sh 가 없다'
[[ -d logs ]] || fail 'logs 디렉터리가 없다'
BASE_OUT_LINES=$(log_marker_lines "$STDOUT_MARKER")
BASE_ERR_LINES=$(log_marker_lines "$STDERR_MARKER")
BASE_LOG_BODY=$(log_body) || BASE_LOG_BODY=""
BASE_LOG_LINES=$(log_lines)
set -m
bash run.sh > logs/supervisor.out 2>&1 &
SUPERVISOR_PID=$!
set +m
# 작업 목록에서 떼어내 bash의 "Killed" 상태 알림이 진단을 덮지 않게 한다.
# 프로세스 그룹 id는 SUPERVISOR_PID 로 남으므로 그룹 정리에는 영향이 없다.
disown "$SUPERVISOR_PID" 2> /dev/null || true

if ! service_pid=$(wait_health "$STARTUP_TIMEOUT_SECONDS"); then
  fail "supervisor 기동 뒤 ${STARTUP_TIMEOUT_SECONDS}초 안에 GET ${EXPECTED_HEALTH_PATH} 가 127.0.0.1:${EXPECTED_PORT} 에서 200을 주지 않았다"
fi
check_pid_file "$service_pid" '첫 기동'
check_log_after_start 1 "$BASE_LOG_BODY" "$BASE_LOG_LINES" '첫 기동'
log_snapshot=$(log_body)
lines_snapshot=$(log_lines)

# --------------------------------------------- 2. 강제 종료 후 재시작 확인
for (( attempt = 1; attempt <= EXPECTED_MAX_RESTARTS; attempt++ )); do
  kill_service "$service_pid" "$attempt"
  if ! next_pid=$(wait_health "$RESTART_TIMEOUT_SECONDS"); then
    fail "강제 종료 ${attempt}회 뒤 ${RESTART_TIMEOUT_SECONDS}초 안에 서비스가 다시 뜨지 않았다 (재시작 한도 ${EXPECTED_MAX_RESTARTS}회)"
  fi
  if [[ $next_pid == "$service_pid" ]]; then
    fail "강제 종료 ${attempt}회 뒤에도 같은 pid(${next_pid})가 응답한다"
  fi
  service_pid=$next_pid
  check_pid_file "$service_pid" "재시작 ${attempt}회"
  check_log_after_start $(( attempt + 1 )) "$log_snapshot" "$lines_snapshot" "재시작 ${attempt}회"
  log_snapshot=$(log_body)
  lines_snapshot=$(log_lines)
done

# ------------------------------------------ 3. 한도 초과 뒤에는 재시작 금지
kill_service "$service_pid" $(( EXPECTED_MAX_RESTARTS + 1 ))
if port_accepts "$DOWN_WINDOW_SECONDS"; then
  fail "재시작 한도 ${EXPECTED_MAX_RESTARTS}회를 넘긴 뒤에도 서비스가 다시 떴다"
fi
if process_alive "$SUPERVISOR_PID"; then
  fail "재시작 한도를 다 쓴 뒤에도 supervisor(${SUPERVISOR_PID})가 살아 있다"
fi

# --------------------------------------- 4. 그룹 이탈 판정, 정리, 잔여 프로세스
# 판정을 먼저 굳히고 회수는 그 뒤에 한다. 회수에 성공했다는 사실이 위반을 지우지 않는다.
escaped=$(escaped_children)
cleanup
snooze 500
leftovers=""
while read -r pid comm; do
  leftovers+="${pid}(${comm}) "
done < <(group_members "$SUPERVISOR_PID")
if [[ -n $leftovers ]]; then
  fail "정리 후에도 프로세스 그룹 ${SUPERVISOR_PID} 에 남은 프로세스가 있다: ${leftovers}"
fi
stray_list=""
while read -r pid pgrp cmd; do
  stray_list+="${pid}(${cmd}) "
done < <(strays)
if [[ -n $stray_list ]]; then
  fail "정리 후에도 이 사본을 쓰는 프로세스가 남아 있다: ${stray_list}"
fi
if port_accepts 0; then
  fail "정리 후에도 포트 ${EXPECTED_PORT} 가 접속을 받는다"
fi
if [[ -n $escaped ]]; then
  fail "supervisor 프로세스 그룹(${SUPERVISOR_PID})을 벗어난 프로세스가 있었다: ${escaped}— 검증기가 회수했지만 기동 조건 위반이다"
fi

printf 'verify: OK 기동·헬스 200·재시작 %s회(기동마다 두 스트림 로그 append, pid 파일 갱신)·한도 초과 후 정지·그룹 이탈 없음·프로세스 정리 확인\n' "$EXPECTED_MAX_RESTARTS"
exit 0
