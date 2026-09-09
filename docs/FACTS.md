# 하네스 통합 레포의 확인된 사실

이 문서는 공개 가능한 기술 관측과 그 한계를 기록합니다. 현재 유지하는 환경은 Linux/WSL2, OMP 18.1.13/18.1.14, Bun 1.3.14입니다. 날짜가 있는 관측은 다른 버전이나 호스트의 성능 보장이 아닙니다.

## 1. 도구 가용성

- 설치기와 런타임 패치는 `@oh-my-pi/pi-coding-agent` 18.1.13 또는 18.1.14를 요구합니다. 다른 버전이나 예상과 다른 source layout은 거부합니다.
- Bun 1.3.14가 설치기, TypeScript extension, `omp-profile`, `harness-run`, cost audit, host-sync의 기준 환경입니다.
- Python 3 표준 라이브러리의 `sqlite3`와 `json`은 benchmark와 collector에 사용됩니다. `sqlite3`나 `jq` CLI가 모든 Herdr/cron 환경에 있다고 가정하지 않습니다.
- 네이티브 Windows와 macOS는 설치 대상으로 확인하지 않았습니다. WSL에서 Windows Chrome을 연결하는 기능은 전체 Windows 설치 지원과 별개입니다.

## 2. OMP 비대화형 실행

OMP 18.1.13의 비대화형 실행에서 사용하는 공개 계약은 다음과 같습니다.

- `omp -p "<프롬프트>"`는 프롬프트를 처리하고 종료합니다.
- `--config <파일>`은 현재 실행의 config overlay이며 반복 지정할 수 있습니다. 공유 설정을 적용하는 명령이 아닙니다.
- `--profile <이름>`은 인증, 세션, 설정, 캐시를 분리하는 OMP 실행 프로필입니다. Harness의 용도별 `/profile`과 다른 개념입니다.
- `--session-dir`, `--model`, `--thinking`, `--mode json`, `--max-time`, `--auto-approve`, `--no-skills`, `--skills <glob>`은 runner가 목적에 맞게 명시합니다.
- `--mode json`의 완성 응답과 usage는 `message_end`의 `message`에 있습니다. 이벤트가 한 줄 JSON이라는 사실만으로 성공을 판단하지 않고 종료 상태와 최종 message를 함께 확인합니다.

Benchmark는 session usage를 사후 집계하므로 후보 실행에 session을 유지합니다. 별도의 rubric judge처럼 구조화 출력에서 usage를 직접 읽는 경계만 session 없이 실행할 수 있습니다.

## 3. 로컬 데이터 원천과 개인정보 경계

### 3-1. `~/.omp/stats.db`

`omp stats --summary`가 session 기록을 증분 적재합니다. `messages`에는 model/provider, timestamp, latency, token classes, catalog-derived cost와 agent type이 있고, `tool_calls`에는 tool name과 입출력 크기가 있습니다.

이 데이터베이스는 프롬프트 본문을 직접 싣지 않더라도 작업 폴더, 모델 사용 패턴, 시간대, 비용을 통해 개인 활동을 드러낼 수 있습니다. 원본 row나 folder별 집계를 공개 문서·fixture로 복사하지 않습니다.

### 3-2. 세션 JSONL

세션에는 대화, 도구 인자와 결과, model 변경, credential pin, compaction 상태, usage가 저장됩니다. Subagent 기록과 큰 tool output은 sidecar 파일로 나뉠 수 있습니다. Benchmark runner는 session metadata로 main/subagent usage를 구분하지만 원문은 공개 산출물이 아닙니다.

### 3-3. `~/.omp/agent/models.db`

`model_cache`에는 provider별 model ID, catalog cost, context window, max output, thinking mode와 effort, 장문 구간이 저장됩니다. 카탈로그는 OMP 시점의 metadata이며 공급자 공식 가격이나 실제 청구서와 다를 수 있습니다. [PRICING](PRICING.md)은 이 차이와 공식 문서를 함께 기록합니다.

### 3-4. `~/.omp/agent/agent.db`

