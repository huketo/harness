#!/usr/bin/env bash
# 서비스 supervisor. 지금은 설정을 읽어 서비스를 한 번 띄우기만 한다.
set -u

ENV_FILE="config/service.env"

if [[ -f $ENV_FILE ]]; then
  set -a
  source "$ENV_FILE"
  set +a
fi

node service/server.js
