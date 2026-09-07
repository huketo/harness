# 모델 작업 벤치마크

이 디렉터리는 동일한 재생 가능 과제를 여러 에이전트 후보로 실행하고, 기계식 검증 결과와 비용을 함께 기록합니다. 후보는 OMP 모델 셀렉터이거나 Antigravity CLI 모델이며, OMP 후보에는 설정 오버레이 변형을 붙일 수 있습니다. 과제는 업무 부류(`class`)에 속하고, 문서 작성처럼 기계 검증만으로 품질을 가릴 수 없는 부류는 루브릭 심판이 추가로 채점합니다. 보고서는 합격률을 최대화하고 실제 작업당 비용을 최소화하는 2차원 Pareto 전선, 부류별 표, 부류 가중치로 합산한 하네스 점수, 그리고 부류마다 어떤 후보를 어떤 하네스 역할에 넣을지에 대한 라우팅 권고를 계산합니다.

## 빠른 시작

아래 명령은 모델을 호출하지 않고 기본 과제와 후보 모델의 조합, 카탈로그 단가 기반 추정 지출, 예산 상한을 출력합니다.

```bash
python3 bench/bench.py run --dry-run
```

실제 실행에서는 `--task`와 `--model`을 반복해서 범위를 좁힐 수 있습니다.

```bash
python3 bench/bench.py run \
  --task bugfix-python \
  --model openai-codex/gpt-5.6-luna:max \
  --model openai-codex/gpt-5.6-sol:high \
  --repeat 1 \
  --budget-usd 1.0
```

과제별 점수와 후보별 보고서는 다음 명령으로 확인합니다.

```bash
python3 bench/bench.py score
python3 bench/bench.py score --format json
python3 bench/bench.py report
python3 bench/bench.py report --format json
```

`report --format json`의 최상위 키는 `candidates`, `classes`, `harness_score`, `routing`입니다. `routing`의 권고를 `omp/config.apply.sh`에 반영하는 경로는 아래 "라우팅 제안" 절의 `routing` 서브커맨드입니다.

결과는 기본적으로 레포 루트의 `var/bench.db`에 누적됩니다. `run`, `score`, `report`, `routing`의 `--db` 인수로 다른 SQLite 파일을 지정할 수도 있습니다.

## 과제 부류

`classes.json`은 업무 부류 목록이며 부류마다 사람이 읽는 제목, 가중치 `weight`, 채점 방식 `grading`, 그 부류가 실제로 닿는 omp `modelRoles` 키 목록 `harness_roles`, `task.agentModelOverrides` 키 목록 `agent_overrides`를 담습니다. 가중치 합은 1.0 ± 0.001이어야 하고, `harness_roles`와 `agent_overrides`는 omp가 아는 키만 쓸 수 있습니다. 이 파일이 없으면 `run`, `score`, `report` 모두 오류로 종료합니다.

과제 JSON의 `class`는 이 목록에 있는 id여야 합니다. `grading`이 `verify`인 부류의 과제는 `verify` 명령만으로 판정하고, `rubric`인 부류의 과제는 `rubric` 블록을 반드시 가져야 합니다. 반대로 `verify` 부류의 과제에 `rubric`을 달면 로드가 실패합니다. 부류와 채점 방식이 엇갈린 과제를 미리 막기 위한 검사입니다.

부류 가중치는 보고서에서 두 곳에 쓰입니다. 하나는 하네스 점수(부류 가중치 × 그 부류의 관측 합격률의 합)이고, 다른 하나는 여러 부류가 같은 역할에 서로 다른 후보를 권고했을 때 어느 부류가 그 역할을 가져가는지입니다.

## GitLab 활동 수집

`bench/corpus/gitlab.py`는 `glab`으로 한 사용자의 프로젝트, 커밋, MR, 이슈, 이벤트를 모아 개발 활동 분포를 요약하는 선택 도구입니다. 기본 호스트는 `GITLAB_HOST`이며 값이 없으면 `gitlab.com`입니다. `--user`를 생략하면 선택한 호스트에 `glab`으로 인증된 계정의 `/user` 응답에서 사용자 이름과 ID를 가져옵니다.

```bash
glab auth status --hostname gitlab.com
python3 bench/corpus/gitlab.py collect --host gitlab.com
python3 bench/corpus/gitlab.py analyze
```

다른 공개 또는 자체 호스팅 GitLab은 `--host`를 바꾸고, 다른 공개 사용자를 조사할 때는 `--user USERNAME`을 명시합니다. 수집 범위는 기본적으로 최근 약 3년이며 `--since`와 `--until`로 바꿀 수 있습니다.

산출물은 레포 루트의 `var/corpus/gitlab/` 아래에 쌓이며 이 경로는 `.gitignore` 대상입니다. `--out`으로 다른 경로를 지정할 때도 버전 관리 밖에 둡니다. 프로젝트와 활동 내용이 들어갈 수 있으므로 산출물을 커밋하지 않습니다. 공개본의 부류와 가중치는 합성 과제를 비교하는 개인 설정으로만 사용하며 업무 분포의 통계적 추정치로 해석하지 않습니다. 설명은 `bench/TAXONOMY.md`, 기계가 읽는 값은 `bench/classes.json`에 있습니다.