`model_perf`는 local latency와 generation throughput 표본, `usage_history`는 subscription quota 상태, `command_usage`는 command/skill 사용 횟수를 담습니다. 계정 식별값과 raw row는 공개하지 않습니다. 속도와 quota는 host, provider load, account plan에 따라 바뀌므로 routing 품질의 독립 증거가 아닙니다.

## 4. 개인 비용 관측에서 남길 수 있는 결론

2026-09 초의 개인 OMP 사용 창을 project와 volume을 식별할 수 없게 집계했을 때 다음 패턴을 확인했습니다.

- OMP가 기록한 비용은 OAuth subscription 사용의 현금 청구액이 아니라 catalog 단가로 환산한 **명목 비용**입니다.
- 명목 비용 구성은 cache read 약 71%, cache write 약 14%, output 약 13%, uncached input 약 2%였습니다.
- token 기준 cache hit 비율은 약 98%였지만, 큰 cache rewrite가 함께 존재했습니다. 높은 hit rate 하나만으로 cache 정책이 최적이라고 결론 내릴 수 없습니다.
- 요청 context는 중위 약 158K, p90 약 466K, 최대 약 622K였습니다. 평균값만 보면 장문 임계와 compaction 압력을 놓칩니다.
- main과 subagent의 명목 비용 비중은 대략 68:32였습니다. 위임 횟수보다 각 subagent가 반복한 context와 model 선택이 비용을 크게 좌우했습니다.
- 동일한 조사 유형에서 큰 model subagent 한 번과 작은 model subagent 한 번 사이에 수백 배의 명목 비용 차이가 관측되었습니다. 이 결과는 품질 동등성 증거가 아니므로 낮은 가격만으로 routing을 바꾸지 않습니다.
- 5분 유휴 cache와 1시간 cache를 비교할 때, 긴 TTL은 더 비싼 cache write를 유휴 복귀의 재사용으로 회수해야 합니다. 짧은 session에서는 `long`이 자동으로 유리하지 않았으므로 기본값은 provider-aware `auto`를 유지합니다.

이 수치는 개인 harness 튜닝의 방향만 설명합니다. 실제 project 이름, 요청 총량, 실제 보고·업무 records, folder별 집계는 공개 근거가 아닙니다.

## 5. 모델 라우팅과 상태 경계

현재 용도별 선택의 정본은 `omp/profiles.json`이며 `omp-profile list`와 `omp-profile show <이름>`으로 확인합니다. 문서에 과거 host의 전체 `modelRoles` snapshot을 복사하지 않습니다.

확인된 상태 경계는 다음과 같습니다.

- 역할 selector의 effort suffix는 agent frontmatter의 `thinking-level`보다 우선합니다.
- `task.agentModelOverrides`의 role alias는 OMP의 model role로 해석됩니다.
- `modelRoles.default`는 session이 현재 model을 바꿀 때 갱신할 수 있으므로 declarative drift 비교에서 예외로 둡니다.
- 같은 provider의 OAuth account pinning이 먼저 작동하고, provider/model fallback은 그 다음 경계입니다. `/account`는 엄격한 billing lock이 아닙니다.
- `/effort high`는 현재 session과 현재 model의 override입니다. `--profile`을 명시한 effort 명령과 `omp-profile effort set`만 공유 profile state를 수정합니다.
- Candidate profile을 config에 적는 일은 benchmark 실행이나 최적성의 증거가 아닙니다. 실제 task, repetitions, failures, cost semantics를 함께 봅니다.

### 계정 선택의 실제 요청 검증 (2026-09-07)

OMP 18.1.13에서 `/fresh`, 컨텍스트 초기화, 명시적 provider session ID는 대화 기록 ID와 실제 요청 ID를 분리할 수 있습니다. 기존 확장은 기록 ID에만 계정을 고정해 이 조건에서 선택 표시와 실제 요청 계정이 달라졌습니다. 런타임 호환 패치가 실제 `AgentSession.sessionId`를 확장에 전달하며 `/account`는 그 ID로 pin·해제·공용 동기화를 수행합니다.

