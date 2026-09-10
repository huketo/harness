# 공급자 과금·프롬프트 캐시·컨텍스트와 OMP 비용 손잡이 (2026-09-05 조사)

## 1. 조사 기준과 값의 의미

조사 기준일은 2026-09-05입니다. 이 문서는 벤치마크가 "같은 모델이라도 설정에 따라 비용이 달라지는" 축을 후보 변형(variant)으로 다루기 위한 근거입니다.

출처 원칙은 세 가지입니다. 첫째, 공급자 값은 실제로 열어 본 공식 문서만 "확인"으로 적고, 열지 못한 것은 "미확인"으로 적으며 추측 URL을 만들지 않았습니다. 둘째, OMP 카탈로그 값은 18.1.13 환경의 `models.db` 구조를 기준으로 읽고 설정은 바꾸지 않았습니다. 셋째, 카탈로그 값과 공식 문서 값이 다르면 둘 다 적고 §6에 모았습니다. 2차 기사·요약은 근거로 쓰지 않았습니다.

카탈로그 단가와 청구액은 다릅니다. OAuth 구독 경로에서 `stats.db`와 세션 JSONL의 `usage.cost.*`는 **카탈로그 단가로 환산한 명목 비용**이며 현금 청구액이 아닙니다. 실제 제약은 `agent.db`의 `usage_history.used_fraction`이 나타내는 구독 한도일 수 있습니다([FACTS](FACTS.md#3-4-ompagentagentdb)). 따라서 `bench/README.md`가 구분하는 `Catalog est/task`와 session-recorded `Actual/task`도 장문 구간·service tier·gateway 경로에 따라 어긋날 수 있으며, 실제 청구액으로 표현하지 않습니다.

공급자 문서 URL 두 곳은 요청 주소에서 리다이렉트되었습니다. `docs.claude.com/...` → `platform.claude.com/...`, `platform.openai.com/docs/...` → `developers.openai.com/api/docs/...`, `developers.openai.com/codex/pricing` → `learn.chatgpt.com/docs/pricing`. 아래 표에는 최종 주소를 적었습니다.

## 2. 공급자별 과금·캐시·컨텍스트

| 공급자 | 항목 | 값 | 조건(TTL, 최소 토큰, 임계값) | URL | 확인 상태 |
| --- | --- | --- | --- | --- | --- |
| Anthropic | Claude Opus 5 단가 | input $5 / output $25 / 캐시읽기 $0.50 / 5분쓰기 $6.25 / 1시간쓰기 $10 (per MTok) | 전 구간 동일 단가 | https://platform.claude.com/docs/en/about-claude/pricing | 확인 |
| Anthropic | Claude Sonnet 5 단가 | input $2 / output $10 / 캐시읽기 $0.20 / 5분쓰기 $2.50 / 1시간쓰기 $4 | $2/$10이 2026-09-01 인상 없이 표준가로 확정 | https://platform.claude.com/docs/en/about-claude/pricing | 확인 |
| Anthropic | 캐시 배수 | 5분 쓰기 1.25배, 1시간 쓰기 2배, 읽기 0.1배 | 배수는 배치 할인·데이터 레지던시와 곱해짐 | https://platform.claude.com/docs/en/about-claude/pricing | 확인 |
| Anthropic | 캐시 TTL | 기본 5분, 옵션 1시간(`cache_control.ttl:"1h"`) | 수명은 **요청 시작 시각**부터 계산되고 적중 시 무료 갱신. 응답 생성 시간도 수명을 깎음 | https://platform.claude.com/docs/en/build-with-claude/prompt-caching | 확인 |
| Anthropic | 캐시 최소 토큰 | Opus 5 = 512, Sonnet 5 = 1,024 | 미달 시 오류 없이 캐시 없이 처리됨 | https://platform.claude.com/docs/en/build-with-claude/prompt-caching | 확인 |
| Anthropic | 캐시 적중 조건 | 프리픽스 해시 일치 + 브레이크포인트 최대 4개 + **되돌아보기 창 20 블록** | `tools`→`system`→`messages` 계층. 상위 변경은 하위 전부 무효화. 도구 정의·effort 변경도 무효화 | https://platform.claude.com/docs/en/build-with-claude/prompt-caching | 확인 |
| Anthropic | 장문 구간 | 임계값 없음 — 1M 창 전체가 표준 단가 | Claude 4.6 이상. 900k 요청과 9k 요청의 per-token 단가가 같음 | https://platform.claude.com/docs/en/about-claude/pricing | 확인 |
| Anthropic | 컨텍스트 창 | Opus 5·Sonnet 5 = 1M, 출력 상한 128k | 베타 헤더 불필요(1M이 기본). 캐시된 프리픽스도 창을 점유함 | https://platform.claude.com/docs/en/build-with-claude/context-windows | 확인 |
| Anthropic | 배치 | 입력·출력 50% 할인 (Opus 5 $2.50/$12.50) | Fast mode와 병용 불가 | https://platform.claude.com/docs/en/about-claude/pricing | 확인 |
| Anthropic | Fast mode | Opus 5 input $10 / output $50 | `speed:"fast"`. 200k 초과 구간에도 동일 적용. 1st-party API 전용. 캐시 배수가 그 위에 곱해짐 | https://platform.claude.com/docs/en/about-claude/pricing | 확인 |
| Anthropic | 구독 한도의 의미 | Max 5x $100/월, Max 20x $200/월 = Pro 대비 세션당 5배·20배 | **5시간 세션 한도 + 계정별 고정 시각의 주간 한도**, 전 모델 공통. claude.ai와 Claude Code가 같은 한도를 공유 | https://support.claude.com/en/articles/11049741-what-is-the-max-plan | 확인 |
| Anthropic | 구독의 과금 성격 | 구독 사용분은 청구되지 않음. API 크레딧으로 넘어가면 표준 API 단가로 별도 청구 | 사용자 동의 없이 전환되지 않음 | https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan | 확인 |
| OpenAI | gpt-6-astra 단가 | 단문 input $10 / output $50 / 캐시읽기 $1 / 캐시쓰기 $12.50, 장문 $20 / $75 / $2 / $25 (per MTok) | Standard 기준. 구독 경로의 카탈로그 0과 구분(§6) | https://developers.openai.com/api/docs/pricing | 확인 |
| OpenAI | gpt-5.6-sol 단가 | 단문 $4 / 캐시읽기 $0.40 / 캐시쓰기 $5 / 출력 $20 | 프로모션가, 최소 2026-11-21까지 유지 | https://developers.openai.com/api/docs/pricing | 확인 |
| OpenAI | gpt-5.6-terra 단가 | 단문 $2 / $0.20 / $2.50 / 출력 $12 | — | https://developers.openai.com/api/docs/pricing | 확인 |
| OpenAI | gpt-5.6-luna 단가 | 단문 $0.20 / $0.02 / $0.25 / 출력 $1.20 | — | https://developers.openai.com/api/docs/pricing | 확인 |
| OpenAI | 캐시 배수 | 쓰기 1.25배, 읽기 0.1배 (GPT-5.6 이상) | GPT-5.5 이하는 쓰기 요금 없음. 1회 쓰기+1회 완전 재사용 = 1.35배 | https://developers.openai.com/api/docs/guides/prompt-caching | 확인 |
| OpenAI | 캐시 TTL | `prompt_cache_options.ttl` = `30m` (유일값·기본값) | 최근 쓰기/재사용 후 30분 이상 유지, 재사용은 무료 갱신 | https://developers.openai.com/api/docs/guides/prompt-caching | 확인 |
| OpenAI | `prompt_cache_retention` | GPT-5.6에는 **적용되지 않음** (GPT-5.5 이하 전용: `in_memory` 5~10분, `24h`) | ZDR 조직은 `in_memory` 기본, 그 외 `24h` 기본 | https://developers.openai.com/api/docs/guides/prompt-caching | 확인 |
| OpenAI | 캐시 최소 토큰 | GPT-5.6 이상 1,024 (가시 입력 토큰), 이전 모델 2,048 | 숨은 시스템 토큰은 최소치에 계상되지 않음 | https://developers.openai.com/api/docs/guides/prompt-caching | 확인 |
| OpenAI | 캐시 적중 조건 | 렌더된 프리픽스 완전 일치. 암묵 모드는 마지막 적격 메시지 끝에 브레이크포인트, 명시 모드는 요청당 쓰기 4개·읽기 최근 50개 후보 | `model`·`tools`·`parallel_tool_calls`·`text.format`·`reasoning.effort`·`text.verbosity`·`context_management` 변경이 프리픽스를 깨뜨림 | https://developers.openai.com/api/docs/guides/prompt-caching | 확인 |
| OpenAI | 캐시 라우팅 | 캐시는 머신 로컬. 분당 15요청 초과 시 오버플로 라우팅으로 미스 발생 | `prompt_cache_key`는 그룹핑에 영향만 주고 적중을 보장하지 않음 | https://developers.openai.com/api/docs/guides/prompt-caching | 확인 |
| OpenAI | 장문 임계값·배수 | **272K 입력 토큰 초과 시 요청 전체가 입력 2배·출력 1.5배** | sol 장문 = $8 / $0.80 / $10 / $30 | https://developers.openai.com/api/docs/models/gpt-5.6-sol | 확인 |
| OpenAI | 컨텍스트 창 | gpt-5.6-sol 1,050,000 (입력 상한 922,000, 출력 128,000) | — | https://developers.openai.com/api/docs/models/gpt-5.6-sol | 확인 |
| OpenAI | 서비스 티어 flex | 표준의 0.5배(배치 단가와 동일) | 느림·`429 Resource Unavailable` 가능(그 경우 과금 없음). 베타·모델 제한 | https://developers.openai.com/api/docs/guides/flex-processing | 확인 |
| OpenAI | 서비스 티어 priority/fast | 표준의 2배 (sol $8 / $0.80 / $10 / $40) | 2026-07-30에 priority가 fast mode로 개명, 두 값 모두 허용 | https://developers.openai.com/api/docs/pricing | 확인 |
| OpenAI | 배치 | 표준의 0.5배 | — | https://developers.openai.com/api/docs/pricing | 확인 |
| OpenAI | Codex 구독 한도의 의미 | Plus $20/월, Pro $100(5x)·$200(20x)/월. **5시간 창당 로컬 메시지 추정치**: sol 10~100(Plus)·50~500(Pro 5x)·200~2,000(Pro 20x), luna 250~2,000·1,250~10,000·5,000~40,000 | 고정 메시지 수가 아니며 모델·컨텍스트·추론·도구·캐시가 소모량을 좌우함. 로컬 메시지와 클라우드 채팅이 같은 할당량을 쓰고 **주간 한도도 함께 적용될 수 있음**("Weekly limits may also apply"). API 키 경로는 사용량 과금 | https://learn.chatgpt.com/docs/pricing | 확인 |
| OpenAI | 포함 한도 소진 뒤 과금 | ChatGPT 크레딧으로 계속 사용. **크레딧/1M토큰(입력·캐시입력·출력)**: sol 100 / 10 / 500, terra 50 / 5 / 300, luna 5 / 0.5 / 30, GPT-6 Astra 250 / 25 / 1,250 | GPT-5.6 메시지 한 건이 평균 5~30 크레딧. fast mode와 speed 설정은 크레딧 소모율을 올려 포함 한도도 더 빨리 소진시킴. 크레딧 구매 단가와 할인은 플랜·계약에 따라 다름 | https://learn.chatgpt.com/docs/pricing | 확인 |
| Google | Gemini 암묵 캐시 | 기본 활성(2.5 이상). 적중분은 자동 할인 | 최소 입력 토큰: 3.x Flash·3.1 Pro 4,096, 2.5 계열 2,048. 적중량은 `usage.total_cached_tokens` | https://ai.google.dev/gemini-api/docs/caching | 확인 |
| Google | Gemini 명시 캐시 | 캐싱 문서에는 없음(암묵만 문서화). 가격표에는 "Context caching" 토큰 단가가 존재 | 3.8 Flash: 캐시 $0.075/MTok + **저장 $0.50/1M토큰·시간** (2026-12-31까지, 이후 2배) | https://ai.google.dev/gemini-api/docs/pricing | 확인(가격) / 미확인(API) |
| Google | 캐시 TTL | 암묵 캐시의 TTL·수명이 캐싱 문서에 명시되어 있지 않음 | 명시 캐시 쪽은 시간당 저장 요금이 있으므로 보존 시간을 사용자가 정하는 구조로 보이나 문서에서 확인 못 함 [추정] | https://ai.google.dev/gemini-api/docs/caching | 미확인 |
| Google | 캐시 쓰기 배수 | 암묵 캐시에는 쓰기 요금 항목이 없음(적중분만 할인). 명시 캐시는 배수가 아니라 캐시 토큰 단가 0.1배 + 시간당 저장료로 과금 | 3.8 Flash 기준 캐시 토큰 $0.075 대 입력 $0.75 | https://ai.google.dev/gemini-api/docs/pricing | 확인 |
| Google | 장문 임계값 | Gemini 3.x Flash 가격표에는 장문 구간 임계값이 없음(단일 구간) | 조사한 3.8·3.7·3.6·3.5 Flash 항목 모두 구간 구분 없이 단일 단가 표 | https://ai.google.dev/gemini-api/docs/pricing | 확인 |
| Google | Gemini 3.8 Flash 단가 | input $0.75 / output $3.75 (2026-12-31까지, 이후 $1.50/$7.50) | 출력에 thinking 토큰 포함 | https://ai.google.dev/gemini-api/docs/pricing | 확인 |
| Google | Gemini 3.8 Flash 컨텍스트 창 | **입력 토큰 상한 1,048,576 / 출력 토큰 상한 65,536** | 후보 `agy/gemini-3.8-flash-high`가 쓰는 모델. thinking은 low·medium·high만 지원하고 `minimal`은 오류 | https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash | 확인 |
| Google | Gemini 3.8 Flash 소비 옵션 | Batch·Flex·Priority 추론 모두 지원, 캐싱 지원 | 2026년 9월 갱신판 모델 페이지 기준 | https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash | 확인 |
| Google | Gemini 티어 | Batch·Flex 0.5배, Priority 1.8배 (3.8 Flash 기준 $1.35/$6.75) | Flex·Batch는 무료 티어 없음 | https://ai.google.dev/gemini-api/docs/pricing | 확인 |
| Google | Antigravity 요금제 | AI Ultra: 최대 할당량 **5시간마다 갱신** + 최고 주간 한도 + 서드파티 모델. AI Pro: **주간 한도에 닿기 전까지 5시간마다 갱신**. 무료: **주간 갱신만** | 한도는 프롬프트 수가 아니라 에이전트가 한 작업량에 비례함 | https://antigravity.google/docs/plans | 확인 |
| Google | Antigravity 초과분 | AI Pro·Ultra는 구매한 AI 크레딧으로 초과 사용 가능(표준 소비 단가) | `AI Credit Overages` 설정 `Never`/`Always`. BYO 키·엔드포인트 미지원 | https://antigravity.google/docs/plans | 확인 |

## 3. OMP 18.1.13 카탈로그 관측값

출처는 OMP의 `model_cache.models` JSON 구조입니다. 표에는 공개 benchmark 후보와 경로별 비용·context 차이를 설명하는 비교 모델만 남겼습니다. 같은 model ID도 provider에 따라 catalog cost, output limit, thinking mode, long-context metadata가 다를 수 있으므로 selector 전체를 기록해야 합니다.

### 3-1. 기본 단가(USD/MTok)와 컨텍스트

| 모델 | 공급자 경로 | input | output | cacheRead | cacheWrite | contextWindow | maxTokens |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| claude-opus-5 | anthropic | 5 | 25 | 0.5 | 6.25 | 1,000,000 | 128,000 |
| claude-opus-5 | google-vertex (`@default`) | 5 | 25 | 0.5 | 6.25 | 1,000,000 | 128,000 |
| claude-opus-5 | github-copilot | 5 | 25 | 0.5 | 6.25 | 1,000,000 | 64,000 |
| claude-opus-5 | venice | 6 | 30 | 0.6 | 7.5 | 1,000,000 | 128,000 |
| claude-sonnet-5 | anthropic | 2 | 10 | 0.2 | 2.5 | 1,000,000 | 128,000 |
| claude-sonnet-5 | google-vertex (`@default`) | 2 | 10 | 0.2 | 2.5 | 1,000,000 | 128,000 |
| claude-sonnet-5 | github-copilot | 2 | 10 | 0.2 | 2.5 | 1,000,000 | 128,000 |
| claude-sonnet-5 | venice | 3 | 15 | 0.3 | 3.75 | 1,000,000 | 64,000 |
| gpt-5.6-sol | openai-codex | 4 | 20 | 0.4 | 5 | 1,000,000 | 128,000 |
| gpt-5.6-sol | openai | 4 | 20 | 0.4 | 5 | 1,050,000 | 128,000 |
| gpt-5.6-sol | azure | 4 | 20 | 0.5 | 6.25 | 1,050,000 | 128,000 |
| gpt-5.6-sol | github-copilot | 2 | 10 | 0.2 | 2.5 | 1,050,000 | 128,000 |
| gpt-5.6-terra | openai-codex | 2 | 12 | 0.2 | 2.5 | 1,000,000 | 128,000 |
| gpt-5.6-terra | openai | 2 | 12 | 0.2 | 2.5 | 1,050,000 | 128,000 |
| gpt-5.6-terra | azure | 2 | 12 | 0.2 | 2.5 | 1,050,000 | 128,000 |
| gpt-5.6-terra | github-copilot | 2 | 12 | 0.2 | 2.5 | 1,050,000 | 128,000 |
| gpt-5.6-luna | openai-codex | 0.2 | 1.2 | 0.02 | 0.25 | 1,000,000 | 128,000 |
| gpt-5.6-luna | openai | 0.2 | 1.2 | 0.02 | 0.25 | 1,050,000 | 128,000 |
| gpt-5.6-luna | azure | 0.2 | 1.2 | 0.02 | 0.25 | 1,050,000 | 128,000 |
| gpt-5.6-luna | github-copilot | 0.2 | 1.2 | 0.02 | 0.25 | 1,050,000 | 128,000 |
| gpt-6-astra | openai-codex | 0 | 0 | 0 | 0 | 272,000 | 128,000 |
| gpt-6-astra-pro | kilo (`openai/gpt-6-astra-pro`) | 10 | 50 | 1 | 12.5 | 1,050,000 | 128,000 |
| gpt-6-astra | kilo (`openai/gpt-6-astra`) | 0 | 0 | 0 | 0 | null | null |
| gpt-6-astra | venice (`openai-gpt-6-astra`) | 0 | 0 | 0 | 0 | null | null |

경로별 단가 차이는 셋입니다. `venice`가 Claude 두 모델을 정확히 1.2배로 재판매하고, `github-copilot`이 `gpt-5.6-sol`을 0.5배(2/10/0.2/2.5)로 계상하며, `azure`가 `gpt-5.6-sol`의 캐시 단가만 anthropic식 0.5/6.25로 올려 잡습니다. 그 외 경로는 1차 단가와 같습니다.

표의 `contextWindow`는 카탈로그 원값입니다. 실행 시점에는 `extendedContext=false`(현재 값) 때문에 `cost.longContext.inputThreshold`가 있는 모델의 창이 그 임계값으로 잘리므로, `gpt-5.6-*`의 openai-codex·openai 경로 실효 창은 **272,000**입니다. `azure`·`github-copilot`은 임계값이 없어 잘리지 않고, anthropic·venice·google-vertex의 Claude도 임계값이 없어 1M 그대로입니다(§4의 `extendedContext` 행, §6 3·6항).

### 3-2. 장문 구간·서비스 티어·원격 압축·사고 모드

| 모델 | 공급자 경로 | longContext 임계 | 장문 in/out/read/write | serviceTierCost | remoteCompaction | thinking.mode / efforts |
| --- | --- | ---: | --- | --- | --- | --- |
| claude-opus-5 | anthropic, google-vertex, github-copilot, venice | 없음 | — | null | null | anthropic-adaptive (venice: effort) / low·medium·high·xhigh·max (venice: minimal~xhigh) |
| claude-sonnet-5 | 위와 같음 | 없음 | — | null | null | 위와 같음 |
| gpt-5.6-sol | openai-codex | 272,000 | 10 / 45 / 1 / 12.5 | flex 0.5, priority 2 | enabled, `openai-codex-responses`, v2 스트리밍 | effort / low·medium·high·xhigh·max |
| gpt-5.6-sol | openai | 272,000 | 10 / 45 / 1 / 12.5 | null | null | effort / 위와 같음 |
| gpt-5.6-sol | azure, github-copilot | 없음 | — | null | null | effort / 위와 같음 |
| gpt-5.6-terra | openai-codex | 272,000 | 4 / 18 / 0.4 / 5 | flex 0.5, priority 2 | enabled | effort / 위와 같음 |
| gpt-5.6-terra | openai | 272,000 | 4 / 18 / 0.4 / 5 | null | null | effort / 위와 같음 |
| gpt-5.6-terra | azure, github-copilot | 없음 | — | null | null | effort / 위와 같음 |
| gpt-5.6-luna | openai-codex | 272,000 | 0.4 / 1.8 / 0.04 / 0.5 | flex 0.5, priority 2 | enabled | effort / 위와 같음 |
| gpt-5.6-luna | openai | 272,000 | 0.4 / 1.8 / 0.04 / 0.5 | null | null | effort / 위와 같음 |
| gpt-5.6-luna | azure, github-copilot | 없음 | — | null | null | effort / 위와 같음 |
| gpt-6-astra | openai-codex | 없음 | — | flex 0.5, priority 2 | enabled, `openai-codex-responses`, v2 스트리밍 | effort / low·medium·high·xhigh·max |
| gpt-6-astra-pro | kilo (`openai/gpt-6-astra-pro`) | 없음 | — | null | null | effort / low·medium·high·xhigh·max |
| gpt-6-astra | kilo, venice | 없음 | — | null | null | null / null |

`gpt-5.6-terra`는 `docs/FACTS.md` §6의 외부 벤치마크 표에 측정값이 없어 후보에서 제외된 모델이지만, 경로별 단가 비교를 위해 남겼습니다.

## 4. OMP 비용 손잡이

이 절의 설정과 비용 설명은 2026-09-05 조사 시점의 기록입니다. 현재 권장값은 [사용법](guides/usage.md#내장-자동-압축)과 `omp/config.apply.sh`가 정하며, 이 표를 설정 복원 템플릿으로 사용하지 않습니다.

| 키 | 2026-09-05 관측값 | 하는 일 | 비용에 닿는 경로 | 근거 |
| --- | --- | --- | --- | --- |
| `providers.cacheRetention` | `auto` | 프롬프트 캐시 보존을 공급자에 전달. `auto`=공급자 기본(Anthropic 5분 + 유휴 keep-alive 갱신)이며 `PI_CACHE_RETENTION` 존중, `short`=5분 고정, `long`=지원 모델에 1시간 TTL·keep-alive 갱신 해제, `none`=캐싱과 캐시 친화 라우팅 해제 | `long`은 쓰기 배수를 1.25배→2배로 올리고 유휴 5~60분 복귀의 재구축만 구제. `none`은 모든 입력을 정가로 되돌림 | `omp://settings.md` L754, `omp://provider-quirks.md` L159 (`applyPromptCaching`이 마지막 두 턴에 `cache_control` 부착, `ttl:"1h"`는 long에서만) |
| `provider.appendOnlyContext` | `auto` | 컨텍스트를 추가 전용으로 유지하는 모드 스위치(`auto`/`on`/`off`) | 프리픽스를 덮어쓰지 않으면 KV/프롬프트 캐시 적중이 유지되어 캐시 쓰기가 줄어듦 [추정] | `omp://settings.md` L755(값만 열거), `omp://provider-quirks.md` L1035 (`config/append-only-context-mode.ts`, 로컬 추론 공급자에서 `<think>` 보존으로 KV 캐시 적중) |
| `contextPromotion.enabled` | `false` | 컨텍스트 오버플로 때 모델의 `contextPromotionTarget`으로 승격 | 승격 대상 모델의 단가로 갈아타므로 요청 단가가 바뀜. 지금은 꺼져 있어 오버플로가 compaction으로 처리됨 | `omp://settings.md` L634 |
| `extendedContext` | `false` | 프리미엄 장문 구간 사용 여부. **꺼져 있으면 `cost.longContext.inputThreshold`가 있는 모델의 `contextWindow`를 그 임계값으로 낮춤**(sol·terra·luna의 openai-codex·openai 경로 → 272,000). `xai-oauth`와 명시적 `contextWindow` 재정의는 예외 | 꺼진 상태에서는 압축이 장문 구간 진입 전에 발동하므로 openai 계열 요청에 입력 2배·출력 1.5배가 붙지 않음. 켜면 창이 1M로 돌아가 272K 초과 요청부터 프리미엄이 붙음 | `pi-coding-agent/src/config/model-registry.ts` L2127-2143(`#applyHardcodedModelPolicies`), `src/config/settings-schema.ts` L2505-2517 |
| `compaction.thresholdTokens` | `300000` | 고정 토큰 트리거. 0보다 크면 이 값에서 압축 | `extendedContext=false`이면 openai 계열 창이 272,000으로 낮아지므로 300K 트리거는 도달하지 않고 예비량 기반 오버플로 경로가 먼저 발동함. anthropic 경로(창 1M, 장문 프리미엄 없음)에서만 실제 트리거로 작동 | `omp://settings.md` L640, `omp://compaction.md` L426-446, `model-registry.ts` L2138-2142 |
| `compaction.thresholdPercent` | `-1` | 컨텍스트 비율 트리거. `-1`은 예비량 기반 기본 동작 | 비율 기준으로 바꾸면 모델 창 크기에 따라 압축 시점이 달라지고 캐시 프리픽스 재구축 횟수도 달라짐 | `omp://settings.md` L639 |
| `compaction.keepRecentTokens` | `40000` | 압축 후에도 항상 보존하는 최근 토큰(스키마 기본 20000) | 보존량이 크면 압축 직후 캐시 쓰기 크기가 커지고, 작으면 재질의로 입력이 늘어남. 측정된 사용 비율에 따라 적응 조정됨 | `omp://settings.md` L642, `omp://compaction.md` L191·L429 |
| `compaction.methodOrder` | `["shake","snapcompact","handoff","soft"]` | 압축 방법 우선순위. 실패·미지원 시 다음으로 넘어감 | `remote`가 빠져 있어 provider-native 서버 압축을 쓰지 않고, `handoff`·`soft`는 요약을 위해 LLM 요청을 한 번 더 씀 | `omp://settings.md` L638, `omp://compaction.md` L426 |
| `compaction.idleEnabled` | `false` | 유휴 상태에서 선제 압축(`idleThresholdTokens` 200000, `idleTimeoutSeconds` 300) | 켜면 유휴 뒤 첫 요청 전에 컨텍스트를 줄여 재구축 크기를 낮춤. 현재 `methodOrder`의 앞 두 방법은 모델 요청이 없으므로(shake는 로컬 축약, snapcompact는 "No model, API key, or network is involved") 추가 LLM 비용은 `handoff`·`soft`까지 내려갈 때만 발생함 | `omp://compaction.md` L440-441, L138, L150 |
| `compaction.supersedeReads` | `true` | 같은 파일을 다시 읽으면 이전 읽기 결과를 대체·축약 | 캐시 안전 타이밍(뒤 접미사가 ~8k 이하이거나 캐시 수명이 지난 뒤)에만 적용하여 프리픽스 무효화를 피하면서 입력을 줄임 | `omp://compaction.md` L441, L178 |
| `compaction.dropUseless` | `true` | 무의미한 도구 결과를 `[Uneventful result elided]`로 치환 | 같은 캐시 안전 타이밍 규칙을 쓰며, 표지보다 작은 결과와 보호 도구는 제외. 요약 직렬화에서는 쌍 전체를 제외해 캐시 비용이 들지 않음 | `omp://compaction.md` L178-180, L442 |
| `snapcompact.systemPrompt` | `none` | 시스템 프롬프트를 이미지 프레임으로 전송하는 임시 압축 범위(`none`/`agents-md`/`all`) | `all`은 시스템 프롬프트를 이미지 토큰으로 바꿔 텍스트 입력을 줄이지만 Anthropic의 시각 토큰 상한과 프리픽스 변경을 함께 건드림 | `omp://compaction.md` L443, L146 |
| `providers.openai-codex.codeMode` | `off` | Codex Code Mode. 직접 도구 표면을 `eval`/`ask`/`todo`로 접고 나머지는 `eval` 셀의 `tool.<name>()` 브리지로 호출 | 다단계 도구 작업을 모델 왕복 한 번으로 접어 요청 수와 누적 입력을 줄임 | `omp://settings.md` L483-484 |
| `providers.openaiWebsockets` | `auto` | OpenAI 계열 WebSocket 전송(`auto`/`off`/`on`) | 전송 방식만 바꾸므로 토큰 단가에는 닿지 않고 지연·재시도에 영향 [추정] | `omp://settings.md` L751(값만), Codex WS 상수는 `omp://provider-quirks.md` OpenAI Codex 절 |
| `providers.fireworksTier` | `standard` | Fireworks 요청에 `service_tier: "priority"` 전송 여부(`/fast` 모드 포함) | Fireworks 경로를 쓸 때만 티어 프리미엄이 붙음. 후보 모델은 Fireworks 경로를 쓰지 않으므로 현재 비용 영향 없음 | `omp://provider-quirks.md` L791 |
| 사고 강도 접미사 `:low`~`:max` | 역할별 지정(`default` `:high`, `slow`/`mid` `:max`/`:xhigh`, `smol` `:max`, `tiny`/`commit` `:low`) | 역할 셀렉터의 접미사가 에이전트 프론트매터의 `thinking-level`을 덮어씀 | 사고 토큰은 출력 토큰으로 과금되며 Anthropic 1M 모델에서는 이전 턴 사고 블록이 컨텍스트에 남아 다음 요청의 입력으로도 과금됨 | `omp://models.md` L428, `docs/FACTS.md` §5, https://platform.claude.com/docs/en/build-with-claude/context-windows |
| `defaultThinkingLevel` / `thinkingBudgets.*` | `high` / minimal 1024·low 2048·medium 8192·high 16384·xhigh 32768·max 32768 | 기본 강도와 강도별 토큰 예산. `--thinking`으로 실행 단위 덮어쓰기 | budget 방식 모델에서 예산이 곧 출력 토큰 상한이므로 강도가 출력 비용을 직접 결정. `xhigh`와 `max`가 같은 32768이므로 이 두 변형은 budget 모델에서 구분되지 않음 | `omp://settings.md` L402-409 |
| `thinking.mode`(카탈로그) | Claude=`anthropic-adaptive`, GPT-5.6=`effort` | 강도를 전달하는 형식. adaptive는 `{type:"adaptive"}`+`output_config.effort`, effort는 `reasoning_effort` | adaptive 모델은 예산이 아니라 모델이 사고량을 정하므로 요청마다 출력 토큰이 흔들림. effort 변경은 Anthropic·OpenAI 양쪽에서 캐시 프리픽스를 무효화함 | `models.db` `thinking.mode`, `omp://provider-quirks.md` L158, https://platform.claude.com/docs/en/build-with-claude/prompt-caching |
| `tier.openai` / `tier.anthropic` / `tier.google` | 모두 `none` | `service_tier` 전송 여부와 값 | `tier.openai: flex`는 0.5배, `priority`는 2배. `tier.anthropic: priority`는 직접 Claude 경로에서 fast mode를 실현하여 Opus 5를 $10/$50로 만듦(Bedrock·Vertex·OpenRouter에서는 무시) | `omp://settings.md` L425-427, https://developers.openai.com/api/docs/pricing, https://platform.claude.com/docs/en/about-claude/pricing |

## 5. 벤치마크가 다뤄야 할 비용 축

**변형 A: `providers.cacheRetention` (`auto` 대 `long` 대 `none`).** 바꾸는 값은 cache write 배수(1.25배↔2배)와 TTL(5분↔1시간)이며, `none`은 cache 자체를 끕니다. 공개 가능한 개인 관측에서는 `long`이 이익이 되려면 비싼 write를 유휴 복귀의 재사용으로 회수해야 했습니다. 짧은 benchmark session에서는 유휴 5분 초과가 드물 수 있으므로, `long`을 자동 절감으로 가정하지 않고 `auto`와 함께 실제 write/read와 재사용 간격을 측정합니다.

**변형 B: 사고 강도 (`:low`/`:medium`/`:high`/`:xhigh`/`:max`).** 바꾸는 값은 output/reasoning token 양이며, Anthropic 1M model에서는 남은 thinking block이 다음 요청의 input에도 계상됩니다. Effort가 높을수록 비용과 품질이 모두 단조롭게 변한다고 가정하지 말고 각 task에서 Pareto 전선을 측정합니다. `thinkingBudgets`의 `xhigh`와 `max`가 같은 32768인 budget 방식 model에서는 둘을 별도 변형으로 세지 않습니다.

**변형 C: 공급자 경로 (같은 모델, 다른 `provider/`).** 바꾸는 값은 카탈로그 단가입니다. `claude-opus-5`는 anthropic 5/25 대 venice 6/30(1.2배), `gpt-5.6-sol`은 openai 4/20 대 github-copilot 2/10(0.5배), azure는 캐시 단가만 0.5/6.25로 다릅니다. 경로가 단가만 바꾸는 것은 아닙니다. 같은 §3 표에서 `github-copilot`의 `claude-opus-5`는 `maxTokens`가 64,000(다른 경로는 128,000)이고, `venice`는 사고 모드가 `effort`이며 effort 집합이 `minimal`~`xhigh`로 `max`가 없습니다. 따라서 이 변형은 `Catalog est/task`만 비교해서는 안 되고 합격률을 함께 측정해야 하며, 합격률 차이가 나오면 정산 경로 차이가 아니라 출력 상한·사고 강도 해석이 만든 **능력 차이**로 해석해야 합니다. 구독 경로(openai-codex, anthropic OAuth)의 비용은 명목값이라 현금 비교로 쓸 수 없습니다.

**변형 D: `extendedContext` (`false`/`true`) — 장문 구간 허용 여부.** 바꾸는 값은 openai 계열 모델의 실효 컨텍스트 창입니다. `extendedContext=false`(현재 값이자 기본값)이면 `#applyHardcodedModelPolicies`가 `cost.longContext.inputThreshold`를 가진 모델의 창을 그 임계값으로 낮추므로 sol·luna의 openai-codex·openai 경로 창은 272,000이 되고, 스키마 주석대로 "compaction kicks in before any request crosses into premium billing"입니다. 즉 지금 설정으로는 openai 후보가 입력 2배·출력 1.5배 구간에 들어갈 수 없고, `compaction.thresholdTokens`를 낮추는 변형은 이 축에서 아무것도 바꾸지 않습니다. `true` 변형은 창을 1M로 되돌려 "프리미엄 요금을 내고 압축을 미루는 쪽"과 "272K에서 압축하는 쪽"을 비교하며, 함께 볼 지표는 장문 구간 요청 수·압축 횟수·합격률입니다. anthropic 경로는 장문 프리미엄이 없어 임계값이 없으므로 이 변형에 영향을 받지 않습니다. 실측(`docs/FACTS.md` §4, p90 466K·최대 622K)은 anthropic 요청이 대부분인 표본이므로 openai 쪽 창 축소의 영향은 그 분포에서 직접 읽을 수 없습니다.

**변형 E: 서비스 티어 (`tier.openai` `none`/`flex`/`priority`).** 바꾸는 값은 단가 배수 0.5배와 2배이며, `flex`는 `429 Resource Unavailable`로 실패할 수 있고 그때는 과금되지 않습니다. 벤치 과제는 지연에 민감하지 않으므로 `flex`가 합격률을 떨어뜨리지 않고 비용만 반으로 줄이는지 확인할 가치가 있고, 실패율과 평균 시간을 함께 기록해야 판단이 됩니다. 카탈로그의 `serviceTierCost`가 openai-codex 경로에만 있으므로 `openai` 경로에서는 이 배수가 명목 비용에 반영되지 않습니다(§6).

**변형 F: `providers.openai-codex.codeMode` (`off`/`on`).** 바꾸는 값은 도구 표면과 모델 왕복 횟수입니다. 다단계 도구 작업이 `eval` 한 셀로 접히면 요청 수와 누적 입력이 줄어드는 대신 도구 오류의 재시도 비용이 커질 수 있습니다. `bench/README.md`가 이미 요청 수와 도구 호출 수를 저장하므로 추가 계측 없이 측정됩니다.

**실행마다 기록해야 할 지표.** (1) cache hit 비율 = `cacheRead / (input + cacheRead + cacheWrite)`, (2) 272,000 input token을 넘는 long-context 요청 수, (3) 큰 cache rewrite 건수, (4) session 최대·p90 context, (5) 적용된 service tier와 `providers.cacheRetention`·`extendedContext` 값입니다. 이 값이 있어야 `Catalog est/task`와 session-recorded `Actual/task`의 차이를 설명할 수 있습니다. 실제 effort는 runner가 지원하는 경로에서 `actual_thinking`으로 저장하며, 값을 관측할 수 없는 경로는 `n/a`로 남깁니다.

## 6. 실측·카탈로그·문서의 불일치와 미확인 항목

1. **`gpt-5.6-sol` 장문 단가가 카탈로그와 공식 문서에서 다릅니다.** 카탈로그 `cost.longContext`는 10/45/1/12.5인데 공식 값은 입력 2배·출력 1.5배 규칙에 따라 8/30/0.8/10입니다. 카탈로그 값은 `gpt-5.5`의 장문 단가(입력 $10, 캐시 $1, 출력 $45)와 일치하므로 이전 세대 값을 물려받은 것으로 보입니다. terra와 luna의 장문 값은 공식과 일치합니다. 다만 이 값이 실제로 쓰이는 것은 `extendedContext=true`일 때뿐입니다. 기본값 `false`에서는 창이 272,000으로 잘려 장문 구간 요청이 발생하지 않으므로 이 오류가 `Catalog est/task`에 나타나지 않고, 장문 변형을 켜는 순간 sol이 과대계상됩니다.
2. **`openai-codex` 경로의 컨텍스트 창이 공식 값과 다릅니다.** 카탈로그는 1,000,000, 공식 `gpt-5.6-sol` 문서는 1,050,000(입력 상한 922,000)입니다. `openai`·`azure`·`github-copilot` 경로는 1,050,000으로 맞습니다.
3. **`azure`·`github-copilot` 경로에는 `cost.longContext`가 없습니다.** 그래서 이 경로는 `extendedContext=false`에서도 창이 잘리지 않아(`inputThreshold`가 없으므로 `#applyHardcodedModelPolicies`의 상한 적용 조건에 걸리지 않음) 1,050,000 창을 그대로 쓰고, 272K를 넘는 요청도 기본 단가로 계산되며 장문 프리미엄만 반영되지 않습니다. 공식 OpenAI 문서의 272K 규칙이 게이트웨이 정산에도 적용되는지는 확인하지 못했습니다 [추정]. 결과적으로 openai 계열의 실효 창이 경로마다 다릅니다(openai-codex·openai 272,000 대 azure·github-copilot 1,050,000).
4. **openai-codex 관측에서 cache write가 0으로 보고될 수 있습니다.** `gpt-5.6-sol`과 `gpt-5.6-luna`의 개인 표본에서는 cache write token과 비용이 0이고 해당 token이 input으로 계상되었습니다. 카탈로그와 공식 문서에는 write 가격이 있으므로, provider-reported usage가 가격표의 모든 분류를 그대로 노출한다고 가정하지 않습니다.
5. **1시간 TTL write 배수는 공식 가격 문서에서 2배입니다.** 따라서 `long`의 break-even은 실제 유휴 복귀 재사용량에 달려 있습니다. 짧은 session에 대한 `auto` 유지 결론은 유효하지만, 다른 workload에는 자체 측정이 필요합니다.
6. **Anthropic에는 조사한 Claude 4.6 이상 1M window의 long-context premium이 없습니다.** 카탈로그에도 `longContext`가 없어 `extendedContext` 상한 적용 대상이 아닙니다. 반대로 premium threshold metadata가 있는 OpenAI 경로는 같은 설정에서 effective window가 먼저 줄 수 있으므로, 긴 task에서 provider별 compaction 횟수가 달라질 수 있습니다.
7. **`tier.anthropic: priority`의 배수가 명목 비용에 반영되지 않습니다.** 문서상 이 값은 fast mode를 실현하고 공식 단가는 Opus 5 입력 $10·출력 $50(각 2배)인데, 카탈로그의 anthropic 항목에는 `serviceTierCost`가 `null`입니다. 이 변형을 벤치에 넣으면 실제 명목 비용이 절반으로 과소계상됩니다.
8. **높은 cache hit 비율과 큰 rewrite는 함께 존재할 수 있습니다.** 공식 문서의 lookback window는 20 block이고 OMP는 최근 turn에 breakpoint를 붙입니다. 유휴 TTL뿐 아니라 한 turn의 block 수와 prefix 변경도 rewrite를 만들 수 있으므로 hit 비율만으로 원인을 확정하지 않습니다.
9. **Google 명시 캐시 API는 미확인입니다.** 캐싱 문서(2026-09-02 갱신)는 암묵 캐시만 설명하는데, 가격표에는 여전히 컨텍스트 캐시 토큰 단가와 시간당 저장 요금($0.50/1M토큰·시간)이 있습니다. 명시 캐시를 만드는 엔드포인트와 TTL 지정 방법을 문서에서 찾지 못했습니다.
10. **문서에 설명이 없는 OMP 키.** `extendedContext`는 `omp://settings.md`가 ungrouped 키 목록에 이름만 열거해 동작을 알 수 없었고, 설치된 소스(`pi-coding-agent/src/config/model-registry.ts` L2127-2143, `src/config/settings-schema.ts` L2505-2517)에서 확인해 §4·§5에 반영했습니다. `provider.appendOnlyContext`와 `providers.openaiWebsockets`는 여전히 허용값만 적혀 있어 §4에서 [추정]으로 표시했습니다.
11. **열지 못한 주소.** `https://support.claude.com/en/articles/11014257-about-claude-s-usage-limits`는 404였고, Anthropic의 5시간·주간 창은 Max 플랜 문서로 대체 확인했습니다. Antigravity의 5시간·주간 버킷은 정성 서술만 있고 구체적 수치가 공개되어 있지 않습니다(문서상 "capacity에 따라 조정" 명시). Google Vertex·Bedrock의 Claude 재판매 단가는 각 클라우드 가격 페이지로 넘겨져 있어 확인하지 않았습니다.
12. **`gpt-6-astra`의 구독 경로 카탈로그 단가는 0이고 공개 API 단가는 별도로 확인되었습니다.** 2026-09-05 추가 조사에서 `openai-codex/gpt-6-astra`는 0/0/0/0, 컨텍스트 272,000, 출력 상한 128,000입니다. 0은 구독 경로의 카탈로그 값이지 무료 API나 구독 한도 무소진을 뜻하지 않습니다. 공식 가격표(https://developers.openai.com/api/docs/pricing)는 Standard 단문 10/50/1/12.5, 장문 20/75/2/25(input/output/cacheRead/cacheWrite)를 명시합니다. `kilo/openai/gpt-6-astra-pro`는 단문과 같은 10/50/1/12.5에 창 1,050,000이지만, 이름이 다른 `-pro` 경로이므로 같은 모델이라는 보장은 확인하지 못했습니다. 조사한 Astra 네 항목 모두 `cost.longContext`가 없어 공식 장문 단가는 카탈로그에 반영되지 않습니다. `kilo/openai/gpt-6-astra`와 `venice/openai-gpt-6-astra`는 원값이 단가 0/0/0/0, `contextWindow`·`maxTokens`·`thinking`은 null이므로 유효한 가격·모델 사양은 미확인입니다.