## 후보 셀렉터와 변형

OMP 후보는 `<공급자>/<모델>:<사고강도>` 형태이며 `omp -p`로 실행합니다. Antigravity CLI 후보는 `agy/<모델-id>` 형태이고, 모델 id는 `agy models`가 출력하는 문자열을 그대로 씁니다. 사고 강도가 이미 모델 id에 들어 있으므로 접미사를 붙이지 않습니다.

```bash
python3 bench/bench.py run --model agy/gemini-3.8-flash-high --repeat 1
```

`agy` 후보는 `--output-format stream-json`으로 실행합니다. 완료 이벤트만 있는 `json` 출력과 달리 이 형식은 단계별 이벤트를 주므로 요청 수와 도구 호출 수를 셀 수 있습니다. 실행 전후로 `agy -p "/usage"`를 호출해서 주간 한도의 잔여 비율을 읽고, 그 차이를 `quota_fraction_used`에 기록합니다. `/usage` 자체는 모델을 호출하지 않으므로 한도를 쓰지 않습니다.

이 CLI는 실제로 응답한 모델을 별도로 알려주지 않고 요청한 id를 그대로 되돌려주므로, `agy` 후보의 라우팅 일치 검사는 실질적인 검증이 아닙니다. 폴백이 일어났는지도 확인할 수 없습니다.

OMP 후보에는 설정 변형을 붙일 수 있습니다. 후보 문자열은 `<공급자>/<모델>:<사고강도>@<변형>` 형태이고, 변형 이름은 `config.json`의 `variants`에 정의되어 있어야 합니다. 정의되지 않은 이름을 쓰면 실행이 시작되기 전에 오류로 끝납니다. `agy` 후보에는 설정 오버레이가 없으므로 `@변형`을 붙이면 오류입니다.

```bash
python3 bench/bench.py run --model "openai-codex/gpt-5.6-luna:max@cache-long" --task bugfix-python --repeat 1
```

변형은 같은 모델의 다른 설정을 별개 후보로 취급하기 위한 축입니다. 보고서의 그룹 키는 변형을 포함한 후보 문자열 전체이며, `runs` 테이블에는 후보 문자열과 별도로 `variant` 열이 남습니다. 지금 정의된 변형은 캐시 보존과 압축 임계 두 개이고 근거는 `docs/PRICING.md` §5입니다.

변형은 `modelRoles`, `task.agentModelOverrides`, `retry.fallbackChains`를 건드릴 수 없습니다. 이 세 경로와 그 상위·하위 키를 쓰는 변형은 설정 로드와 오버레이 생성 양쪽에서 오류가 됩니다. 이 고정과 빈 폴백 체인이 "한 실행은 한 후보의 측정"을 성립시키는 장치이므로, 변형이 그것을 옮기면 후보의 이름을 달고 다른 것을 측정하게 됩니다.

## 실행 격리와 안전장치

각 실행은 `tempfile.mkdtemp`로 만든 작업 디렉터리에 fixture를 복사한 뒤 진행합니다. 러너는 복사 전후의 원본 fixture 전체 해시를 비교하며, 원본 fixture를 직접 수정하지 않습니다. 또한 과제의 `protected_paths`에 기재된 테스트와 채점 자료가 작업 사본에서 바뀌면 테스트 명령이 성공해도 불합격으로 처리합니다.

러너는 먼저 깨끗한 작업 사본에서 `verify`를 실행합니다. 이 사전 검증이 성공하면 이미 풀린 과제이므로 모델을 호출하지 않고 오류로 종료합니다. 모델 실행 후에는 같은 작업 사본에서 `verify`를 다시 실행합니다. 합격 조건은 `verify` 종료 코드 0, 보호 파일 보존, 그리고 루브릭이 있는 과제라면 `quality_score >= pass_threshold`까지 세 가지를 모두 만족하는 것입니다. 루브릭 과제에서도 `verify`는 반드시 있고 형식과 결정적 사실을 검사하는 게이트 역할을 합니다.

OMP 후보 실행에는 임시 JSON 오버레이 파일을 만들고 다음 형태로 OMP를 호출합니다.

```text
omp -p <prompt> --config <temporary-overlay.json> --model <selector> --cwd <fixture-copy> --auto-approve --session-dir <dedicated-temp-directory> --max-time <seconds>
```

JSON은 YAML의 부분집합이므로 OMP의 `config.yml` 형식 오버레이로 읽힙니다. 오버레이는 `modelRoles`의 모든 역할(`default, slow, mid, smol, tiny, commit, plan, designer, advisor`)과 `task.agentModelOverrides`의 알려진 키(`scout, librarian, sonic, task, reviewer, security-reviewer`)를 모두 후보 셀렉터로 고정하고 `retry.fallbackChains`를 빈 객체로 비웁니다. 기본 역할만 고정하면 서브에이전트가 사용자 설정의 다른 모델로 돌아 후보 비교가 두 모델의 혼합이 되고, 폴백 체인을 남겨 두면 공급자 장애가 조용히 다른 모델로 갈아탑니다. 변형의 dotted 키는 중첩 객체로 바꿔 이 기본값 위에 마지막으로 덮어쓰지만, 위 세 경로는 변형이 옮길 수 없습니다. `--model`도 같은 후보를 명시합니다. 러너는 `~/.omp/agent/config.yml`을 쓰지 않고 `omp config set`도 호출하지 않습니다.