`bun test omp/extensions/accounts/accounts.runtime.test.ts`는 compiled CLI를 별도 RPC 프로세스로 실행하고, 합성 OAuth와 loopback Codex Responses 서버에서 실제 `Authorization`을 관측합니다. 일반 동일-ID 경로는 수정 전에도 통과했고, 분리된 ID의 연속 요청·재개와 공용 선택의 기존/새 세션·도구 continuation 경로는 계정 2 대신 1을 보내 실패했습니다. 패치한 CLI 복사본과 수정 확장으로 같은 시나리오가 통과했습니다. 변경 후 sibling 격리와 기존 local 선택보다 공용 선택이 우선하는 경로도 검사합니다. 이는 실제 CLI 요청 경로의 증거이며, 실제 OAuth 계정이나 유료 서버의 인증·한도 복구를 실행한 결과는 아닙니다.

설치 런타임에 패치를 적용한 뒤 두 배포 트리에서 `bun test omp/extensions omp/native-runtime.test.ts herdr/scripts/harness-run.test.ts`가 각각 **47 passed, 139 assertions**로 통과했습니다. `bun omp/native-runtime.ts --check`, 변경한 TypeScript 파일의 `biome check`, `bash -n install.sh`도 통과했습니다. 실제 CLI 회귀 3개는 합계 16개 HTTP 요청을 관측하며, 별도 시작 실패·ready timeout 주입에서 생성한 자식 프로세스가 모두 종료된 것도 확인했습니다.

## 6. 벤치마크 해석

이 레포의 benchmark는 작은 개인 decision tool입니다. 결과를 보편적인 model leaderboard로 해석하지 않습니다.

- model 비교에서는 harness, task, timeout, tools, skills, context policy, effort를 고정합니다.
- harness 비교에서는 model과 task를 고정합니다. 둘을 동시에 바꾼 결과에 model 단독 원인을 붙이지 않습니다.
- 합격률은 반복과 산포를 함께 보고, best run만 대표값으로 고르지 않습니다.
- `Catalog est/task`, session-recorded `Actual/task`, subscription quota는 서로 다른 값입니다. 현금 청구액처럼 섞지 않습니다.
- Public fixtures와 examples는 처음부터 synthetic이어야 합니다. Private work나 report를 이름만 바꿔 public corpus로 만들지 않습니다.
- Oracle, protected path, clean-fixture preflight는 grading leakage와 broken task를 막지만 model contamination 전체를 보장하지 않습니다.

외부 benchmark 방법론은 [BENCH-SURVEY](BENCH-SURVEY.md), 가격과 cache/long-context caveat는 [PRICING](PRICING.md), runner contract는 [bench README](../bench/README.md)에 있습니다.

## 7. 공개 하네스 자산과 통합 관측

- `skills/`는 personal/adopted skill source이고, `third-party/adopted-skills.json`은 provenance를 기록합니다. 외부 manager-owned skills는 public pins만 `third-party/skills.lock.json`에 남깁니다.
- `herdr/plugins.manifest.json`은 public plugin repositories와 pins를 기록합니다. Managed checkout이나 binaries를 source tree에 복사하지 않습니다.
- `herdr/cron/jobs.snapshot.yaml`은 intentionally empty입니다. Cost audit와 host-sync source가 존재한다는 사실은 scheduled job이 installed 또는 enabled라는 뜻이 아닙니다.
- `agy/settings.snapshot.json`의 permissive policy는 personal example입니다. File-tool permission rules는 arbitrary shell access를 막는 sandbox가 아닙니다.
- `harness-run`은 retained Herdr tab에서 long-running command와 independent agent를 시작하고 state/log를 XDG state directory에 둡니다. `--detach`는 handle만 반환하며 readiness를 증명하지 않습니다.
- Built-in task agents는 OMP Agent Hub에 남습니다. `harness-run agent`는 별도 conversation이므로 explicit brief가 필요합니다.

### WSL에서 Windows Chrome

기록된 NAT-mode WSL 환경에서 Windows Chrome은 remote-debugging address를 지정해도 loopback에만 listen했고 WSL-to-host gateway access가 차단되었습니다. `skills/windows-chrome/scripts/windows-chrome.js`는 Windows `node.exe` relay를 process마다 interop으로 연결해 이를 우회합니다.

