# 벤치마크 과제 부류와 가중치

이 문서는 `bench/classes.json`의 부류 ID와 가중치를 사람이 검토할 수 있게 설명한다. 과제와 fixture는 모두 합성이며, 공개본의 가중치는 모델 비교를 위한 **개인 설정값**으로 제공한다. 원본 업무 자료와 집계는 공개하지 않으며, 이 가중치를 특정 조직이나 일반적인 개발 조직의 업무 분포에 대한 통계적 추정치로 해석하지 않는다.

## 설계 원칙

부류는 결과를 서로 다른 관찰 경계에서 채점해야 할 때 나눈다.

- 기능과 버그 수정은 변경 전후 행동으로 판정한다.
- 리팩터는 새 계약과 옛 공개 이름 제거를 함께 판정한다.
- 테스트 작성은 실제 테스트 통과뿐 아니라 알려진 변이를 잡는지 판정한다.
- 문서와 조사는 저장소 안의 합성 출처에 대한 충실도를 판정한다.
- 리뷰는 심어 둔 결함의 재현율과 정밀도를 판정한다.
- 정성 품질이 필요한 문서 초안은 결정적 형식 게이트 위에 루브릭을 둔다.

회의 참석, 인사, 결재처럼 에이전트가 대신 수행할 수 없거나 외부 계정 상태에 의존하는 활동은 과제로 만들지 않는다. 클라우드 배포 같은 인프라 작업도 공개 벤치에서 재현 가능한 로컬 프로세스 범위로 제한한다.

## 부류와 휴리스틱 가중치

| class | weight | grading | 선택 이유 |
| --- | ---: | --- | --- |
| `dev-feature` | 0.230 | verify | 여러 파일과 호출부에 걸친 새 행동을 가장 강하게 반영 |
| `docs-technical` | 0.218 | verify | 코드와 CLI에서 사실을 찾아 정확한 사용 문서로 옮기는 능력 반영 |
| `dev-infra-ops` | 0.162 | verify | 설정, 프로세스 수명주기, 헬스 체크를 종단에서 확인 |
| `docs-business` | 0.084 | rubric | 합성 입력을 사람이 읽는 업무 초안으로 변환하는 제한된 정성 과제 |
| `dev-refactor` | 0.079 | verify | 행동 보존과 공개 계약의 완전한 이전을 확인 |
| `dev-test-ci` | 0.062 | verify | 경계와 변이를 실제로 검출하는 테스트 설계 확인 |
| `dev-fix` | 0.057 | verify | 좁은 재현에서 원인을 고치는 능력 확인 |
| `research` | 0.054 | verify | 여러 로컬 출처를 연결해 정확한 답을 추출하는 능력 확인 |
| `dev-review` | 0.054 | verify | 결함을 찾되 과잉 지적하지 않는 능력 확인 |
| 합 | 1.000 |  |  |

이 값은 모델 점수를 하나로 접기 위한 초기 우선순위일 뿐이다. 공개 결과를 해석할 때는 가중 합계와 함께 부류별 합격률, 표본 수, 신뢰구간을 본다. 사용 목적이 다르면 `classes.json`의 가중치를 복사해 별도 설정에서 바꾸고 그 근거를 기록한다.

가중치와 과제 수는 같지 않다. 판정 경계가 중요한 부류에는 작은 가중치여도 두 과제가 있을 수 있고, 루브릭 비용이 드는 부류는 대표 과제 하나만 둘 수 있다.

## 부류별 과제 계약

### `dev-feature`

- 입력: 동작하는 합성 코드베이스, 이슈형 요구사항, 수용 기준, 새 행동을 관찰하는 테스트
- 산출물: 새 행동과 모든 필요한 호출부 변경
- 채점: 변경 전 실패하는 새 계약이 변경 후 통과하고 기존 행동도 유지되는지 확인
- 현재 과제: TypeScript HTTP 조회 기능, Go CLI 출력 기능

### `docs-technical`

- 입력: 합성 소스와 현재 문서 또는 문서가 없는 저장소
- 산출물: 지정된 Markdown 문서
- 채점: 공개 이름, 시그니처, 옵션, 기본값, 종료 코드처럼 소스나 실제 `--help`에서 관찰되는 사실을 결정적으로 비교
- 현재 과제: TypeScript API 레퍼런스, Shell CLI README 동기화