전용 세션 디렉터리는 시스템 임시 디렉터리에 남겨 두며, 데이터베이스의 `session_file`과 `session_files_json`에 경로를 기록합니다. 이 경로는 운영체제의 임시 파일 정리 정책에 따라 나중에 사라질 수 있습니다.

`agy` 후보에는 오버레이도 세션 디렉터리도 없습니다. 러너는 fixture 사본을 작업 디렉터리이자 `--add-dir` 대상으로 지정해서 다음 형태로 호출하고, 대화 기록은 `~/.gemini/antigravity-cli/conversations/<대화-id>.db`에 남으므로 그 경로를 `session_file`에 기록합니다.

```text
agy -p <prompt> --model <model-id> --output-format stream-json --dangerously-skip-permissions --add-dir <fixture-copy> --print-timeout <seconds>s
```

`--add-dir`는 생략할 수 없습니다. `agy` 1.1.25의 print 모드는 프로세스의 작업 디렉터리를 워크스페이스로 삼지 않고 `~/.gemini/antigravity-cli/scratch`에 뿌리를 둔 기본 프로젝트를 엽니다. 이 옵션이 없으면 에이전트는 빈 워크스페이스를 보고 과제를 찾으러 파일 시스템을 돌아다니며, 실제로 `gemini-3.1-pro-high`가 홈 디렉터리를 훑어 사본이 아닌 원본 fixture를 고친 사례가 있었습니다. 러너의 fixture 해시 검사가 그 실행을 실패로 잡아냈습니다. 이 동작은 1.1.24에서 처음 확인했고 1.1.25에서 다시 확인했습니다.

이 호출에는 하네스 커스터마이즈가 그대로 적용됩니다. OMP 후보가 `--append-system-prompt`로 밀어 넣는 무인 실행 규칙을 `agy`에서는 전역 규칙이 이미 담고 있고, 같은 일을 하는 명령행 옵션도 없기 때문입니다. 다만 `--dangerously-skip-permissions`는 워크스페이스 밖 접근 제한까지 함께 풀어 주므로, 이 조합은 원본을 해시로 지키는 러너 안에서만 써야 합니다.

`--dry-run`은 에이전트를 호출하거나 결과 데이터베이스를 만들지 않습니다. `--budget-usd`는 현재 명령의 지출 상한입니다. 러너는 다음 실행의 과제별 토큰 추정치가 남은 예산보다 크면 실행을 시작하지 않으며, 각 실행 후에는 세션에 기록된 실제 비용을 누적합니다. 실제 토큰 사용량은 추정치와 다를 수 있으므로 마지막으로 시작한 실행이 상한을 넘길 수 있지만, 그 뒤의 실행은 시작하지 않습니다. `agy` 후보는 요금이 아니라 Antigravity 요금제의 한도를 쓰므로 추정치와 실제 비용이 모두 0이며 예산 상한에 걸리지 않습니다. `config.json`의 기본 상한은 1달러입니다. 각 완료 행은 실행 직후 별도 트랜잭션으로 커밋되므로 이후 실행이 중단되어도 이미 끝난 결과는 남습니다.

## 루브릭 심판

`rubric` 블록이 있는 과제는 `verify`가 통과하고 보호 파일도 그대로일 때만 심판 모델이 산출물의 품질을 채점합니다. 심판은 결정적 게이트 위의 품질 순위만 매기므로, 이미 불합격이 결정된 실행에는 매길 순위가 없고 심판을 부르면 정해진 실패를 확인하는 데 돈과 두 번째 실패 사유를 더하게 됩니다. 그런 실행은 `quality_score`가 NULL, `judge_cost_total`이 0으로 남습니다. 심판은 과제 지시문, 기준 목록, 기준 산출물 원문, 후보 산출물 원문을 한 번에 받고 다음 형태로 호출됩니다.

```text
omp -p <judge-prompt> --model <judge> --mode json --no-skills --no-session --append-system-prompt <무인 실행 규칙>
```

심판의 작업 디렉터리는 심판 전용 빈 임시 디렉터리입니다. 과제 fixture도, 이 레포도, 후보의 작업 사본도 열 수 없게 하려는 것입니다. `--mode json` 출력은 줄마다 JSON 이벤트이므로, 러너는 마지막 `message_end` 이벤트의 `message.content[]` 중 `type=text` 조각을 이어 붙이고 같은 이벤트의 `message.usage.cost.total`을 `judge_cost_total`에 기록합니다. 세션 비용을 사후 집계할 필요가 없으므로 이 호출만 `--no-session`을 씁니다.

