# 공급자 과금·프롬프트 캐시·컨텍스트 (2026-09-05 조사)

## 1. 조사 기준과 값의 의미

조사 기준일은 2026-09-05입니다. 이 문서는 Claude Code, Codex, agy가 쓰는 공급자의 과금·프롬프트 캐시·컨텍스트 규칙과 구독 한도의 의미를 기록합니다. 3절은 그 뒤에 발표된 모델의 공급사 단가를 덧붙입니다.

출처 원칙은 두 가지입니다. 첫째, 공급자 값은 실제로 열어 본 공식 문서만 "확인"으로 적고, 열지 못한 것은 "미확인"으로 적으며 추측 URL을 만들지 않았습니다. 둘째, 공식 문서끼리 다르거나 확인하지 못한 값은 4절에 모았습니다. 2차 기사·요약은 근거로 쓰지 않았습니다.

명목 비용과 청구액의 관계는 이렇습니다. OAuth 구독 계정 경로에서 세션 기록이나 도구가 단가로 환산해 보여 주는 비용은 **명목 비용**이고 현금 청구액이 아닙니다. 실제 제약은 5시간·주간 한도의 소진율일 수 있습니다(2절의 구독 한도 행).

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
| OpenAI | gpt-6-astra 단가 | 단문 input $10 / output $50 / 캐시읽기 $1 / 캐시쓰기 $12.50, 장문 $20 / $75 / $2 / $25 (per MTok) | Standard 기준 | https://developers.openai.com/api/docs/pricing | 확인 |
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
| Google | Gemini 3.8 Flash 컨텍스트 창 | **입력 토큰 상한 1,048,576 / 출력 토큰 상한 65,536** | agy의 `gemini-3.8-flash-*`가 쓰는 모델. thinking은 low·medium·high만 지원하고 `minimal`은 오류 | https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash | 확인 |
| Google | Gemini 3.8 Flash 소비 옵션 | Batch·Flex·Priority 추론 모두 지원, 캐싱 지원 | 2026년 9월 갱신판 모델 페이지 기준 | https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash | 확인 |
| Google | Gemini 티어 | Batch·Flex 0.5배, Priority 1.8배 (3.8 Flash 기준 $1.35/$6.75) | Flex·Batch는 무료 티어 없음 | https://ai.google.dev/gemini-api/docs/pricing | 확인 |
| Google | Antigravity 요금제 | AI Ultra: 최대 할당량 **5시간마다 갱신** + 최고 주간 한도 + 서드파티 모델. AI Pro: **주간 한도에 닿기 전까지 5시간마다 갱신**. 무료: **주간 갱신만** | 한도는 프롬프트 수가 아니라 에이전트가 한 작업량에 비례함 | https://antigravity.google/docs/plans | 확인 |
| Google | Antigravity 초과분 | AI Pro·Ultra는 구매한 AI 크레딧으로 초과 사용 가능(표준 소비 단가) | `AI Credit Overages` 설정 `Never`/`Always`. BYO 키·엔드포인트 미지원 | https://antigravity.google/docs/plans | 확인 |

## 3. 2026-09-23 이후 발표된 모델의 공급사 단가

각 값은 해당 조사일에 공급사 발표문이나 모델 문서에서 읽은 값입니다. 단위는 100만 토큰당 USD이며, 구독 계정에서는 명목 비용입니다.

