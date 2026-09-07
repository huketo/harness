#!/usr/bin/env bash
# 서비스 supervisor. 설정을 읽어 서비스를 띄우고, 죽으면 정해진 횟수만큼 다시 띄운다.
# 서비스의 두 출력 스트림은 로그에 붙여 쓰고, 지금 돌고 있는 pid는 pid 파일에 남긴다.
set -u

ENV_FILE="service.env"
LOG_FILE="logs/service.log"
PID_FILE="logs/service.pid"
MAX_RESTARTS=3

if [[ ! -f $ENV_FILE ]]; then
  printf 'run.sh: 설정 파일이 없다: %s\n' "$ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

restarts=0
while :; do
  node service/server.js >> "$LOG_FILE" 2>&1 &
  child=$!
  printf '%s\n' "$child" > "$PID_FILE"

  wait "$child"
  status=$?

  if (( restarts >= MAX_RESTARTS )); then
    printf 'run.sh: 재시작 한도 %s회를 다 썼다. 마지막 종료 상태 %s\n' "$MAX_RESTARTS" "$status" >&2
    break
  fi
  restarts=$(( restarts + 1 ))
done