WSL과 Windows가 같은 port를 쓰면 localhost forwarding과 relay가 서로 되돌아오는 loop가 생길 수 있어 WSL 9222와 Windows 19222를 분리합니다. Chrome이 반환하는 WebSocket URL은 request `Host` header를 따르므로 relay가 client-facing host로 normalize합니다. 이는 관측한 WSL/Chrome 조합의 mechanism이며 모든 network mode의 보장이 아닙니다.

### Herdr와 AGY

AGY의 print mode는 process cwd와 별도의 workspace를 선택할 수 있으므로 automation은 작업 directory를 명시해야 합니다. Model UI display name과 `--model` ID의 형식도 같다고 가정하지 않습니다.

Herdr의 화면 기반 완료 감지는 integration마다 신뢰도가 다릅니다. Detached process, screen marker, or scheduler `success`는 실제 service readiness, final response, or remote publication proof가 아닙니다. `harness-run`은 exit state와 log를 보존하지만 caller가 intended outcome을 따로 확인해야 합니다.

## 8. 모델 프로필·컨텍스트 정책의 근거 (2026-09-07)

현재 정책의 정본은 `omp/profiles.json`입니다. Fable 5.1과 Astra는 medium, AGY Flash는 high를 사용하며 AGY Opus 4.6 Thinking은 별도 effort 선택을 노출하지 않습니다. Model guide, OMP catalog, runtime behavior를 분리해 해석합니다.