### `dev-infra-ops`

- 입력: 로컬 서비스, 시작 스크립트, 설정 파일, 헬스와 재시작 요구사항
- 산출물: 고친 설정과 스크립트
- 채점: 지정 포트 접속, 헬스 응답, 제한된 재시작, 로그와 pid 갱신, 프로세스 정리를 실제로 실행
- 외부 클라우드 계정과 컨테이너 데몬은 사용하지 않음

### `docs-business`

이 ID는 기존 벤치 계약과의 호환을 위해 유지한다. 현재 과제는 실제 사업 문서가 아니라 합성 커밋, 합성 일정, 합성 열린 항목을 일일 업무 초안으로 정리하는 문서 변환이다.

- 입력: `commits.log`, `schedule.txt`, `open-items.txt`, `template.md`의 합성 자료
- 산출물: Markdown 초안과 HTML 목록
- 채점: 구조와 이스케이프는 결정적 검증기로 검사하고, 토픽 그루핑·항목 문장 형식·계획 순서·입력 충실도는 0/1/2 루브릭으로 비교
- 기준 산출물은 fixture 밖 `bench/references/<task-id>/`에 두어 후보가 읽지 못하게 함

### `dev-refactor`

- 입력: 행동 보존 제약, 새 공개 계약, 제거할 옛 이름, 기존 테스트
- 산출물: 새 계약으로 이전한 구현과 호출부
- 채점: 새 계약 통과와 옛 이름·재수출 별칭·호환 shim 부재를 함께 확인
- 현재 과제: 세 Python 모듈에 걸친 가격 계산 API 이전

### `dev-test-ci`

- 입력: 테스트가 없는 합성 모듈과 보장할 행동
- 산출물: 테스트 파일
- 채점: 원본 구현에서 통과하고 사전 정의한 각 오류 변이에서 하나 이상의 테스트가 실패하는지 확인
- 테스트 수가 아니라 반올림, 통화 자릿수, 환율 방향, 부호, 알 수 없는 입력 같은 독립 행동 경계를 평가

### `dev-fix`

- 입력: 실패 재현과 기대 행동
- 산출물: 원인을 고치는 최소 변경
- 채점: 변경 전 실패, 변경 후 통과, 기존 테스트 유지
- 현재 과제: Python 구간 경계, TypeScript 재시도 취소 경계

### `research`

- 입력: 저장소 안에 고정된 합성 레코드와 질문
- 산출물: 엄격한 키=값 형식의 짧은 답
- 채점: 여러 출처를 연결해 얻은 값과 파생값을 전체 문자열로 비교
- 웹과 개인 계정은 사용하지 않음

### `dev-review`

- 입력: 합성 diff와 저장소 규약
- 산출물: 기계 판독 가능한 지적 목록
- 채점: 심어 둔 결함에 대한 재현율과 정밀도를 함께 계산하고 줄 번호에는 작은 허용 범위를 둠
- 모든 줄을 지적하는 전략이 유리하지 않도록 정밀도 하한을 적용

## 과제와 검증기

현재 과제 정의는 `bench/tasks/*.json`, 합성 작업 사본은 `bench/fixtures/`, 제작 시 통과를 확인하는 해답은 `bench/oracle/`, 루브릭 기준 산출물은 `bench/references/`에 있다.

공통 규칙:

- `verify`는 셸을 거치지 않는 명령 배열이며 동일 사본에서 반복 실행해도 같은 결과를 내야 한다.
- 독립 Python 검증기는 `python3 -I verify.py`로 실행해 사용자 환경의 모듈 간섭을 줄인다.
- `protected_paths`는 glob이 아니라 개별 파일 경로이며 테스트, 검증기, 합성 원본을 보호한다.
- 루브릭 기준 산출물은 `fixtures/` 밖에 둔다. fixture 안에 두면 후보가 정답을 읽을 수 있다.
- 외부 네트워크, 실제 회사 시스템, 개인 계정 상태가 없어도 채점이 끝나야 한다.
- timeout은 과제 정의의 실제 `timeout_seconds`를 따른다.

구현된 task ID:

