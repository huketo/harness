# 개인 하네스 전역 규칙

이 규칙은 Antigravity CLI(`agy`)의 모든 세션에 적용됩니다. 같은 사람이 `omp`와 Claude Code도 함께 쓰므로, 세 도구가 같은 스킬과 같은 판단 기준을 공유하도록 맞춥니다.

## 공유 스킬을 쓰는 방법

`~/.agents/skills`의 스킬은 `omp`, Claude Code와 함께 쓰는 자산이며 도구 이름이 `omp` 기준으로 적혀 있습니다. 스킬을 따를 때에는 절차와 판정 기준을 그대로 지키되, 도구 이름만 아래 대응표에 따라 바꾸어 실행합니다.

| 스킬에 적힌 이름 | Antigravity CLI에서 쓸 도구 |
| --- | --- |
| `read` | `view_file`, `list_dir`, `read_url_content` |
| `write` | `write_to_file` |
| `edit` | `replace_file_content` |
| `grep` | `grep_search` |
| `glob` | `find_by_name` |
| `bash`, `eval` | `run_command` |
| `web_search` | `search_web` |
| `ask` | `ask_question` |
| `task` | `define_subagent`, `invoke_subagent`, `manage_subagents` |
| `hub` | `send_message`, `manage_task`, `schedule` |
| `todo` | 별도 도구가 없으므로 응답 안에서 진행 상황을 적습니다 |

`skill://<이름>`은 `~/.agents/skills/<이름>/SKILL.md`를 가리킵니다. `omp` 전용 URI(`agent://`, `artifact://`, `xd://`)는 이 CLI에서 실행할 수 없으므로 해당 단계는 직접 수행합니다. 독립 에이전트가 필요하면 Herdr 안에서는 `harness-run agent`로 용도 프로필을 선택하여 보이는 세션을 만들고, Herdr 밖에서는 AGY의 `define_subagent`를 사용하되 별도 페인에서 볼 수 없음을 구분합니다.

## 실행과 모델 선택

Herdr 안(`HERDR_ENV=1`)에서는 실행이 오래 걸리거나, 사람이 진행 상황을 확인해야 하거나, 서버·디버거·REPL처럼 사람과 함께 조작해야 할 때만 명령을 탭/페인에서 실행합니다. 이때 `harness-run --help`로 실행 인자를 확인하고 현재 cwd와 사용자 포커스를 유지합니다. 짧은 조회·변환·검증은 `run_command`로 직접 수행합니다. 빌드·테스트라는 이유만으로 Herdr를 쓰지 않습니다. 독립 에이전트는 Herdr에서 확인·재사용할 수 있게 띄웁니다. 예약 실행은 스케줄러의 종료·로그 계약을 따릅니다.

용도별 모델 선택의 정본은 `omp-profile list`입니다. 영상·음악 해석과 웹 검색은 Flash의 `media`·`search`, 명세가 확정된 단순 작업은 `mechanical`, 정기 자동화는 `automation`, Claude 계정 사용량을 분산할 때는 AGY Opus 4.6의 `fallback`을 선택합니다. CLI마다 effort의 의미가 다르므로 OMP의 `max`를 AGY에 그대로 넘기지 않습니다.

다른 실행기나 모델로 작업을 넘길 때는 목표, 사용자 제약, 결정과 근거, 변경한 파일, 검증 결과, 남은 작업을 읽을 수 있는 인계문으로 전달합니다. 영상·음악 원본 경로와 타임스탬프를 함께 남기고 해석한 구간과 추론을 구분합니다. AGY의 실제 컨텍스트 상한과 압축은 CLI가 관리하므로 OMP 설정이 적용된다고 가정하지 않습니다.

Flash의 검색 결과는 원문과 출처 URL로 확인하고, 기계적 작업은 합의한 변경 범위를 그대로 수행합니다. Opus 4.6 Thinking fallback에서도 같은 완료 기준과 검증 수준을 유지하며, 짧은 계획과 변경 경로에 맞는 검증 결과를 남깁니다. fallback은 사용량을 부담하는 계정을 바꾸는 선택이지 작업 범위를 줄이는 선택이 아닙니다.

## 사람의 결정이 필요할 때

사람만 내릴 수 있는 결정은 `herdr-hitl` 스킬의 절차를 그대로 따릅니다. 그 스킬은 질문마다 채널을 먼저 확인하도록 요구하므로, 채널을 확인하지 않은 채 질문 경로를 임의로 고르지 않습니다. 저장소 맥락과 도구, 테스트로 풀 수 있는 사항은 사람에게 묻지 않고 직접 해결합니다.

`herdr-cron`이나 벤치마크 러너처럼 스케줄러가 띄운 무인 실행에서는 `herdr-hitl`을 호출하지 않습니다. 사람만 결정할 수 있는 사항이 나오면 그 작업을 멈추고 작업 트리를 일관된 상태로 남긴 뒤, 막힌 지점과 근거를 실행 출력에 남깁니다.

## 검증

동작을 바꾸었으면 실제로 실행해서 확인합니다. 버그를 고칠 때에는 먼저 재현하고 수정한 뒤 그 재현이 더는 일어나지 않는지 확인합니다. CLI나 스크립트를 바꾸었으면 그 명령을 직접 실행해서 결과를 봅니다. 확인하지 않은 내용을 확인한 것처럼 서술하지 않으며, 근거가 추론이라면 추론이라고 밝힙니다.