- [OpenAI Compaction](https://developers.openai.com/api/docs/guides/compaction)의 `context_management`는 Responses request field입니다. 문서 예시 threshold는 보편적인 optimum이 아닙니다. Standalone compaction의 반환 window는 일부 item만 골라내지 않고 전체를 다음 request에 전달해야 합니다.
- [Claude Compaction](https://platform.claude.com/docs/en/build-with-claude/compaction)은 beta와 strategy를 request와 replay 양쪽에 요구합니다. Minimum input token 조건에 못 미친 요청은 성공한 compaction으로 표시하지 않습니다.
- Opaque provider state는 다른 provider로 그대로 옮기지 않습니다. Provider를 건널 때에는 human-readable portable handoff를 사용합니다.
- Context trigger는 advertised maximum만이 아니라 effective window와 output reserve를 고려합니다. `extendedContext`가 false이면 premium long-context threshold가 있는 OMP catalog model의 effective window가 먼저 줄 수 있습니다.
- [Codex config reference](https://learn.chatgpt.com/docs/config-file/config-reference)의 key는 Codex config contract입니다. 같은 model을 쓴다는 이유로 OMP config에 복사하지 않습니다.
- Prompting guidance는 model-specific overlay에 필요한 차이만 둡니다. Common repository rules와 skills 전체를 모든 request에 중복 삽입하지 않습니다.

### 적용·검증 결과

기록된 구현 검증은 Bun 1.3.14와 OMP 18.1.13 compatibility source를 대상으로 했습니다.

- Profile tests cover purpose/model effort precedence, session override isolation, shared-profile opt-in, context reserve, and protected provider switching.
- Account tests cover provider-scoped selection, shared pin state, automatic selection return, and token non-copying.
- `harness-run` tests cover argument preservation, nonzero exit, detached state, and independent-agent invocation.
- Benchmark unit tests exercise selection, fixture protection, grading, cost-accounting boundaries, and dry-run without model calls.

이 기록은 실제 사용자 계정의 model availability, provider uptime, paid API quality, 모든 host 조합을 증명하지 않습니다.

### 기본 effort 명령의 세션 격리

기본 `/effort <level>`은 현재 대화와 model에만 적용되고 shared OMP config를 쓰지 않습니다. `/effort reset`은 그 override를 제거합니다. `/profile`로 용도를 다시 고르면 선택한 model의 session override를 정리하고 profile value를 적용합니다.

Regression boundary는 같은 model을 쓰는 두 session 중 한쪽의 effort 변경이 다른 쪽이나 shared config를 바꾸지 않는지를 확인합니다. Session replay는 `harness-session-effort` conversation entry를 사용합니다. `--profile`을 명시한 변경은 이 격리 계약의 의도적인 예외입니다.

### 네이티브 compaction 구현·검증

이 절은 이전 native 생성 구현의 관측입니다. 현재 일반 세션은 OMP 내장 압축을 사용하며, 확장은 이미 저장된 native 상태의 재생·portable 이전만 담당합니다. 현재 동작과 적용 조건은 [사용법](guides/usage.md#자동-압축과-기존-native-상태-이전)이 정본입니다. 아래 생성·과금 테스트 설명은 현재 테스트 목록이 아닙니다.

`omp/extensions/native-compaction`은 OMP 18.1.13의 compaction hook과 final request transform을 사용합니다. Opaque state는 session의 `preserveData.harnessNativeCompaction`에 chunk와 integrity hash로 보존하여 serialization truncation을 피합니다. `/clear` 이후에는 이전 state를 재사용하지 않습니다.

- General OpenAI Responses adapter는 standalone compaction 반환 window 전체를 보존합니다. Codex transport에서 standalone endpoint가 지원되지 않은 관측 때문에 installed OMP의 native Responses transport와 trigger를 사용합니다.
- Claude request와 replay 양쪽에 필요한 beta와 strategy를 포함합니다. Pause response를 committed compaction entry로 만든 뒤 다음 request에 replay합니다.
- Manual native compaction 뒤 짧은 conversation에서도 portable handoff hook에 도달하도록 OMP 18.1.13 runtime patch가 event timeout과 hook gate를 조정합니다. 다른 event timeout은 넓히지 않습니다.
- Usage for compaction iteration is stored separately in compaction details. Existing `omp stats` message total에 자동으로 합산된다고 주장하지 않습니다.
- Regression tests cover full-window preservation, tool-call/result pairs, provider errors, cancellation, chunk integrity, session replay, usage accounting, and existing profile/account behavior.

설치된 OMP process는 extension과 runtime patch를 읽도록 재시작해야 합니다. Upgrade 뒤에는 patch와 regression boundary를 다시 확인하며, 다른 OMP version에 자동 적용하지 않습니다.

## 9. 내장 압축과 플러그인 핀 갱신 (2026-09-08)

일반 세션은 OMP 내장 압축을 사용하고, 기존 Harness-native 상태만 portable 이전 경로로 처리하도록 변경했습니다. 현재 동작은 [사용법](guides/usage.md#자동-압축과-기존-native-상태-이전)에 설명합니다. `bun test omp/native-runtime.test.ts omp/extensions/native-compaction omp/extensions/accounts omp/extensions/profiles`는 38개 테스트와 134개 assertions를 통과했습니다. 설치된 OMP 18.1.14의 compiled CLI 계정 경로를 합성 OAuth·loopback 서버로 확인했으며, 유료 공급자 API의 가용성을 검증한 결과는 아닙니다.

별도 합성 SDK 실행에서는 shake 산출물 저장 실패 시 원본 branch가 유지되었고, 정상 저장 후 원문 artifact 조회와 디스크 재개 후 복구 참조 보존을 확인했습니다. 합성 입력의 토큰 추정치는 실제 비용·속도 개선이나 장기 요약 품질을 입증하지 않습니다. 이번 통합에서는 설치·재시작·플러그인 업데이트를 실행하지 않았습니다.

`herdr/plugins.manifest.json`은 다음 설치 핀을 기록합니다. 원격 확인 당시 각 핀은 해당 `huketo` 저장소의 `main`과 일치했습니다.

| 플러그인 | 버전 | 커밋 |
| --- | --- | --- |
| herdr-cron | 0.2.2 | `3805d2c` |
| Herdr HITL | 0.2.1 | `b478557` |
| Herdr Sheep | 0.3.1 | `dc60164` |
| Agent Usage | 0.5.12 | `7cdbc13` |

HITL 기록을 0.2.0에서 [0.2.1](https://github.com/huketo/herdr-hitl/releases/tag/v0.2.1)로 갱신했습니다. 이 릴리스의 [IPC 수정](https://github.com/huketo/herdr-hitl/commit/d594c5eb023fc4bb87b15d87ff8a21124320d164)은 timeout 미지정과 명시적인 `0`을 구분하고 알림 유지 시간을 daemon 설정에 맡깁니다. 이는 설치된 핀의 변경이력이며 Telegram rate limit을 해결했다고 주장하지 않습니다.

Agent Usage는 AGY 지원 등이 포함된 `huketo/herdr-agent-usage` fork를 유지합니다. [upstream과의 비교](https://github.com/huketo/herdr-agent-usage/compare/7cdbc13a3443d3868496d3d3f821bca2710b4b81...df95abc0ba2edb002697d49a218868f87f823a3e)에서는 fork 고유 커밋 6개와 upstream 고유 커밋 3개가 확인되었습니다. Upstream의 0.5.13·sidebar cache diagnostics는 별도 통합 검토 대상이며, 설치 핀을 upstream으로 교체하지 않았습니다.

## 10. awesome-interface 편입과 검증 (2026-09-09)

`awesome-interface`는 한 개의 `SKILL.md`, 여섯 전문 영역, 다섯 작업 절차, 공통 리뷰 양식으로 구성됩니다. [Jakub Krehel의 skills](https://github.com/jakubkrehel/skills/tree/267330e1adfc66a718fb65fa6918c1f06d0a689e)와 [make-interfaces-feel-better](https://github.com/jakubkrehel/make-interfaces-feel-better/tree/35545ea1512ad59fa463e6b1f95ca9c052981fe6)의 MIT 자료를 선별·재구성했습니다. 라이선스를 확인하지 못한 `oklch-skill`의 고유 콘텐츠는 복사하지 않았습니다. 입력 revision·해시·고지와 변경 경계는 `third-party/adopted-skills.json`의 개별 항목에 있습니다.

OMP 18.1.15, `openai-codex/gpt-6-astra:low`에서 합성 입력 10개와 기존 설치본 비교 3개를 실행했습니다. 후보의 문구 수정은 writing만, 버튼 이름 수정은 accessibility와 writing을 읽었고, 전체 검토는 여섯 영역을 모두 읽었습니다. 수정 도구가 제공된 리뷰 사례도 fixture를 변경하지 않았습니다. backend 타입 설명과 문자열 배열 요청은 UI 스킬이나 특수 모드를 호출하지 않았습니다. 변경 리뷰는 이름 제거를 HIGH 회귀로 분류했습니다. 스트레스·대안·설명 사례는 요청된 계획·근거 경계를 확인했으며, 실제 대안 앱 생성이나 외부 사이트 분석까지 검증한 것은 아닙니다.

초기 이름·설명 문자열은 나머지 설치 스킬을 동일하게 유지한 조건에서 8,790자에서 8,241자로 줄었습니다. 표시 항목은 36개에서 30개로 줄었으며 이 중 UI 영역은 7개에서 1개로 바뀌었습니다. 각 사례 1회뿐이고 작은 요청의 라우터 읽기 비용도 있어, 전체 토큰·비용·호출 정확도가 개선됐다고 주장하지 않습니다. 최초 평가 실행은 discovery 함수에 스킬의 부모 디렉터리 대신 스킬 디렉터리를 넘겨 후보를 찾지 못했습니다. 해당 결과를 제외하고, 실제 후보 노출을 검사하도록 고친 평가기로 위 13개 실행을 다시 수행했습니다.

합성 fixture의 후보 출력은 Chromium에서 별도로 확인했습니다. 320px에서 이름이 있는 닫기 버튼과 가시적 포커스, Tab·Enter 활성화, 넘침 없음을 확인했고, 데스크톱에서 수정된 복구 문구와 키보드 저장 활성화를 확인했습니다. 자동화 click helper는 보이는 버튼에서도 timeout이 발생해 키보드 경로로 검증했습니다. 스크린리더 발화·200% 확대·포인터 자동화 성공을 주장하지 않습니다.

독립적인 Claude 계열 제한 리뷰어가 세 구현 슬라이스를 검토했고 blocking은 없었습니다. 확인된 보완 사항인 색상 외 상태 단서, 규칙 중복, 대안 preview의 수명, 스트레스 증거 보존은 통합 시 반영했습니다. 구조 검사에서는 단일 스킬 진입점, 105개 로컬 Markdown 링크, 두 MIT 출처와 10개 평가 입력이 확인됐습니다. 평가 입력은 `skills/awesome-interface/evals/`에 있으며 실제 응답·비교 화면·캡처는 배포하지 않습니다.