과제가 `rubric.context`를 선언하면 그 fixture 파일들의 원문이 기준 산출물 앞에 `## 입력 자료: <경로>` 절로 프롬프트에 실립니다. 심판은 빈 디렉터리에서 돌아 fixture를 열 수 없으므로, 입력 충실도를 보는 기준은 이 절 없이는 채점할 근거가 없습니다. 원문은 후보의 작업 사본이 아니라 원본 fixture에서 읽습니다. 후보가 사본을 고쳤을 수 있고, 심판이 봐야 하는 것은 과제가 실제로 준 입력이기 때문입니다.

이어 붙인 텍스트 전체가 `{"scores": [정수...], "rationale": "..."}` 한 덩어리여야 합니다. 앞뒤 공백만 무시하며, 산문이나 코드 펜스로 감싼 출력은 파싱 실패로 처리합니다. 산문에서 JSON을 파내면 출력 계약을 무시한 답을 채점에 쓰게 되고, 출력 계약을 무시하는 심판은 측정이 아닙니다.

각 기준은 0·1·2점이고 `quality_score`는 `점수 합계 / (2 × 기준 수)`이므로 0에서 1 사이입니다. 기본 합격 문턱은 0.7이며 과제의 `pass_threshold`로 바꿉니다. 에이전트가 `rubric.output`에 해당하는 파일을 쓰지 않았으면 심판을 호출하지 않고 `quality_score = 0`으로 기록합니다. 출력이 위 형태로 파싱되지 않거나 점수 개수가 기준 수와 다르거나 0~2 범위를 벗어나면 그 실행은 `quality_score`가 NULL, 불합격이 되고 `termination_reason`에 `judge_parse_error`가 붙습니다. 재시도는 하지 않습니다. 심판을 다시 부르면 같은 실행에 두 번 돈을 쓰면서 어느 판정이 맞는지는 여전히 알 수 없기 때문입니다.

심판 비용은 후보의 `cost_total`에 합치지 않고 `judge_cost_total` 열에 따로 남깁니다. 어느 심판이 채점했는지는 `judge` 열에 실행 단위로 남으며, 심판을 실제로 호출한 실행에만 채워집니다. 산출물이 없어 `quality_score = 0`으로 끝난 실행이나 게이트에서 이미 불합격한 실행은 이 열이 `''`입니다. 보고서는 이 열을 읽어 그 실행의 심판 공급자가 후보 공급자와 같을 때 `(self-judge)` 표기를 붙입니다. 자기 계열이 자기 산출물을 채점한 값은 독립 측정이 아니기 때문입니다. 심판을 바꿔 다시 돌리면 표기도 따라 바뀌고, 심판이 붙은 실행이 하나도 없는 후보는 이 값이 `null`입니다. 설정의 현재 심판으로 과거 실행을 소급 판단하지 않습니다. 기본 심판은 `config.json`의 `judge`이고 `run --judge <셀렉터>`로 덮어씁니다.

## 벤치마크 설정

`config.json`에는 다음 키가 있습니다.

- `candidates`는 후보 셀렉터 배열이며 `provider/model:thinking` 또는 `agy/<모델-id>` 형식을 씁니다. 후보 목록은 소스 코드가 아니라 이 파일 또는 반복 가능한 `run --model` 인수에서 가져옵니다.
- `variants`는 변형 이름에서 OMP 설정 dotted 키와 값으로 가는 표입니다. 예를 들어 `{"cache-long": {"providers.cacheRetention": "long"}}`입니다. 로드 시점에 dotted 키를 중첩 객체로 바꿔 보고 고정 경로 침범도 검사하므로, 잘못된 키 형태와 금지된 경로는 실행 전에 걸립니다.
- `judge`는 루브릭 심판의 모델 셀렉터입니다. `run --judge`로 덮어씁니다.
- `default_budget_usd`는 `--budget-usd`를 생략했을 때 적용하는 명령 단위 상한입니다.
- `minimum_samples_warning`은 후보의 실행 수가 이 값보다 적을 때 보고서에 저표본 경고를 붙이는 기준입니다.

다른 설정 파일은 `run --config <path>`와 `report --config <path>`로 선택할 수 있습니다.

## 과제 정의 형식

`tasks/*.json`의 각 객체에는 다음 키가 있습니다.