| 모델 | 조사일 | input | output | 캐시 읽기 | 조건 | 출처 |
| --- | --- | ---: | ---: | ---: | --- | --- |
| claude-opus-5-5 | 2026-09-23 | 4 | 20 | 0.20 | fast mode $8/$40 | [Opus 5.5 발표](https://www.anthropic.com/claude-opus-5-5) |
| gpt-6-sol | 2026-09-23 | 2 | 10 | — | GPT-5.6 Sol의 절반 | [Sol·Luna 발표](https://openai.com/index/introducing-gpt-6-sol-and-luna/) |
| gpt-6-luna | 2026-09-23 | 0.10 | 0.50 | — | — | 같은 발표 |
| claude-sonnet-5-5 | 2026-09-29 | 2 | 10 | 0.20 | 캐시·배치를 포함한 모든 단가가 Sonnet 5와 같습니다. 1시간 캐시 쓰기는 $4, 최소 캐시 프롬프트는 512 토큰(Sonnet 5는 1,024)입니다. | [Sonnet 5.5 안내](https://claude.dev/blog/building-with-claude-sonnet-5-5/) |
| gpt-6.1-sol | 2026-09-30 | 2 | 10 | 0.10 | 캐시 입력만 GPT-6 Sol의 절반입니다. 272K 입력을 넘는 요청에는 입력·캐시 2배, 출력 1.5배를 적용합니다. 창은 1,050,000(최대 입력 922,000)이며 `none`·`minimal` effort를 지원하지 않습니다. | [GPT-6.1 Sol 발표](https://openai.com/index/introducing-gpt-6-1-sol/), [모델 페이지](https://developers.openai.com/api/docs/models/gpt-6.1-sol) |
| claude-haiku-5-5 | 2026-10-13 | 0.10 | 0.50 | 0.01 | 프롬프트 100,000 토큰 이하 기준이며 5분 캐시 쓰기 $0.125, 1시간 캐시 쓰기 $0.20입니다. 100,000 토큰을 넘으면 각각 5배($0.50·$2.50·$0.05, 쓰기 $0.625·$1)입니다. | [모델 개요](https://platform.claude.com/docs/en/models/haiku-5-5/overview), [Haiku 5.5 발표](https://www.anthropic.com/claude-haiku-5-5) |
| gemini-4-argon | 2026-10-22 | 2 | 10 | — | 소개 단가이며 캐시 입력은 입력 단가의 95% 할인입니다. 소개 기간 후 단가는 $4/$20이고 종료일은 발표문에 없습니다. 발표 시점에는 접근을 단계적으로 확대하는 중이었으므로 `agy/gemini-4-argon-high`의 사용 가능 여부는 각자의 CLI와 계정에서 확인합니다. API 가격과 AGY 구독 한도는 같은 비용 지표가 아닙니다. | [Gemini 4 Argon 발표](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-4-argon/) |

Codex 구독 한도에서는 [ChatGPT 요금 안내](https://learn.chatgpt.com/docs/pricing)의 5시간당 로컬 메시지가 GPT-6.1 Sol 15–160, GPT-6 Sol 15–150이고, 100만 토큰당 크레딧은 GPT-6.1 Sol이 입력 50·캐시 입력 2.5·출력 250, GPT-6 Sol이 50·5·250입니다(2026-09-30 조회). 따라서 공급사 표 기준으로는 Sol을 6.1로 바꿔도 Codex 한도 부담이 늘지 않습니다. 이 판단은 실측이 아닙니다.

Anthropic 구독 한도는 모델 공통이므로(2절) Sonnet 5.5나 Haiku 5.5가 Opus 5.5보다 한도를 얼마나 덜 쓰는지는 공급사 자료로 알 수 없습니다.

## 4. 문서 간 불일치와 미확인 항목

1. **Anthropic에는 장문 프리미엄이 없습니다.** 공식 문서는 Claude 4.6 이상에서 1M 창 전체가 표준 단가라고 명시합니다. 반면 OpenAI 계열은 272K 입력을 넘는 요청 전체에 입력 2배·출력 1.5배를 적용하므로, 두 공급자의 긴 컨텍스트 비용 구조가 다릅니다. 예외로 Claude Haiku 5.5는 100,000 토큰을 경계로 단가 구간이 있습니다(3절).
2. **Google 명시 캐시 API는 미확인입니다.** 캐싱 문서(2026-09-02 갱신)는 암묵 캐시만 설명하는데, 가격표에는 여전히 컨텍스트 캐시 토큰 단가와 시간당 저장 요금($0.50/1M토큰·시간)이 있습니다. 명시 캐시를 만드는 엔드포인트와 TTL 지정 방법을 문서에서 찾지 못했습니다.
3. **열지 못한 주소.** `https://support.claude.com/en/articles/11014257-about-claude-s-usage-limits`는 404였고, Anthropic의 5시간·주간 창은 Max 플랜 문서로 대체 확인했습니다. Antigravity의 5시간·주간 버킷은 정성 서술만 있고 구체적 수치가 공개되어 있지 않습니다(문서상 "capacity에 따라 조정" 명시). Google Vertex·Bedrock의 Claude 재판매 단가는 각 클라우드 가격 페이지로 넘겨져 있어 확인하지 않았습니다.
