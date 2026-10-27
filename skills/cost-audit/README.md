# cost-audit

Claude Code와 Codex CLI의 로컬 세션 JSONL에서 같은 기준선과 비용 낭비 패턴을 계산합니다. Python 3 표준 라이브러리만 사용하며 사용자 운용 데이터는 수정하지 않습니다.

## 실행

```bash
python3 skills/cost-audit/analyze.py --days 7 --format markdown
```

주요 선택지는 다음과 같습니다.

```text
--source claude|codex|all  기본값 all. 존재하는 소스만 포함합니다.
--claude-dir DIR          설정 디렉터리. 반복 가능. 기본은 존재하는 ~/.claude. 다른 계정의 설정 디렉터리는 이 옵션으로 더합니다.
--codex-dir DIR           기본 ~/.codex.
--rates PATH              기본 ~/.t3/userdata/usage-model-rates.json.
--days N                  조회 기간입니다. 기본값은 7일입니다.
--format markdown|json    출력 형식입니다. 기본값은 markdown입니다.
--out PATH                stdout 대신 파일에 씁니다.
--folder TEXT             folder에 TEXT가 포함된 프로젝트만 조회합니다.
--session VALUE           정확한 JSONL 경로나 세션 ID 앞글자로 좁힙니다.
--baseline                탐지기 없이 기준선만 계산합니다.
--ctx-threshold TOKENS    context_bloat 임계값입니다. 기본값은 400,000입니다.
```

상대 `--out` 경로는 레포 루트를 기준으로 해석합니다. 디렉터리 없는 파일명은 `var/audit/` 아래에 저장합니다. 예를 들어 `--out weekly.md`는 `var/audit/weekly.md`를 만들고, `--out var/audit/team.json`은 그 경로를 그대로 사용합니다.

## 탐지기

- `context_bloat`: `input_tokens + cache_read_tokens + cache_write_tokens`가 임계값을 넘는 요청을 찾고 `cost_cache_read`를 귀속합니다. 전체 요청의 평균·중위·p90·p99·최댓값도 제시합니다.
- `cache_rebuild`: `cache_write_tokens > 20,000`인 요청과 직전 동일 `session_file` 요청의 시간 간격을 계산합니다. 5분 초과, 5~60분, 60분 초과를 분리합니다. 1시간 보존의 순이익은 관측된 5~60분 재구축 비용에서 전체 캐시 쓰기에 대한 추정 프리미엄 증가분을 뺀 값입니다. 5분 1.25배와 1시간 2배는 추정 상수입니다.
- `model_misroute`: Opus를 사용한 subagent 요청을 파일별로 모으고 `--rates`의 Claude Haiku 5.5·GPT-6.1 Sol 단가를 적용하여 반사실 비용을 계산합니다. 로그에는 역할명이 없으므로 Haiku 절감액은 상한이고 Sol 결과는 별도 비교값입니다. 장문 구간 단가는 적용하지 않으므로 긴 요청의 절감액은 실제보다 크게 나올 수 있습니다.
- `low_effort_expensive`: Codex 요청과 직전 `turn_context`의 effort를 연결하여 Opus의 `minimal`·`low` 구간을 찾습니다. Opus 5.5의 기본값이자 하네스가 일반 작업에 쓰는 `medium`은 세지 않습니다. 근거로 Artificial Analysis Intelligence Index v4.3.2(2026-10-13)의 Opus 5.5 low 42/$0.55, GPT-6.1 Sol medium 48/$0.21, Claude Haiku 5.5 high 38/$0.08을 표시합니다. Terminal-Bench 4.0에서도 GPT-6.1 Sol medium(48%)이 Opus 5.5 low(31%)보다 높아, 이 비교에서는 Sol medium이 두 지수와 작업당 비용 모두에서 앞섭니다.
- `fat_tool_result`: 도구 이름별 결과 문자 수와 이후 동일 세션 요청 수를 합산합니다. 4문자당 1토큰으로 환산하고 이후 요청 모델의 cache-read 단가를 적용합니다.
- `error_and_retry_spend`: 오류·중단 계열 `stop_reason`이나 비어 있지 않은 `error_message`를 묶고 해당 요청의 명목 비용을 합산합니다.
- `compaction_churn`: 압축 이벤트의 압축 전 토큰 수(Claude `compactMetadata.preTokens`)와 바로 다음 요청의 캐시 쓰기를 연결합니다. 세션별 횟수와 60분 이내 최대 밀도로 우선순위를 정합니다.
- `idle_session_resume`: 동일 세션 요청 간격이 60분을 넘은 복귀 지점과 그 요청의 캐시 쓰기 비용을 모읍니다.