- `id`는 데이터베이스와 CLI 필터에 쓰는 고유 과제 식별자입니다.
- `title`은 사람이 읽는 제목입니다.
- `class`는 `classes.json`에 있는 부류 id이며 필수입니다.
- `fixture`는 `bench/`를 기준으로 하며 `fixtures/` 아래 디렉터리만 허용하는 상대 경로입니다.
- `prompt`는 에이전트에 한 번 전달하는 완전한 작업 지시입니다.
- `verify`는 셸을 거치지 않고 실행하는 채점 명령과 인수의 문자열 배열입니다. 러너가 같은 작업 사본에서 사전 검증과 사후 검증으로 두 번 실행하므로, `verify`는 작업 사본을 바꾸지 않아야 하고 두 번 돌려도 같은 판정을 내야 합니다. 파일을 고치는 채점 명령(예: `sed -i`)은 두 번째 실행의 대상을 바꿔 버립니다. 판정을 파일에 쓰지 말고 종료 코드로만 내고, 임시 산출물이 필요하면 사본 밖에 두거나 실행 끝에 지우세요.
- `timeout_seconds`는 OMP의 `--max-time`, `agy`의 `--print-timeout`, 그리고 외부 프로세스 제한에 쓰는 양의 정수입니다. 에이전트가 그 값보다 45초 더 살아 있으면 러너가 프로세스를 죽이고 그 실행을 불합격(`termination_reason`이 `external_timeout`으로 시작)으로 기록한 뒤 다음 조합으로 넘어갑니다. 배치는 중단되지 않습니다. 자식 프로세스의 stdin은 `/dev/null`입니다: `omp -p`는 stdin이 TTY가 아닌 열린 파이프이면 `readPipedInput` 단계에서 EOF를 기다리므로, 감독 프로세스(hub, cron) 아래에서 러너를 돌릴 때 이 조치가 없으면 모든 실행이 타임아웃됩니다.
- `default_repetitions`는 `--repeat`를 생략했을 때 후보마다 실행하는 횟수입니다.
- `estimated_usage`는 `input`, `output`, `cacheRead`, `cacheWrite`의 예상 토큰 수를 모두 담습니다. `--dry-run`과 실행 전 예산 차단에만 사용하며, 관측 결과로 취급하지 않습니다.
- `rubric`은 선택 항목이며 `grading`이 `rubric`인 부류의 과제에만 씁니다. `output`은 에이전트가 fixture 사본 안에 써야 하는 산출물의 상대 경로, `reference`는 `bench/` 기준 기준 산출물 경로, `criteria`는 0·1·2점으로 채점할 기준 문장 배열, `pass_threshold`는 합격 문턱(기본 0.7)입니다. `reference`는 `fixtures/` 아래에 둘 수 없습니다. fixture는 에이전트의 작업 디렉터리로 복사되므로 그 아래의 정답은 채점받는 후보가 읽을 수 있기 때문이며, 로드할 때 경로와 존재 여부를 함께 검사합니다.
- `rubric.context`는 선택 항목이며 fixture 기준 상대 경로의 배열입니다. 심판 프롬프트에 원문으로 실을 입력 자료를 지정하고, 로드할 때 각 경로가 fixture 안의 실제 파일인지 검사합니다. 절대 경로는 fixture 안을 가리켜도 거부합니다. 프롬프트가 이 파일을 과제가 준 상대 경로로 이름 붙이고, 러너는 실행 전에 fixture를 다른 위치로 복사하기 때문입니다. 입력 충실도를 보는 기준이 있는 과제에만 씁니다.
- `protected_paths`는 에이전트가 바꾸면 안 되는 fixture 기준 파일 경로 배열입니다. 테스트, 채점 스크립트, 조사 원본을 보호하는 데 사용합니다.

과제 JSON 밖에 두는 자료가 두 종류 있습니다.

- `bench/oracle/<task-id>/`에는 과제를 정의할 때 통과를 한 번 확인하는 해답 덮어쓰기 파일을 둡니다. fixture 사본 위에 이 디렉터리의 파일을 그대로 덮어쓰면 `verify`가 통과해야 하며, 그것으로 과제가 실제로 풀리는 문제임을 확인합니다. 러너는 이 디렉터리를 읽지 않으므로 채점받는 후보에게도 보이지 않습니다.
- `bench/references/<task-id>/`에는 `rubric` 부류의 기준 산출물을 둡니다. 과제의 `reference`가 가리키는 경로이며 `fixtures/` 아래에 둘 수 없으므로 이 위치가 관례입니다. 기준 산출물은 과제를 만드는 사람이 합성 입력만 보고 직접 씁니다.

현재 저장소에는 9개 부류의 합성 과제 12건이 있습니다. task ID, 부류, 검증 명령과 관찰 경계는 `bench/TAXONOMY.md`의 표를 기준으로 확인합니다. 실제 실행 범위는 `bench/tasks/*.json`에서 로드되므로 문서의 목록을 실행 입력으로 사용하지 않습니다.

## 저장 지표와 보고서 해석

`runs` 테이블은 실행마다 한 행을 추가합니다. 행에는 배치 ID, 과제 ID와 제목, 과제 부류, 후보 셀렉터와 변형 이름, 반복 인덱스, 합격 여부, 보호 파일 보존 여부, 루브릭 점수, 벽시계 경과 시간, 입력·출력·캐시 읽기·캐시 쓰기 토큰, 캐시 적중률, 최대 컨텍스트, 장문 구간 요청 수, `usage.cost.total` 합계, 카탈로그 추정 비용, 심판 비용, 요청 수와 그중 서브에이전트 요청 수, 도구 호출 수, 실제 모델, 실제 사고 강도, 폴백 여부, 에이전트와 검증 종료 코드, 종료 사유, 생성 시각, 세션 파일 경로, 그리고 `agy` 후보가 쓴 한도 버킷과 그 소진 비율이 들어갑니다.

