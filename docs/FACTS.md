# 하네스 통합 레포의 확인된 사실

이 문서는 공개 가능한 기술 관측과 그 한계를 기록합니다. 날짜가 있는 관측은 다른 버전이나 호스트의 성능 보장이 아닙니다. 2026-09-10부터 accounts·native-compaction 확장과 전용 런타임 패치를 제거하고 OMP 내장 기능을 사용합니다. 이전 버전의 코드·패치·테스트 경로는 이력이며 현재 설치 지침이 아닙니다.

## 1. 도구 가용성

- 현재 설치기는 OMP CLI와 SDK를 패치하지 않습니다. 계정 선택은 내장 `/session pin`, 압축은 관리 설정과 내장 `/compact`를 사용합니다. 현재 설치·설정의 정본은 [설치 안내](guides/installation.md)입니다.
- Bun 1.3.14가 설치기, TypeScript extension, `omp-profile`, `harness-run`, cost audit, host-sync의 기준 환경입니다.
- Python 3 표준 라이브러리의 `sqlite3`와 `json`은 benchmark와 collector에 사용됩니다. `sqlite3`나 `jq` CLI가 모든 Herdr/cron 환경에 있다고 가정하지 않습니다.
- 네이티브 Windows와 macOS는 설치 대상으로 확인하지 않았습니다. WSL2의 BrowserSkill 연결 검증은 전체 Windows 설치 지원과 별개입니다.

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
- 계정 선택은 OMP 내장 `/session pin`으로 수행합니다. 제거한 `/account`의 공용 선택 동기화는 제공하지 않으며, 내장 pin을 엄격한 과금 잠금으로 간주하지 않습니다.
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

### BrowserSkill on WSL2

2026-09-21에 Linux x64 `bsk 0.3.0`과 Windows Chrome 152의 BrowserSkill extension 0.3.0을 확인했습니다. WSL loopback의 기본 port 52800에서 daemon protocol 1.3과 extension protocol 1.3이 연결됐고, `bsk doctor --json`은 manager-owned `codex`·`claude-code` skill을 포함해 `fail`이나 `warn` 없이 통과했습니다.

CLI session은 `https://example.com`을 열어 “Example Domain”과 documentation-use 설명을 관찰한 뒤 중지됐고, fresh OMP 실행은 `--skills=browser-skill`로 같은 BrowserSkill workflow를 완료했습니다. 이는 해당 WSL2/Windows Chrome 조합의 local connection과 skill discovery를 확인한 결과이며 다른 network mode나 future release의 보장이 아닙니다.

### Herdr와 AGY

AGY의 print mode는 process cwd와 별도의 workspace를 선택할 수 있으므로 automation은 작업 directory를 명시해야 합니다. Model UI display name과 `--model` ID의 형식도 같다고 가정하지 않습니다.

Herdr의 화면 기반 완료 감지는 integration마다 신뢰도가 다릅니다. Detached process, screen marker, or scheduler `success`는 실제 service readiness, final response, or remote publication proof가 아닙니다. `harness-run`은 exit state와 log를 보존하지만 caller가 intended outcome을 따로 확인해야 합니다.

## 8. 모델 프로필·컨텍스트 정책의 근거 (2026-09-07)

현재 정책의 정본은 `omp/profiles.json`입니다. Fable 5.1과 Astra는 medium, AGY Flash는 high를 사용하며 AGY Opus 4.6 Thinking은 별도 effort 선택을 노출하지 않습니다. Model guide, OMP catalog, runtime behavior를 분리해 해석합니다. 이 절의 모델·effort는 2026-09-07 기준이며, 2026-09-23 개편 이후의 선택과 근거는 12절에 있습니다.

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