각 탐지기는 `id`, `title`, `severity`, `findings`, `estimated_usd`, `recommendation`을 공통으로 반환합니다. JSON에는 모든 finding을 담고, 사람이 읽는 Markdown에는 탐지기별 상위 10개만 표시합니다.

## 기준선과 주의 사항

보고서 상단에는 기간, 요청 수, 총 토큰, 모델별·소스별 지출(`model_spend`, `source_spend`), input·output·cache-read·cache-write 비용, 캐시 적중률, main·subagent 분해가 있습니다. 캐시 적중률은 다음 식을 사용합니다.

```text
cache_read_tokens / (input_tokens + cache_read_tokens + cache_write_tokens)
```

모든 금액은 구독 계정 사용량의 카탈로그 정가 환산치이며 실제 청구액이 아닙니다. 도구 결과의 문자 수는 토큰 수의 근사치이고, 압축 이후 토큰 수와 실제 cache prefix 경계는 데이터에 없습니다. `compaction`의 절감량과 도구 결과의 정확한 재전송 횟수는 계산할 수 없습니다.

로그가 없는 소스는 건너뛰고 최상위 `parse_warnings` 및 `limitations`에 기록합니다. 조회 결과가 비면 요청 수 0인 기준선을 반환합니다.

## 로컬 로그와 단가

Claude는 각 설정 디렉터리의 `projects/**/*.jsonl`을 읽고 `subagents/agent-*.jsonl`을 subagent로 구분합니다. 같은 `message.id`·`requestId` 응답의 반복 줄은 마지막 사용량과 종료 사유를 가진 한 요청으로 합치며 최초 timestamp를 유지합니다. 여러 설정 디렉터리에 복제된 동일 응답도 한 번만 셉니다. 도구 호출 ID를 결과와 연결하고 compact boundary·summary를 압축 이벤트로 읽습니다. `summary` 및 `isCompactSummary` 항목을 지원하며, boundary 뒤 다음 요청 전의 summary는 같은 압축으로 셉니다.

Codex는 `sessions/**/rollout-*.jsonl`의 `token_count.info.last_token_usage`만 합산합니다. `total_token_usage`는 반복 상태 알림을 구분하는 데만 쓰며 합산하지 않습니다. 직전 `turn_context`의 모델·effort와 세션 cwd를 유지하고 `session_meta.source.subagent`를 subagent로 분류합니다. 입력은 `input_tokens - cached_input_tokens`로 캐시를 제외합니다. 함수·custom 도구 결과와 `compacted`·compaction 이벤트도 읽습니다. 이전 요청 timestamp는 기간 필터를 적용하기 전에 계산합니다.

단가 파일은 LiteLLM 객체 또는 `{"fetchedAtMs": ..., "document": {...}}`를 받습니다. 정확한 모델 ID를 먼저 찾고 공급자 접두어가 붙은 키는 정확한 키가 없을 때만 보조로 사용합니다. `input_cost_per_token`, `output_cost_per_token`, `cache_read_input_token_cost`, `cache_creation_input_token_cost`는 per-token USD입니다. 단가가 없으면 경고와 함께 해당 금액을 0으로 저장하므로 비용 0을 무료 사용으로 해석하면 안 됩니다.

제공되지 않는 신호는 각 탐지기의 `details.unsupported_sources`에 표시합니다. Claude는 effort가 없고, Codex는 캐시 쓰기량과 요청에 연결된 종료·오류 상태가 없습니다. Codex의 압축 횟수·idle 간격은 관측할 수 있지만 후속 캐시 쓰기 비용은 계산할 수 없습니다. 빈 findings는 이 소스에서 문제가 없다는 뜻이 아닙니다. 권고는 하네스 중립적인 표현이므로, 설정을 바꾸기 전에 해당 하네스의 실제 설정 키를 확인합니다.

Antigravity는 저장 형식이 문서화되지 않아 미지원입니다. T3의 버전이 붙은 내부 `usage-scan-cache-*.json`은 읽지 않습니다.

실제 로그는 민감 자료입니다. 저장소 테스트는 합성 fixture만 사용하며, 호스트 스모크의 보고에는 집계 숫자나 키 목록만 남깁니다.

```bash
python3 -m unittest discover -s skills/cost-audit -p 'test_*.py' -v
```