에이전트 프로세스의 종료 코드는 `agent_exit_code` 열에 들어갑니다. OMP만 러너를 쓰던 시절에는 이 열의 이름이 `omp_exit_code`였으며, `bench.py`는 기존 데이터베이스를 열 때 열 이름을 한 번 바꾸고 그 뒤에 생긴 열을 추가합니다. 마이그레이션은 `run`뿐 아니라 `score`와 `report`에서도 돌기 때문에, 예전 러너가 기록한 데이터베이스를 그대로 읽을 수 있습니다. 이때 개념 자체가 없던 값은 `''`이고 측정하지 않은 값은 NULL로 남습니다. 부류별 표는 예전 행의 빈 `task_class`를 과제 정의의 `class`로 채워 읽으므로, 부류가 생기기 전에 기록한 실행도 자기 부류의 표에 그대로 나타납니다. 과제 정의에서 사라진 `task_id`의 행은 기록된 `task_class` 값을 그대로 쓰고, 그 값이 `classes.json`에 없으면 부류별 표와 하네스 점수에서 빠지며 `Rows with no defined class: N`으로만 보고됩니다. 가중치 0인 가짜 부류를 만들어 조용히 섞지 않습니다.

세션 디렉터리 아래의 모든 JSONL을 읽으므로 서브에이전트가 생기면 그 사용량과 도구 호출도 실행 비용에 포함됩니다. 요청 수는 사용량을 가진 assistant 메시지 수이며, 그중 서브에이전트 세션 파일에서 나온 것은 `subagent_request_count`에 따로 셉니다. 도구 호출 수는 `customType=tool_execution_start` 엔트리 수입니다. 실제 주 모델과 사고 강도는 최상위 세션에서 읽습니다. 후보와 실제 값이 다르거나 `resolvedModelIsFallback`이 참이면 보고서의 모델 라우팅 불일치 목록에 드러납니다.

캐시와 컨텍스트 지표는 요청 단위로 계산합니다. `cache_hit_ratio`는 `cacheRead / (input + cacheRead + cacheWrite)`이며 분모가 0이면 NULL입니다. `max_context_tokens`는 요청별 `input + cacheRead + cacheWrite`의 최대값입니다. `long_context_requests`는 그 값이 실제 모델의 카탈로그 `cost.longContext.inputThreshold`(openai 계열 272,000)를 넘은 요청 수이고, 카탈로그에 장문 구간이 없는 모델은 0입니다. `catalog_cost_total`도 같은 판정을 써서 장문 구간을 넘은 요청에만 `longContext` 단가를 적용합니다. `agy` 후보는 요청별 사용량을 주지 않고 실행 전체 합계만 주므로 `max_context_tokens`가 NULL입니다.

`agy` 후보는 `quota_fraction_used`에 주간 한도의 소진 비율을 남기고 `cost_total`은 0으로 남깁니다. 실제로 돈이 나가지 않기 때문이며, 그래서 `report`의 Pareto 전선은 `agy` 후보를 유료 후보와 같은 축에서 비교하지 못합니다. 보고서는 그런 행이 있으면 그 사실을 아래에 적으며, `agy` 후보끼리는 `Quota/task` 열로 비교해야 합니다.

`Catalog est/task`는 관측 토큰에 `~/.omp/agent/models.db`의 실제 모델 기본 단가를 적용한 작업당 비용입니다. `Actual/task`는 세션의 `usage.cost.total`을 합산한 작업당 비용입니다. 장문 컨텍스트 별도 구간과 공급자별 정산 방식 때문에 두 값이 다를 수 있습니다. 두 비용 모두 구독 계정의 현금 청구액이 아니라 카탈로그 단가로 환산한 명목 비용일 수 있습니다.

합격률 신뢰구간은 95% Wilson 구간입니다. `Cost/pass`는 후보의 전체 실제 비용을 합격 실행 수로 나눈 값이며, 합격이 없으면 `n/a`로 표시합니다. Pareto 판정은 관측 합격률과 실제 작업당 비용만 사용합니다. 다른 후보보다 합격률이 높지 않고 비용도 낮지 않으면서 적어도 한 축에서 열세이면 지배당한 후보로 분류합니다. 평균 시간은 별도로 표시하지만 Pareto 축에는 넣지 않습니다.

`report`는 네 부분을 냅니다. 첫째는 위의 후보 전체 표(Pareto)입니다. 둘째는 부류 × 후보 표이며 실행 수, 합격률과 Wilson 구간, `pass^k`, 평균 quality, 실제 작업당 비용, 평균 초, 캐시 적중률 평균, 장문 요청 수 합을 담습니다. `pass^k`는 반복이 2회 이상인 과제 중 모든 시도가 합격한 과제의 비율입니다. 한 번만 돌린 과제로는 운과 신뢰성을 구분할 수 없으므로 그런 과제는 세지 않고, 대상이 없으면 `n/a`입니다. 셋째는 하네스 점수이며 후보마다 Σ(부류 weight × 그 부류 합격률)이고 데이터가 없는 부류는 0으로 계산한 뒤 어느 부류가 0으로 들어갔는지 함께 적습니다. 넷째는 라우팅 권고입니다.

