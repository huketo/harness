# 설계 근거

기준일 2026-09-03. 근거로 세는 자료는 기준일로부터 3개월 안(2026-06-03 이후)에 발행되거나 갱신된 1차 자료로 제한한다. 이 스킬을 고칠 때도 같은 창을 적용한다. 3개월이 지난 항목은 근거에서 빼고, 같은 주장을 담은 새 자료로 바꾸거나 규칙을 지운다. 스킬 실행에는 이 파일이 필요하지 않다.

## 분해와 격리

- Anthropic, Patterns and problems in emerging multiagent systems (2026-08-13). 같은 모델·같은 컨텍스트의 에이전트는 같은 결정을 한다(30명 중 18명이 같은 브랜치 이름). 파일 소유권이 높을수록 PR 병합률이 높다. 합의는 이미 공유된 지식으로 수렴하고 한 명만 아는 결정적 사실은 눌린다("consensus is not necessarily evidence"). 슬라이스 소유권, 독립 1회차, 근거 무게 판정, 소수 의견 보존의 근거. https://www.anthropic.com/research/multiagent-systems
- Claude Code, Orchestrate teams of Claude Code sessions (문서, 2026-09-03 확인). 팀원은 리드의 대화를 상속하지 않고 스폰 프롬프트가 전부. 3~5명에서 시작. 같은 파일을 두 명이 고치면 덮어쓴다. 리드가 기다리지 않고 직접 구현하는 실패. 경쟁 가설은 "서로 반증하게" 하여 앵커링을 막는다. https://code.claude.com/docs/en/agent-teams
- Shopify, Building an agentic harness that outlasts the model (2026-07-29). Hunter는 파티션별 병렬, Verifier는 다른 모델로 순차 실행(포트·DB·픽스처 충돌 회피). 테스트가 오라클. 더 좋은 모델은 더 자신감 있는 노이즈도 더 낸다. 파티션은 컨텍스트 창의 20~30%. 리뷰어를 다른 계열에 두고, 슬라이스 검증은 격리된 페인에서, 전체 스위트는 통합에서 한 번만 도는 규칙의 근거. https://shopify.engineering/building-an-agentic-harness-that-outlasts-the-model
- Cursor, How we set up our cloud agent environment (2026-07-30). 에이전트가 빌드·테스트를 스스로 돌릴 수 있는 환경이 성과를 갈랐다(클라우드 에이전트 PR 비율 10%→50% 이상). 실패한 실행의 트레이스를 읽어 스킬과 환경을 고치는 루프(Cloud Doctor). 수용 기준에 실행 명령을 붙이는 규칙과 skill-doctor 검수 단계의 근거. https://cursor.com/blog/cloud-agent-environment
- Uber, Running a Software Factory Efficiently at Uber Scale (2026-08). PR 70% 이상이 에이전트 기여. 워크로드별 Pareto 효율 모델 선택(uReview는 실제 버그 PR 벤치마크로 F1·비용 측정). 성과 단위 비용(병합 PR당, 리뷰당)과 revert rate로 품질 추적. 근거를 앞에 주면 탐색 비용이 줄고, 근거 없는 에이전트는 "천천히 실패한다". 역할별 실행기 선택과 run.md 예산 기록의 근거. https://www.uber.com/blog/efficient-software-factory/

## 리뷰와 합의

- Qiu & Gill, Adversarial Review: Structured Disagreement for Grounded Agentic Code Review (arXiv 2026-08-16). 코딩 에이전트 + 리뷰어 + 리뷰를 감사하는 비평가 셋이 다섯 에이전트 팀을 이겼다. 순진한 버전은 근거 없이 합의하는 false-consensus 실패를 보였고, "불일치를 명시적으로 요구"하는 프롬프트 한 줄이 최고 F1을 냈다. 쿼럼의 반박 회차, "내 입장의 약점" 항목, 근거 없는 만장일치를 결정으로 인정하지 않는 규칙의 근거. https://arxiv.org/abs/2608.18167
- Baltes, Cheong, Treude, "An Endless Stream of AI Slop" (arXiv 2026-03-28; 3개월 창 밖이지만 slop 판정의 유일한 실증 연구라 예외로 남기며, 대체 자료가 나오면 교체). 1,154개 개발자 게시글에서 Review Friction(리뷰 부담·신뢰 침식), Quality Degradation(코드베이스·지식·역량 훼손)을 코드화. slop 비용이 리뷰어에게 외부화되는 공유지의 비극 프레임. review.md의 C절이 리뷰어 부담을 기준으로 항목을 고른 근거. https://arxiv.org/abs/2603.27249

## 이 기계의 실측(2026-09-03)

- omp는 Herdr 확장이 생명주기를 직접 보고(`screen_detection_skipped: true`), agy는 화면 감지. agy `agent prompt`는 여러 줄이면 `agent_prompt_stalled`.
- 이 기계의 계열: omp 기본(anthropic), `omp --model sol`(openai), agy(gemini, `herdr integration status`에서 `antigravity-cli: current (v2)`). 스킬 본문은 이 대응을 적지 않고 `omp models`·`herdr integration status`로 확인하게 한다.
- 타이밍: omp `agent start` 3.1초, 파일 브리프 한 줄 프롬프트 13.5초에 `done`. agy `agent start` 4.8초, 조사 프롬프트 447초에 `done`(정확). 워크트리 경로는 `~/.herdr/worktrees/<repo>/<브랜치 슬래시→하이픈>`이었으나 응답의 `checkout_path`가 정본.
- Anthropic 제공자 장애(`overloaded_error`) 중 omp 세션 둘이 회복 불가 상태에 빠졌고 새 세션으로만 복구됐다. 같은 시간 `--model sol` 세션은 정상.
- 쿼럼 스모크(state-dir 결정): 목소리 셋이 1회차에 같은 선택지를 골랐지만, 2회차 반박에서 근거 인용 오류 3건(앵커 없는 URL, 제약 조건을 규격에 귀속, tmpfs 전제)이 걸러졌다. 반박 회차가 없었으면 오류 근거가 결정 기록에 남았을 것이다.
- agy print 모드 조사 보고 두 건은 참고 문헌을 도메인 수준으로만 적었다. 스카우트 브리프의 "정확한 URL, 못 찾으면 미확인" 요구의 근거.