| task id | class | verify | 핵심 관찰 |
| --- | --- | --- | --- |
| `feature-ts-endpoint` | `dev-feature` | `bun test` | 필터·페이지네이션·정렬·잘못된 쿼리 |
| `feature-go-cli` | `dev-feature` | `go test ./...` | text·json·csv CLI 출력 |
| `docs-api-reference` | `docs-technical` | `python3 -I verify.py` | 소스 선언과 문서 일치 |
| `docs-cli-sync` | `docs-technical` | `bash verify.sh` | 실제 도움말과 README 일치 |
| `infra-service-health` | `dev-infra-ops` | `bash verify.sh` | 기동·헬스·재시작·정리 |
| `report-draft-ko` | `docs-business` | `python3 -I verify.py` + rubric | 합성 근거에 충실한 업무 초안 |
| `multifile-refactor` | `dev-refactor` | `python3 -m unittest` | 새 계약과 옛 이름 제거 |
| `testci-mutation-guard` | `dev-test-ci` | `python3 -I verify.py` | 원본 통과와 변이 검출 |
| `bugfix-python` | `dev-fix` | `python3 -m unittest` | 포함 구간 경계 |
| `bugfix-ts-cancel` | `dev-fix` | `bun test` | 재시도 중 취소 경계 |
| `search-and-answer` | `research` | `python3 -I verify.py` | 로컬 출처 연결과 파생값 |
| `review-planted-defects` | `dev-review` | `python3 -I verify.py` | 재현율과 정밀도 |

## 라우팅 해석

`classes.json`의 `harness_roles`와 `agent_overrides`는 각 부류가 닿을 수 있는 OMP 역할을 나타낸다.

| class | 역할 |
| --- | --- |
| `dev-feature` | `default`, `mid`; `task` |
| `docs-technical` | `default`, `smol`; `scout` |
| `dev-infra-ops` | `default` |
| `docs-business` | `default` |
| `dev-refactor` | `default`, `mid`; `task` |
| `dev-test-ci` | `default`, `mid`; `task` |
| `dev-fix` | `default` |
| `research` | `default`, `smol`; `scout` |
| `dev-review` | `default`, `slow`; `reviewer` |

과제 프롬프트는 서브에이전트 사용을 강제하지 않는다. 따라서 `mid`, `smol`, `slow`와 대응 override는 실행 기록에서 `subagent_request_count > 0`이 관찰된 부류에만 라우팅 근거가 된다. 관찰되지 않은 역할은 성능이 낮은 것이 아니라 측정되지 않은 것이다.

여러 부류가 같은 역할에 다른 후보를 권고하면 휴리스틱 weight가 큰 부류가 우선하되 충돌을 보고서에 남긴다. 표본이 적거나 신뢰구간이 넓으면 자동 결론 대신 추가 반복 대상으로 취급한다.

## 변형 해석

설정 변형은 같은 모델 셀렉터에 다른 하네스 설정을 적용하는 비교 축이다. `modelRoles`, `task.agentModelOverrides`, `retry.fallbackChains`는 변형이 바꿀 수 없다. 이 경로가 움직이면 한 후보 실행에 여러 모델이 섞여 비교 의미가 사라지기 때문이다.

캐시 보존, 장문 컨텍스트, 공급자 정산 차이는 품질과 비용을 서로 다른 방식으로 바꿀 수 있다. `docs/PRICING.md`의 현재 카탈로그 의미와 실제 실행의 요청별 사용량을 함께 보고, 짧은 합성 과제에서 발동하지 않은 변형을 성능 차이로 해석하지 않는다.

## 한계

- 12개 합성 과제와 9개 부류는 절대적인 모델 순위를 만들기에 작다.
- 가중치는 개인 휴리스틱이라 다른 사용자의 실제 작업 비중을 대표하지 않는다.
- fixture와 검증기가 공개되어 있으므로 공개 벤치에 대한 특화 가능성을 없앨 수 없다.
- 루브릭 심판은 비결정적이며 후보와 같은 공급자일 때 독립 평가가 아니다.
- 서브에이전트 역할은 실제 호출이 관찰된 실행에서만 평가할 수 있다.
- 결과는 모델 단독 순위가 아니라 해당 하네스 설정과 모델 셀렉터 조합의 관찰값이다.

따라서 보고서는 Pareto 전선, 부류별 결과, 표본 수, 신뢰구간, 라우팅 불일치와 함께 읽고 다음 실험을 고르는 자료로 사용한다.