라우팅 권고는 부류마다 "관측 합격률이 최대인 후보들 중 실제 작업당 비용이 가장 낮은 후보"를 고르고, `classes.json`의 `harness_roles`와 `agent_overrides`로 펼쳐 `modelRoles`와 `task.agentModelOverrides` JSON을 만듭니다. 같은 역할을 두 부류가 서로 다른 후보로 권고하면 weight가 큰 부류가 그 역할을 가져가고 충돌 목록에 함께 적습니다. 권고의 표본이 `minimum_samples_warning` 미만이면 `(low-sample)` 표기가 붙습니다. 권고 후보에 변형이 있으면 역할 값에는 셀렉터만 들어가고 변형 이름은 따로 적습니다. 변형은 모델 셀렉터가 아니라 설정 오버레이여서 역할 값에 넣을 수 없기 때문입니다.

`agy` 후보는 역할 값에 들어가지 않습니다. OMP는 `agy/` 셀렉터를 해석하지 못하고, 그 후보의 실제 비용은 구조적으로 0이므로 비용 동률을 항상 이깁니다. 어느 부류의 권고가 `agy` 후보면 같은 규칙을 그 부류의 OMP 후보에만 다시 적용해 역할 값을 채우고, 그 역할 키를 `unroutable`에 권고 후보와 대체 후보(`omp_fallback`)와 함께 적습니다. 그 부류에 OMP 후보가 하나도 없으면 역할을 비워 두고 `unroutable`에만 적습니다. 어느 경우에도 `agy` 권고가 그 역할 키의 소유자로 남으므로, weight가 낮은 부류가 대신 채워 넣지 못하고 서로 다른 후보를 권고했다면 충돌 목록에 나옵니다.

부류의 `harness_roles` 중 `default`가 아닌 역할과 `agent_overrides` 키는 그 부류의 실행 행에 `subagent_request_count > 0`인 행이 하나라도 있을 때만 권고에 들어갑니다. 러너가 띄우는 에이전트 자신은 `modelRoles.default`만 쓰므로, 서브에이전트를 띄운 실행이 없는 부류는 나머지 키에 대해 아무것도 측정하지 않은 것입니다. 그 키는 권고에서 빠져 `unobserved`에 `{key, class}`로 실리고 소유자도 정해지지 않으므로, 관측이 있는 더 가벼운 부류가 대신 채울 수 있습니다. 실행이 하나도 없는 부류도 같은 방식으로 자기 키를 `unobserved`에 싣습니다. "실행 없음"은 "관측 없음"의 가장 강한 형태이므로, 데이터가 없다는 사실이 목록에서 조용히 사라지지 않게 합니다.

`report --format json`의 최상위 키는 `candidates`, `classes`, `harness_score`, `routing`이고 `routing`은 `modelRoles`, `agentModelOverrides`, `conflicts`, `low_sample`, `variants`, `unroutable`, `unobserved`, `evidence`를 담습니다. `evidence`는 권고된 키마다 근거 부류와 권고 후보, 그리고 실제로 쓰이는 셀렉터·표본 수·자기채점 여부·변형 이름·저표본 여부를 담으며 `routing` 서브커맨드가 표와 `changes`를 그리는 데 씁니다. 표본 수와 자기채점, 저표본 여부는 `agy` 권고가 대체된 경우 대체 후보(실제로 적용되는 후보)의 값입니다. 원래 `agy` 승자는 `unroutable`에만 남습니다. 후보 레코드에는 전체 표와 부류별 표 모두 `self_judge`가 `true`·`false`·`null`로 들어갑니다.

현재 과제는 12건뿐이고 기본 반복 횟수도 작으므로 신뢰구간이 넓습니다. 저표본 상태의 Pareto 전선은 후보의 확정 순위가 아니라 추가 반복 대상을 고르는 탐색 결과로만 해석해야 합니다. 합성 과제는 실제 저장소의 규모, 장시간 조사, 외부 서비스 상태를 모두 대표하지 않습니다. 캐시 상태, 공급자 부하, 폴백, 하네스와 CLI 버전도 반복 간 변동 요인입니다.

루브릭 채점에는 추가 변동 요인이 있습니다. 심판 모델의 판정은 결정적이지 않고, 심판을 바꾸면 같은 산출물의 `quality_score`가 달라지며, 심판과 후보의 공급자가 같은 행은 독립 측정이 아닙니다. 그래서 부류별 표의 quality 열은 후보 간 순위를 정하는 값이 아니라 같은 심판 아래에서의 상대 비교로만 읽어야 합니다.

러너의 판정 규칙에는 회귀 테스트가 있습니다. `python3 -m unittest discover -s bench/tests`로 돌리며 모델을 호출하지 않고 과제 fixture도 읽지 않습니다(입력이 필요한 경우는 임시 디렉터리에 만듭니다). 오버레이 변환과 고정 경로 침범 거부, 후보 문자열 문법, 루브릭 산술과 문턱 경계, `rubric.context` 경로 검사와 `grade_rubric`이 심판에게 넘기는 입력(원본 fixture의 원문이 기준 산출물 앞에 실리고 작업 사본의 내용은 실리지 않음), 심판 스트림 파싱과 엄격한 JSON 판정(실패 경로 포함), 장문 구간 카탈로그 비용, 라우팅 충돌 규칙과 `agy` 대체, 서브에이전트 관측 조건, apply.sh 부분 갱신과 별칭 유지, `--check` 종료 코드 판정, 그리고 `--write`가 CRLF가 섞인 사본에서도 두 줄 외의 바이트를 바꾸지 않는다는 성질을 덮습니다.

