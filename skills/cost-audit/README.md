# cost-audit

OMP의 읽기 전용 통계 DB와 세션 JSONL을 결합하여 비용 낭비 패턴을 찾습니다. Python 3 표준 라이브러리만 사용하며 사용자 운용 데이터는 수정하지 않습니다.

## 실행

먼저 통계를 동기화합니다.

```bash
omp stats --summary
python3 skills/cost-audit/analyze.py --days 7 --format markdown
```

주요 선택지는 다음과 같습니다.

```text
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
- `model_misroute`: Opus를 사용한 subagent 요청을 파일별로 모으고 `models.db`의 Luna·Sol 단가와 long-context 구간을 적용하여 반사실 비용을 계산합니다. 통계에는 역할명이 없으므로 Luna 절감액은 상한이고 Sol 결과는 별도 비교값입니다.
- `low_effort_expensive`: JSONL의 `thinking_level_change`와 assistant 요청을 연결하여 Opus의 `minimal`·`low`·`medium` 구간을 찾습니다. 외부 기준에서 Opus low 58%/$1.66가 Luna max 67%/$0.61에 지배된다는 근거를 함께 표시합니다.
- `fat_tool_result`: 도구 이름별 결과 문자 수와 이후 동일 세션 요청 수를 합산합니다. 4문자당 1토큰으로 환산하고 이후 요청 모델의 cache-read 단가를 적용합니다.
- `error_and_retry_spend`: 오류·중단 계열 `stop_reason`이나 비어 있지 않은 `error_message`를 묶고 해당 요청의 명목 비용을 합산합니다.
- `compaction_churn`: JSONL의 `compaction.tokensBefore`와 바로 다음 요청의 캐시 쓰기를 연결합니다. 세션별 횟수와 60분 이내 최대 밀도로 우선순위를 정합니다.
- `idle_session_resume`: 동일 세션 요청 간격이 60분을 넘은 복귀 지점과 그 요청의 캐시 쓰기 비용을 모읍니다.

각 탐지기는 `id`, `title`, `severity`, `findings`, `estimated_usd`, `recommendation`을 공통으로 반환합니다. JSON에는 모든 finding을 담고, 사람이 읽는 Markdown에는 탐지기별 상위 10개만 표시합니다.

## 기준선과 주의 사항

보고서 상단에는 기간, 요청 수, 총 토큰, 모델별 지출, input·output·cache-read·cache-write 비용, 캐시 적중률, main·subagent 분해가 있습니다. 캐시 적중률은 다음 식을 사용합니다.

```text
cache_read_tokens / (input_tokens + cache_read_tokens + cache_write_tokens)
```

모든 금액은 구독 계정 사용량의 카탈로그 정가 환산치이며 실제 청구액이 아닙니다. 도구 결과의 문자 수는 토큰 수의 근사치이고, 압축 이후 토큰 수와 실제 cache prefix 경계는 데이터에 없습니다. `compaction`의 절감량과 도구 결과의 정확한 재전송 횟수는 계산할 수 없습니다.

DB가 없거나 조회 결과가 비어 있으면 분석기는 직접 동기화하지 않고 `omp stats --summary`를 실행하라는 오류를 반환합니다. `stats.db`와 `models.db`는 모두 SQLite URI의 `mode=ro`로 엽니다.