이 절은 제거된 native 구현의 과거 관측입니다. 현재는 OMP 내장 압축만 사용하며, 기존 `harnessNativeCompaction` 상태의 replay·portable 이전도 제공하지 않습니다. 데이터 이전 없이 해당 legacy 상태에 의존하는 세션의 재개를 보장하지 않습니다. 현재 동작은 [사용법](guides/usage.md#내장-자동-압축)이 정본이며, 아래 생성·과금 테스트 설명은 현재 테스트 목록이 아닙니다.

`omp/extensions/native-compaction`은 OMP 18.1.13의 compaction hook과 final request transform을 사용합니다. Opaque state는 session의 `preserveData.harnessNativeCompaction`에 chunk와 integrity hash로 보존하여 serialization truncation을 피합니다. `/clear` 이후에는 이전 state를 재사용하지 않습니다.

- General OpenAI Responses adapter는 standalone compaction 반환 window 전체를 보존합니다. Codex transport에서 standalone endpoint가 지원되지 않은 관측 때문에 installed OMP의 native Responses transport와 trigger를 사용합니다.
- Claude request와 replay 양쪽에 필요한 beta와 strategy를 포함합니다. Pause response를 committed compaction entry로 만든 뒤 다음 request에 replay합니다.
- Manual native compaction 뒤 짧은 conversation에서도 portable handoff hook에 도달하도록 OMP 18.1.13 runtime patch가 event timeout과 hook gate를 조정합니다. 다른 event timeout은 넓히지 않습니다.
- Usage for compaction iteration is stored separately in compaction details. Existing `omp stats` message total에 자동으로 합산된다고 주장하지 않습니다.
- Regression tests cover full-window preservation, tool-call/result pairs, provider errors, cancellation, chunk integrity, session replay, usage accounting, and existing profile/account behavior.

당시 설치된 OMP process는 extension과 runtime patch를 읽도록 재시작해야 했으며, 다른 OMP version에는 패치를 자동 적용하지 않았습니다. 이 패치는 현재 배포에서 제거되었습니다.

## 9. 내장 압축과 플러그인 핀 갱신 (2026-09-08)

2026-09-08에는 일반 세션을 OMP 내장 압축으로 처리하고, 기존 Harness-native 상태만 portable 이전 경로로 처리하도록 변경했습니다. 이후 두 확장이 제거되었으며 현재 동작은 [사용법](guides/usage.md#내장-자동-압축)을 따릅니다. 당시 `bun test omp/native-runtime.test.ts omp/extensions/native-compaction omp/extensions/accounts omp/extensions/profiles`는 38개 테스트와 134개 assertions를 통과했습니다. OMP 18.1.14의 compiled CLI 계정 경로를 합성 OAuth·loopback 서버로 확인했으며, 유료 공급자 API의 가용성을 검증한 결과는 아닙니다.

별도 합성 SDK 실행에서는 shake 산출물 저장 실패 시 원본 branch가 유지되었고, 정상 저장 후 원문 artifact 조회와 디스크 재개 후 복구 참조 보존을 확인했습니다. 합성 입력의 토큰 추정치는 실제 비용·속도 개선이나 장기 요약 품질을 입증하지 않습니다. 이번 통합에서는 설치·재시작·플러그인 업데이트를 실행하지 않았습니다.

`herdr/plugins.manifest.json`은 다음 설치 핀을 기록합니다. 원격 확인 당시 각 핀은 해당 `huketo` 저장소의 `main`과 일치했습니다.

| 플러그인 | 버전 | 커밋 |
| --- | --- | --- |
| herdr-cron | 0.2.2 | `3805d2c` |
| Herdr HITL | 0.2.1 | `b478557` |
| Herdr Sheep | 0.3.1 | `dc60164` |
| Agent Usage | 0.5.12 | `7894d50` |

HITL 기록을 0.2.0에서 [0.2.1](https://github.com/huketo/herdr-hitl/releases/tag/v0.2.1)로 갱신했습니다. 이 릴리스의 [IPC 수정](https://github.com/huketo/herdr-hitl/commit/d594c5eb023fc4bb87b15d87ff8a21124320d164)은 timeout 미지정과 명시적인 `0`을 구분하고 알림 유지 시간을 daemon 설정에 맡깁니다. 이는 설치된 핀의 변경이력이며 Telegram rate limit을 해결했다고 주장하지 않습니다.

Agent Usage는 `huketo/herdr-agent-usage` fork의 `7894d50`을 사용합니다. 이 핀은 Claude가 로컬에 기록한 모델 전용 주간 한도에서 Fable 사용량을 표시하고, 안정적인 비대화형 인증 경로가 없는 Antigravity provider를 제거하며, 지원 종료된 agent의 오래된 usage metadata를 정리합니다. Upstream 0.5.13과 sidebar cache diagnostics 통합은 별도 검토 대상입니다.

## 10. awesome-interface 편입과 검증 (2026-09-09)

`awesome-interface`는 한 개의 `SKILL.md`, 여섯 전문 영역, 다섯 작업 절차, 공통 리뷰 양식으로 구성됩니다. [Jakub Krehel의 skills](https://github.com/jakubkrehel/skills/tree/267330e1adfc66a718fb65fa6918c1f06d0a689e)와 [make-interfaces-feel-better](https://github.com/jakubkrehel/make-interfaces-feel-better/tree/35545ea1512ad59fa463e6b1f95ca9c052981fe6)의 MIT 자료를 선별·재구성했습니다. 라이선스를 확인하지 못한 `oklch-skill`의 고유 콘텐츠는 복사하지 않았습니다. 입력 revision·해시·고지와 변경 경계는 `third-party/adopted-skills.json`의 개별 항목에 있습니다.

OMP 18.1.15, `openai-codex/gpt-6-astra:low`에서 합성 입력 10개와 기존 설치본 비교 3개를 실행했습니다. 후보의 문구 수정은 writing만, 버튼 이름 수정은 accessibility와 writing을 읽었고, 전체 검토는 여섯 영역을 모두 읽었습니다. 수정 도구가 제공된 리뷰 사례도 fixture를 변경하지 않았습니다. backend 타입 설명과 문자열 배열 요청은 UI 스킬이나 특수 모드를 호출하지 않았습니다. 변경 리뷰는 이름 제거를 HIGH 회귀로 분류했습니다. 스트레스·대안·설명 사례는 요청된 계획·근거 경계를 확인했으며, 실제 대안 앱 생성이나 외부 사이트 분석까지 검증한 것은 아닙니다.

초기 이름·설명 문자열은 나머지 설치 스킬을 동일하게 유지한 조건에서 8,790자에서 8,241자로 줄었습니다. 표시 항목은 36개에서 30개로 줄었으며 이 중 UI 영역은 7개에서 1개로 바뀌었습니다. 각 사례 1회뿐이고 작은 요청의 라우터 읽기 비용도 있어, 전체 토큰·비용·호출 정확도가 개선됐다고 주장하지 않습니다. 최초 평가 실행은 discovery 함수에 스킬의 부모 디렉터리 대신 스킬 디렉터리를 넘겨 후보를 찾지 못했습니다. 해당 결과를 제외하고, 실제 후보 노출을 검사하도록 고친 평가기로 위 13개 실행을 다시 수행했습니다.

합성 fixture의 후보 출력은 Chromium에서 별도로 확인했습니다. 320px에서 이름이 있는 닫기 버튼과 가시적 포커스, Tab·Enter 활성화, 넘침 없음을 확인했고, 데스크톱에서 수정된 복구 문구와 키보드 저장 활성화를 확인했습니다. 자동화 click helper는 보이는 버튼에서도 timeout이 발생해 키보드 경로로 검증했습니다. 스크린리더 발화·200% 확대·포인터 자동화 성공을 주장하지 않습니다.

독립적인 Claude 계열 제한 리뷰어가 세 구현 슬라이스를 검토했고 blocking은 없었습니다. 확인된 보완 사항인 색상 외 상태 단서, 규칙 중복, 대안 preview의 수명, 스트레스 증거 보존은 통합 시 반영했습니다. 구조 검사에서는 단일 스킬 진입점, 105개 로컬 Markdown 링크, 두 MIT 출처와 10개 평가 입력이 확인됐습니다. 평가 입력은 `skills/awesome-interface/evals/`에 있으며 실제 응답·비교 화면·캡처는 배포하지 않습니다.

## 11. 스킬 description 축소와 git-commit 편입 (2026-09-09)

10절 이후 설치 스킬 전체를 단일 진입점·내부 라우팅 후보로 다시 조사했습니다. OMP 18.1.15는 시스템 프롬프트에 `name`과 `description`만 렌더링하고(`src/prompts/system/system-prompt.md:32-36`), `disable-model-invocation`은 `hide`로 정규화되어 목록에서 빠지며(`src/extensibility/skills.ts:113`), 본문과 참조는 `read skill://…`에서만 로드됩니다(`src/internal-urls/skill-protocol.ts:51-95`). `allowed-tools`는 `discovery/agent-plugin-format.ts:94,155-158`에서 문자열 타입만 검증하며 도구 실행 경로에서 참조되지 않습니다. 추가 통합 후보는 소유권(관리형·CLI 제공)이나 작업 단위 차이로 채택하지 않았고, 라우팅보다 description 길이가 더 큰 상시 비용이었습니다.

`daily-report`, `code-review`, `diagnosing-bugs`, `tdd`, `writing-for-agents`의 description을 트리거 조건만 남기도록 줄였고 본문은 바꾸지 않았습니다. `diagnosing-bugs`와 `tdd`는 "원인 미상"과 "원인이 테스트 환경으로 확인됨"으로 간헐 실패 트리거를 나눴고, `writing-for-agents`는 `skill-creator`와 겹치던 "creating or editing skills"를 제거했습니다. `git-commit`은 [github/awesome-copilot](https://github.com/github/awesome-copilot/tree/7568a482ce2df38f8965ab5336a3220db796a4ba)(MIT)에서 편입하고 `third-party/adopted-skills.json`에 이전 등록·입력 해시·로컬 변경을 기록했습니다.

같은 로더로 같은 설치 목록을 읽은 조건에서 가시 이름·설명 문자 수는 8,241자에서 6,554자로 줄었습니다(항목 30개 동일). 라우팅 프로브는 OMP SDK `openai-codex/gpt-6-astra:low`, 도구 read/glob/grep, 빈 합성 작업 디렉터리에서 긍정 13·부정 7 프롬프트를 각 1회 실행했고 기준선과 후보 모두 20/20 통과했습니다. 각 사례 1회이므로 호출 정확도의 통계적 개선이나 전체 토큰·비용 절감을 주장하지 않습니다. 제한 SDK 리뷰어(다른 모델 계열) 1회차에서 blocking은 없었고 nit 4건을 반영했습니다.

`herdr-hitl`의 description은 upstream v0.3.1에서 줄였고, 따옴표 없는 값의 `: `를 엄격한 YAML 파서가 거부하여 v0.3.2에서 값을 인용했습니다. OMP 로더가 경고 없이 읽는 것과 `skills` CLI가 설치할 수 있는 것은 다른 조건입니다.

## 12. 새 모델 기준 라우팅 개편 (2026-09-23)

2026-09-22에 공개된 Claude Opus 5.5, GPT-6 Sol, GPT-6 Luna를 기준으로 용도 프로필, 내장 역할, 모델별 지침, 벤치 후보를 다시 정했습니다. Fable 5.1과 GPT-6 Astra가 맡던 역할은 Opus 5.5로 옮기고 Sol과 Luna는 비용 계층으로 둡니다. 근거는 아래 공급사 자료와 Artificial Analysis(AA) 조회이며, 측정값은 조회 시점의 외부 결과이지 이 하네스 안의 성능 보장이 아닙니다.

### 공급사 자료

- [Opus 5.5 발표](https://www.anthropic.com/claude-opus-5-5)는 대부분의 작업에서 Fable 5.1 수준이고 기본 설정에서 Opus 5보다 40% 적게 든다고 밝힙니다. 단가는 입력 $4, 출력 $20, 캐시 읽기 $0.20입니다.
- [Opus 5.5 프롬프트 가이드](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5)는 기본 effort `medium`(Opus 5는 `high`)에서 시작해 자체 평가로 여러 단계를 비교하라고 권하고, `xhigh`·`max`는 품질 향상을 측정한 작업에만 쓰라고 적습니다. 요청 최상위 effort를 바꾸면 프롬프트 캐시가 무효화되고, 도구 없이 effort를 올려도 차트 읽기는 거의 나아지지 않는다고 설명합니다. 무인 실행 절은 도구 호출 없이 끝난 턴을 완료가 아니라 보고로 다루라고 하며, 소스 코드의 취약점 찾기는 사이버보안 안전장치의 허용 범위로 적습니다.
- [GPT-6 Sol·Luna 발표](https://openai.com/index/introducing-gpt-6-sol-and-luna/)는 두 모델 API 단가를 GPT-5.6 대비 50% 내린 $2/$10, $0.10/$0.50로 밝힙니다.
- [GPT-6 가이드](https://developers.openai.com/api/docs/guides/latest-model)는 이전 모델의 실효 reasoning effort를 유지하라고 권하고, Sol과 Luna는 `none`을 지원하지만 Astra는 지원하지 않는다고 적습니다. 자율 진행, 지시·스킬 우선순위, 평이한 문장, 위임, 테스트 범위 조절 지침이 있습니다.

`omp/prompts/claude-opus-5-5.txt`, `gpt-6-sol.txt`, `gpt-6-luna.txt`는 이 중 완료 조건, 진행 알림, 자율 진행, 지시 우선순위, 필요한 만큼의 검증, 간결한 문장만 짧게 담습니다.

### Artificial Analysis

[모델 리더보드](https://artificialanalysis.ai/leaderboards/models)(Intelligence Index v4.3.2, 2026-09-23 조회)의 값입니다. Anthropic 행은 AA 표기상 "with fallback" 조건이고, 작업당 비용은 AA 지수 실행의 API 비용입니다.

| 모델·강도 | Intelligence | Terminal-Bench 4.0 | 작업당 비용 | 출력 tok/s 중앙값 | 첫 청크 s 중앙값 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Opus 5.5 max | 58 | 60% | $5.98 | — | — |
| Opus 5.5 xhigh | 56 | 60% | $3.46 | 76 | 165.2 |
| Opus 5.5 high | 54 | 57% | $1.82 | 90 | 12.8 |
| Opus 5.5 medium | 51 | 53% | $1.34 | 76 | 22.8 |
| Fable 5.1 high | 51 | 52% | $3.91 | 56 | 26.2 |
| Astra high | 51 | 54% | $1.73 | 49 | 79.0 |
| Sol max | 48 | 44% | $1.06 | 115 | 102.2 |
| Sol xhigh | 44 | 30% | $0.53 | 128 | 46.5 |
| Sol high | 43 | 26% | $0.37 | 119 | 9.9 |
| Luna max | 37 | 13% | $0.07 | 154 | 124.2 |
| Luna xhigh | 34 | 8% | $0.04 | 153 | 22.5 |

### 강도 결정

- **Opus 5.5 일상 작업은 high**입니다(`frontend`·`orchestrate`·`opus-code`, `default`·`designer`·`plan`·`vision` 역할). 이전 Opus 코딩 프로필이 high였고, AA에서 high는 medium보다 지수 3점, Terminal-Bench 4%p 높습니다. 비코딩 `opus-general`은 공급사 기본값 medium입니다.
- **어려운 작업과 최상위 계층은 xhigh**입니다(`hard-code`·`best`, `slow`·`advisor` 역할). AA에서 high보다 2점과 3%p 높지만 비용은 약 1.9배입니다. 공급사 권고에 따라 일상 역할에는 쓰지 않고, AA Terminal-Bench가 xhigh와 같은 `max`는 쓰지 않습니다.
- **`vision` 역할은 `best`가 아니라 `frontend`를 따릅니다.** `read <image>?q=`의 위임 질문은 `images.questionTimeoutMs` 안에 끝나야 하는데 AA의 xhigh 첫 청크 중앙값은 165초이고, 공급사는 도구 없이 effort를 올려도 차트 읽기가 거의 나아지지 않는다고 적습니다.
- **Sol `code`는 high, `general`은 medium**입니다. GPT-6 가이드의 권고대로 이전 GPT-5.6 Sol의 강도를 유지했습니다. AA에서 xhigh는 1점과 4%p 높지만 비용이 약 1.4배입니다.
- **Luna는 max를 유지**합니다. 이전 강도와 같고 AA에서 xhigh보다 3점과 5%p 높지만, 첫 청크 중앙값이 124초 대 22초입니다. OMP의 `tiny` 역할은 세션 제목 같은 배경 작업에도 쓰이므로 이 지연을 감수하는 선택입니다.
- Fable 5.1과 Astra는 모든 프로필과 역할에서 뺐고, 모델 항목만 명시적 선택과 비교 실행에 남깁니다.

### 설정·러너 변경

- `omp/config.apply.sh`는 OMP 18.2에서 없어진 `librarian` override를 빼고, 18.2.10이 알 수 없는 키로 거부하는 `providers.imageOrder` 대신 `modelRoles.image`를 선언합니다. OMP가 이전 목록을 옮겨 적은 `retry.fallbackChains.image`는 `modelRoles.default`처럼 호스트 값을 채택합니다.
- `bench/bench.py`에 `run --suite`, 과제 `setup`, 버전이 붙은 카탈로그 행 병합을 추가했고 고정 override 키에서 `librarian`을 뺐습니다. `bench/config.json`의 후보와 심판도 새 모델로 바꿨습니다.
- 비용 감사의 반사실 단가는 GPT-6 Luna·Sol이며, 저강도 탐지는 Opus의 `minimal`·`low`만 셉니다.
- 실제 모델을 호출하는 벤치 결과는 이 문서에 싣지 않습니다.