## 라우팅 제안

`routing` 서브커맨드는 `report`의 라우팅 권고를 `omp/config.apply.sh`의 관리 값으로 옮기는 경로입니다. 집계는 `report`와 같고(같은 DB, 같은 `classes.json`, 같은 계산 함수), 출력은 apply.sh의 `modelRoles`·`task.agentModelOverrides` 두 줄에 대한 제안입니다.

```bash
python3 bench/bench.py routing
python3 bench/bench.py routing --format json
python3 bench/bench.py routing --apply-script omp/config.apply.sh --write
```

표에는 키, apply.sh의 현재 값, 제안 값, 근거 부류, 그 부류에서 실제로 쓰인 후보의 표본 수, 그리고 `(low-sample)`·`(self-judge)`·`conflict`·`unroutable`·`variant:<이름>` 표기가 들어갑니다. 이어서 그 두 줄만 바뀌는 unified diff를 냅니다. 권고가 없는 키는 현재 값을 그대로 두는 부분 갱신이므로, 측정하지 않은 역할이 빈 값이 되거나 다른 부류의 값으로 덮이지 않습니다. 위의 서브에이전트 관측 조건이 그대로 적용되어 관측이 없는 키는 제안에서 빠지고 `unobserved`로 보고됩니다.

`task.agentModelOverrides` 값에는 권고 셀렉터를 그대로 씁니다. 예외는 apply.sh의 현재 값이 역할 별칭(`@mid`·`@smol`·`@slow`)이고 그 권고가 제안된 `modelRoles`의 같은 역할 값과 같은 경우이며, 이때는 별칭을 유지합니다. 같은 값을 셀렉터로 다시 적으면 지금은 결과가 같지만 그 역할을 다음에 바꿀 때 오버라이드가 따라오지 않게 됩니다.

권고 후보에 변형이 붙어 있으면 셀렉터만 쓰고 `changes[].flags`에 `variant:<이름>`을 넣으며, 그 변형의 오버레이 키를 한 줄로 보여 줍니다. 권고 값이 apply.sh의 현재 값과 같더라도 이 항목은 `changes`에 남습니다. 값은 같지만 그 값을 뒷받침한 측정이 다르고, 오버레이는 사람이 따로 적용하거나 버려야 하는 부분이기 때문입니다. 변형은 모델 셀렉터가 아니라 설정 오버레이라서 apply.sh의 역할 값으로 적용할 수 없습니다.

`--write`는 그 두 줄만 고쳐 쓰고 나머지 바이트를 그대로 보존합니다. 파일은 바이트로 읽고 바이트로 쓰므로 줄 끝 형식과 관리 두 줄 밖의 내용이 그대로 남습니다. 기록 뒤에는 apply.sh의 `--check` 모드(설정을 바꾸지 않고 다른 값만 보고하는 모드)를 실행해 결과를 보고합니다. 이 모드의 종료 코드 0(모두 일치)과 1(일부 차이)은 둘 다 보고이므로 `routing` 자체는 0으로 끝납니다. 그 밖의 종료 코드는 스크립트가 검사를 못 한 것이므로(`omp`가 PATH에 없는 경우 등) 오류로 끝냅니다. 검사할 수 없는 제안은 사람이 적용을 판단할 근거가 없기 때문입니다. 이때도 파일은 이미 기록되었으므로 `write`와 `check`가 담긴 문서를 먼저 stdout에 낸 다음 실패로 끝냅니다. 이 명령은 `omp config set`을 부르지 않습니다.

절차는 다음과 같습니다.

1. `python3 bench/bench.py routing`으로 제안과 근거를 읽습니다.
2. 받아들일 만하면 `--write`로 apply.sh를 고치고 `git diff omp/config.apply.sh`로 사람이 검토합니다.
3. 검토를 통과했을 때에만 사람이 직접 `bash omp/config.apply.sh`를 실행해 설정에 적용하고, 그 변경을 커밋합니다.

`--format json`의 키는 `proposal`, `current`, `changes`, `unobserved`, `unroutable`, `conflicts`, `low_sample`이고 `changes`의 항목은 `{key, from, to, class, samples, flags}`에 변형이 붙은 경우 `variant_overlay`가 더해집니다. `--write`를 함께 주면 `write`(`{path, changed_lines}`)와 `check`(`{exit, output}`)가 같은 문서에 더해집니다. 검사가 실패해 종료 코드가 0이 아닌 경우에도 이 문서는 stdout에 그대로 나옵니다. JSON 모드의 stdout은 언제나 문서 하나뿐이고 `wrote <경로>`와 오류 메시지 같은 사람용 줄은 stderr로 갑니다.
