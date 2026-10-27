# 주요 AI 모델·에이전트 벤치마크 조사와 이 레포 `bench/`에 대한 설계 시사점

조사 기준일은 2026-09-05입니다. 이 문서의 모든 항목은 1차 출처, 즉 논문(arXiv), 벤치마크 공식 사이트와 리더보드, 공식 GitHub 저장소, 발표 기관 블로그만 근거로 삼았고 2차 기사·요약은 근거로 쓰지 않았습니다. 표의 "확인" 표시는 조사 과정에서 그 URL을 실제로 열어 본문을 읽은 항목이며, "미확인"은 존재를 다른 1차 출처의 인용으로만 확인했고 원문을 열지 못한 항목입니다. 추측한 내용에는 `[추정]`을 붙였습니다. 리더보드 수치는 새로 실행하거나 예측하지 않고, 인용한 페이지가 그 페이지에 적어 둔 값과 날짜만 옮겼습니다.

## 1. 벤치마크 표

| 이름 | 발표 기관·연도·최신판 | 재는 것 | 과제 출처 | 채점 | 지표 | 비용·시간 보고 | 오염 대책 | 하네스 고정 | 정확한 URL | 확인 상태 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SWE-bench | Princeton 등, 2023-10 논문; 공식 리더보드는 Verified·Multimodal·Multilingual·Lite·Full 탭 운영 | 실제 GitHub 이슈를 해결하는 저장소 규모 코드 수정 | Python 12개 저장소의 해결된 이슈와 그 PR 2,294건 | PR에 포함된 단위 테스트(FAIL_TO_PASS/PASS_TO_PASS) 실행 | resolved % | 리더보드에 resolved vs cost 산점도, 누적 비용·스텝 분포 차트 제공 | 없음(정적 데이터셋) | 아니오 | https://www.swebench.com/ , https://arxiv.org/abs/2310.06770 | 확인 |
| SWE-bench Verified | OpenAI + SWE-bench 저자, 2024-08-13(2025-02-24 갱신) | 위와 같으나 과제 품질을 사람이 검증한 500건 부분집합 | 원본 테스트셋에서 사람 주석으로 선별 | 동일한 단위 테스트, Docker 평가 하네스 | resolved % | 없음(문서에는 사람 기준 난이도 시간 분포만) | 없음 | 아니오 | https://openai.com/index/introducing-swe-bench-verified/ | 확인 |
| SWE-bench Multimodal | Princeton·Meta 등, 2024-10 | 이미지가 포함된 JavaScript UI 소프트웨어의 버그 수정 | JS 라이브러리 17개에서 수집한 617건, 각 인스턴스에 이미지 1장 이상 | 단위 테스트 | resolved % | 없음 | 없음 | 아니오 | https://arxiv.org/abs/2410.03859 | 확인 |
| SWE-bench Pro | Scale AI, 페이지 표기 2025-09-19 | 다중 파일·장기 과제의 해결률 | 공개 731 + 보류 858 + 상용 276 = 1,865건, 저장소 41개. 커밋 스크래핑 후 전문가가 문제 서술·요구사항으로 증강 | fail-to-pass 신규 테스트 통과 + pass-to-pass 회귀 없음 | Resolve Rate | 리더보드 각주에 턴 상한(250), 과거 실행의 비용 상한 표기 | 공개·보류 세트는 강한 copyleft(GPL) 저장소, 상용 세트는 비공개 코드베이스 | 부분: 고정은 발표 실험의 SWE-Agent 스캐폴드와 턴 상한 250; 변수는 리더보드 행마다 다른 에이전트(mini-swe-agent)와 비용·턴 상한 | https://scale.com/blog/swe-bench-pro , https://labs.scale.com/leaderboard/swe_bench_pro_public | 확인 |
| SWE-bench-Live | Microsoft 등(RepoLaunch), 정기 갱신 | 최신 이슈에 대한 해결률, 다중 언어·다중 OS | 자동 큐레이션 파이프라인이 새 이슈를 계속 수집. lite·verified 스플릿은 고정, test 스플릿은 갱신 | 컨테이너에서 테스트 실행 | resolved % | 없음 | 정기 갱신으로 오염 회피. 제출 시 에이전트 궤적 제출을 요구해 문제 서술과 도커 이미지 외 정보 유출 여부를 검증 | 아니오 | https://swe-bench-live.github.io/ | 확인 |
| SWE-rebench | 논문 2025-05(초록에 소속 표기 없음, 저자는 Nebius 연구진 `[추정]`) | 상시 갱신되는 상호작용형 SWE 과제 | GitHub에서 자동 추출한 21,000건 이상 | 테스트 실행 | resolved %(신선 과제 대비 SWE-bench Verified 비교) | 없음 | 신선 과제 상시 공급으로 비오염 평가. 오염으로 점수가 부풀 수 있음을 실증 | 아니오 `[추정]`(초록에 에이전트 스캐폴드 고정 여부 기술 없음) | https://arxiv.org/abs/2505.20411 | 확인 |
| Terminal-Bench | Stanford·Laude Institute 등. 공식 사이트 기준 현재 4.0, 논문은 ICLR 2026 | 터미널에서 끝까지 수행하는 에이전트 능력 | 사람이 작성한 과제(지시문·테스트 스크립트·oracle 해답). 다른 벤치마크 어댑터도 보유 | 과제별 테스트 전부 통과 여부 | Resolution Rate | 리더보드가 COST와 TOKENS 열을 모델·에이전트별로 표시 | 저장소 CI에 canary 검사 워크플로(`check-canary.yml`) 존재 | 아니오 | https://www.tbench.ai/ , https://github.com/laude-institute/terminal-bench , https://github.com/harbor-framework/harbor | 확인 |
| Aider Polyglot | Aider 프로젝트, 2024-12 도입 | 지시를 따라 기존 파일을 편집하는 능력 | Exercism 연습문제 225건, C++·Go·Java·JavaScript·Python·Rust | 문제에 딸린 테스트 | Percent correct, Correct edit format | 리더보드에 실행 Cost(USD) 열과 실행 명령 표기 | 없음 | 부분: 고정은 aider 하네스와 행마다 공개되는 실행 명령; 변수는 편집 형식(diff·architect 등)·추론 강도·editor model | https://aider.chat/docs/leaderboards/ | 확인 |
| LiveCodeBench | UC Berkeley 등, 2024-03 | 경쟁 프로그래밍 문제로 본 코드 생성·자기수정·실행 예측 | LeetCode·AtCoder·Codeforces에서 시간순으로 계속 수집 | 테스트 케이스 실행 | pass@1 등 | 없음 | 문제 공개 시점 구간을 나눠 학습 이후 문제만 평가 | 부분: 고정은 공식 평가 코드와 문제 시점 구간; 변수는 프롬프트·샘플링 설정 | https://arxiv.org/abs/2403.07974 | 확인 |
| HumanEval·MBPP·EvalPlus | OpenAI 2021-07, Google 2021-08, EvalPlus 2023-05 | 함수 단위 프로그램 합성 | 사람이 작성한 합성 과제(MBPP 974건). EvalPlus는 HumanEval 테스트를 80배로 증강 | 단위 테스트 | pass@k | 없음 | 없음(EvalPlus는 테스트 불충분으로 인한 오판을 교정) | 부분: 고정은 테스트 스위트; 변수는 프롬프트·샘플 수·디코딩 설정 | https://arxiv.org/abs/2107.03374 , https://arxiv.org/abs/2108.07732 , https://arxiv.org/abs/2305.01210 | 확인 |
| BigCodeBench | BigCode 커뮤니티, 2024-06 | 여러 라이브러리 함수를 호출해 실무형 과제를 푸는 능력 | 139개 라이브러리·7개 도메인의 세분 과제 1,140건 | 과제당 평균 5.6개 테스트, 평균 분기 커버리지 99% | pass@1(사람 97% 기준선 병기) | 없음 | 없음 | 부분: 고정은 공식 평가 하네스와 테스트; 변수는 Complete·Instruct 프롬프트 변형과 디코딩 설정 | https://arxiv.org/abs/2406.15877 | 확인 |
| SWE-Lancer | OpenAI, 2025-02 | 프리랜스 소프트웨어 작업의 금전 가치 환산 성능 | Upwork 실제 발주 1,400건 이상, 총 100만 달러 | 독립 과제는 숙련 엔지니어가 3중 검증한 E2E 테스트, 관리자 과제는 실제 고용 매니저의 선택과 비교 | 획득 금액(USD), 통과율 | 과제 자체가 달러 가치로 표시됨 | 없음. 공개 스플릿(Diamond)과 비공개 스플릿 분리 | 부분: 고정은 통일 Docker 이미지와 채점 절차; 변수는 에이전트 하네스 | https://arxiv.org/abs/2502.12115 | 확인 |
| MLE-bench | OpenAI, 2024-10 | 데이터 준비·학습·실험을 포함한 ML 엔지니어링 | Kaggle 대회 75건 | 대회 채점 기준과 공개 리더보드 기반 사람 기준선(메달 등급) | 메달 획득 비율 | 자원 스케일링(시간·시도 수) 실험을 별도 보고 | 사전학습 오염 영향을 별도로 조사 | 부분: 고정은 `mlebench-env` 이미지와 24시간·자원 기본값 권고; 변수는 에이전트(리더보드가 Agent·LLM 열 분리, 에이전트 비가정 설계) | https://arxiv.org/abs/2410.07095 , https://github.com/openai/mle-bench | 확인 |
| SkillsBench | BenchFlow 등, 2026-02 논문 | 에이전트 스킬(절차 지식 패키지)이 실제로 성능을 올리는지 | 8개 도메인 87개 과제 + 큐레이트된 스킬 | 결정론적 verifier(`verifier/test.sh`), 에이전트 실행 전 oracle 해답이 먼저 통과해야 함 | 짝지은 조건별 pass rate와 그 차이(no-Skills 33.9% → curated 50.5%) | 없음 | 없음 | 부분: 고정은 각 조합 안의 모델·하네스와 87과제·시행 수; 변수는 스킬 조건(no-Skills·curated·self-authored)과 18개 조합 사이의 하네스 차이 | https://arxiv.org/abs/2602.12670 , https://arxiv.org/html/2602.12670 , https://github.com/benchflow-ai/skillsbench | 확인 |
| RepoBench | 논문 2023-06(초록에 소속 표기 없음) | 저장소 수준 코드 자동완성(검색·완성·파이프라인) | Python·Java 저장소에서 추출 | 다음 줄 예측 정확도 등 | 과제별 정확도 지표 | 없음 | 없음 | 부분: 고정은 평가 스위트; 변수는 검색·컨텍스트 구성 | https://arxiv.org/abs/2306.03091 | 확인 |
| Long Code Arena | JetBrains Research, 2024-06 | 프로젝트 전체 컨텍스트가 필요한 6개 과제(라이브러리 기반 생성, CI 빌드 수정, 프로젝트 완성, 커밋 메시지, 버그 위치, 모듈 요약) | 실제 저장소에서 수집하고 사람이 검증 | 과제별 평가 스위트 | 과제별 지표 | 없음 | 없음(수동 검증 테스트셋) | 부분: 고정은 과제별 평가 스위트; 변수는 오픈 베이스라인 구성 | https://arxiv.org/abs/2406.11612 | 확인 |
| τ-bench | Sierra, 2024-06 | 도구·정책을 갖춘 에이전트와 사용자(LM 시뮬레이션)의 대화 수행 | 소매·항공 도메인 규칙과 API를 사람이 설계 | 대화 종료 시점의 데이터베이스 상태를 정답 상태와 비교 | pass@1과 pass^k(k회 시도 전부 성공) | 없음 | 없음 | 부분: 고정은 공개 구현의 사용자 시뮬레이터와 환경·채점; 변수는 에이전트 방식(function calling·ReAct·Act)과 시뮬레이터 모델 | https://arxiv.org/abs/2406.12045 | 확인 |
| τ²-bench | Sierra, 2025-06 | 사용자도 도구를 쓰는 이중 제어 환경에서의 조율·안내 | 원자 요소를 조합하는 과제 생성기(Telecom 도메인) | 검증 가능한 상태 비교 | pass@1·pass^k, 추론/의사소통 오류 분해 | 없음 | 프로그램 생성이라 고정 문항 노출이 적음 `[추정]` | 부분: 고정은 이중 제어 환경·사용자 시뮬레이터 구현과 과제 생성기; 변수는 에이전트 전략(초록에 고정 여부 기술 없음 `[추정]`) | https://arxiv.org/abs/2506.07982 | 확인 |
| BrowseComp | OpenAI, 2025-04 | 찾기 어려운 사실을 웹에서 찾아내는 능력 | 사람 트레이너가 작성한 단문 정답 문제 1,266건 | 단문 정답에 대한 LLM 심판. 공식 구현은 grader 모델에게 `correct: yes\|no`를 생성하게 하고 형식이 맞지 않으면 `no`로 처리 | Accuracy. 문항별 64회 시도로 pass rate 분포 분석 | 없음(테스트타임 컴퓨트 스케일링과 best-of-N 효과는 보고) | canary 문자열 배포(문항·정답을 canary로 XOR 암호화해 배포), 예시 평문 공개 금지 요청 | 부분: 고정은 simple-evals 평가·채점 코드와 grader 프롬프트; 변수는 브라우징 도구와 에이전트 구성 | https://openai.com/index/browsecomp/ , https://github.com/openai/simple-evals/blob/main/browsecomp_eval.py | 확인 |
| Vending-Bench | 논문 2025-02(Andon Labs 소속 `[추정]`) | 장기 지평(실행당 2,000만 토큰 초과)에서의 일관성 | 자판기 운영 시뮬레이션 | 시뮬레이터 상태(순자산·재고 등) | 순자산 등 결과값과 실행 간 분산 | 실행당 토큰 규모를 명시 | 시뮬레이션이라 고정 정답 없음 | 예(모델만 교체) | https://arxiv.org/abs/2502.15840 | 확인 |
| GAIA | Meta·HuggingFace 등, 2023-11 | 추론·멀티모달·웹 탐색·도구 사용이 섞인 일반 조수 과제 | 사람이 작성한 466문항 | 단문 정답 일치 | Accuracy(사람 92% 대 당시 GPT-4+플러그인 15%) | 없음 | 466문항 중 300문항 정답을 비공개로 유지하고 리더보드로만 채점 | 아니오 | https://arxiv.org/abs/2311.12983 | 확인 |
| GDPval | OpenAI, 2025-09 발표, ICLR 2026 채택 | 44개 직업의 실제 업무 산출물 품질 | 평균 14년 경력 전문가가 실제 업무 산출물을 바탕으로 작성. 전체 1,320건, 공개 gold 220건. 과제당 평균 5회(최소 3회) 전문가 검토 | 같은 직업 전문가가 사람 산출물과 모델 산출물을 블라인드 pairwise 비교(better/as good as/worse). 직업별 루브릭 병기. 실험적 자동 채점기 별도 제공 | win rate(+tie). 자동 채점기 일치율 65.7%, 사람 간 일치율 70.8% | 모델이 전문가보다 약 100배 빠르고 100배 저렴하다고 보고(모델 추론 시간과 API 요금 기준). 과제당 전문가 소요 시간 평균 7시간 | 없음. 공개 gold 세트와 전체 세트 분리 | 부분: 고정은 과제와 블라인드 pairwise 채점 절차; 변수는 샘플링 경로(일부 제품 UI·일부 API)와 도구 구성 | https://openai.com/index/gdpval/ , https://cdn.openai.com/pdf/d5eb7428-c4e9-4a33-bd86-86dd4bcf12ce/GDPval.pdf , https://proceedings.iclr.cc/paper_files/paper/2026/file/290c2430f91912204f30bbcc990fff1d-Paper-Conference.pdf | 확인 |
| PaperBench | OpenAI, 2025-04 | AI 논문을 코드부터 실험까지 재현하는 능력 | ICML 2024 Spotlight·Oral 논문 20편, 저자와 공동 작성한 계층 루브릭 | 루브릭 8,316개 노드를 LLM 심판이 채점. 심판 성능 검증용 별도 벤치마크(JudgeEval) 제작 | 평균 재현 점수(%) | 없음. 상위 ML 박사 인력의 사람 기준선 별도 측정 | 없음 | 부분: 고정은 루브릭·o3-mini SimpleJudge 심판·12시간 재현 실행 한도; 변수는 에이전트 스캐폴드(BasicAgent 대 IterativeAgent)와 실행 시간(12·36시간) | https://arxiv.org/abs/2504.01848 | 확인 |
| Artificial Analysis Intelligence Index | Artificial Analysis, 현재 v4.1.1 | 9개 평가의 가중 평균으로 본 종합 지능 | 외부 벤치마크 재구현 + 자체 비공개 평가 | 대부분 pass@1. GDPval-AA v2는 3개 연구소의 프론티어 LLM 심판 패널 pairwise → Bradley-Terry Elo(사람 전문가 1000 기준) | Intelligence Index, 카테고리 가중치(Agents 34%·Coding 24%·Scientific 24%·General 18%) | 과제당 비용(입력·캐시 히트·캐시 쓰기·추론·출력 토큰 단가 반영)과 인덱스 전체 실행 비용을 별도 차트로 공개 | 일부 평가(AA-AnalystAgent 등)는 문항·정답·원본 파일 비공개 | 부분: 고정은 Stirrup 하네스·e2b 샌드박스·도구 6종과 에피소드·타임아웃·누적 입력 토큰 상한; 변수는 모델별 최대 출력 토큰·추론 설정(추론 모델은 모델마다 커스텀) | https://artificialanalysis.ai/methodology/intelligence-benchmarking , https://artificialanalysis.ai/models | 확인 |
| Epoch Capabilities Index (ECI) | Epoch AI, 논문 2025-11-28 | 여러 벤치마크를 하나의 능력 척도로 접합 | 기존 벤치마크 50종 이상의 공개 점수 | 2모수 로지스틱(2PL) 문항반응이론 적합 | ECI 점수(선형 척도) | 없음 | 개별 벤치마크 포화를 척도 접합으로 우회 | 아니오 | https://epoch.ai/data/eci-documentation , https://arxiv.org/abs/2512.00193 | 확인 |
| METR 시간 지평 | METR, 논문 2025-03, 현재 Time Horizon 1.1(페이지 최종 갱신 2026-05-08) | 사람 전문가 소요 시간으로 환산한 과제 길이 지평 | RE-Bench·HCAST와 짧은 신규 소프트웨어 과제 100여 건 | 자동 채점 + 사람 베이스라인 소요 시간 측정 | 50%·80% 성공 시간 지평(로지스틱 적합) | 사람 기준 소요 시간이 축 자체. 과제 가중치와 부트스트랩 신뢰구간 사용 | 비공개 과제 사용, 제로 데이터 리텐션 요구 | 부분: 고정은 자체 스캐폴드의 도구·상호작용 루프; 변수는 모델별 elicitation 조정 | https://metr.org/time-horizons/ , https://metr.org/blog/2025-03-19-measuring-ai-ability-to-complete-long-tasks/ | 확인 |
| LMArena·Code Arena | LMSYS→Arena, 논문 2024-03 | 사람 선호로 본 상대 품질(코드 아레나는 웹앱 생성) | 크라우드 사용자가 직접 입력한 프롬프트 | 블라인드 pairwise 투표 | Elo형 점수(Bradley-Terry) | 없음 | 실시간 사용자 프롬프트라 고정 문항 없음 | 아니오 | https://lmarena.ai/leaderboard , https://web.lmarena.ai/leaderboard , https://arxiv.org/abs/2403.04132 | 확인(리더보드 수치는 스크립트 렌더라 본문에서 읽지 못함) |
| GitHub Copilot 에이전틱 하네스 평가 | GitHub·Microsoft, 2026-06-25 | 같은 모델을 두고 하네스를 바꿨을 때의 해결률과 토큰 효율 | 공개 벤치마크(SWE-bench Verified·Pro, SkillsBench, TerminalBench 2.0)와 내부 벤치마크(Win-Hill) | 각 벤치마크의 자동 검증 | pass@1 해결률, 토큰 소비, 과제당 비용 | 과제당 평균 비용 대 해결률 산점도에 ±1σ 타원. 전 실행 2시간 타임아웃 | 없음(공개 벤치마크 그대로 사용) | 부분: 고정은 모델·과제·컨텍스트 창·추론 강도(medium)·도구 구성·2시간 타임아웃; 변수는 하네스(의도된 비교 대상) | https://github.blog/ai-and-ml/github-copilot/evaluating-performance-and-efficiency-of-the-github-copilot-agentic-harness-across-models-and-tasks/ | 확인 |

표에 있는 벤치마크는 28건입니다. `하네스 고정` 열은 3-6절의 정의, 즉 "모델을 비교할 때 에이전트 하네스와 그 설정을 고정하고 모델만 바꾸는가"로 판정했고, 값은 세 가지만 씁니다. `예(모델만 교체)`는 벤치마크가 하네스와 설정을 정하고 모델만 바꾸는 경우, `아니오`는 임의 에이전트·스캐폴드 제출을 비교하거나 하네스 개념이 없는 경우, `부분: <고정된 것>; <변수인 것>`은 일부만 고정하고 나머지를 변수로 남기는 경우입니다. 실제로 `예`에 해당하는 것은 시뮬레이션 환경 하나뿐이고 나머지는 `부분` 또는 `아니오`입니다. 즉 공개 벤치마크에서 "같은 조건" 비교는 기본값이 아니라 예외입니다.

## 2. 표에 담지 못한 절차와 수치

- **SWE-bench**: 각 인스턴스는 해결된 이슈와 그 PR에서 만들며, PR의 테스트가 수정 전 실패·수정 후 통과(FAIL_TO_PASS)인지, 그리고 무관한 기존 기능이 계속 통과(PASS_TO_PASS)하는지를 함께 확인합니다. 공식 리더보드는 resolved 외에도 resolved vs cost, cost limit, step limit 축의 비교 차트를 제공합니다.
- **SWE-bench Verified**: Python 숙련 개발자 93명이 무작위 1,699건을 주석했고, 한 표본을 3명이 독립 주석한 뒤 가장 심각한 등급으로 앙상블했습니다. 문제 서술 미명세는 38.3%, 유효 해답을 부당하게 탈락시킬 수 있는 테스트는 61.1%에서 발견되어 전체의 68.3%가 걸러졌습니다. 주석자 온보딩 시험용으로 엔지니어가 먼저 50건을 라벨링했습니다.
- **SWE-bench Multimodal**: 프런트엔드·시각화·다이어그램 등 사용자 대면 JS 라이브러리에서 모았고, 상위권 SWE-bench 시스템이 크게 고전한다는 결과로 언어·양식 일반화의 한계를 보였습니다(SWE-agent 12% 대 차순위 6%).
- **SWE-bench Pro**: 저장소마다 50~100개 과제를 배정해 한 프로젝트 스타일에 과적합하지 않게 했고, 해답 패치는 평균 4.1개 파일·107.4줄 변경 규모입니다. 환경 구축, 이슈 증강, 테스트 관련성·플레이키 검증의 세 지점에 사람을 넣습니다.
- **SWE-bench-Live**: 제출자는 에이전트 궤적을 함께 내야 하고, 관리자가 문제 서술과 도커 이미지 외의 필드나 정답 결과가 에이전트에 유출되지 않았음을 확인한 제출만 Verified 태그를 받습니다. RepoLaunch 에이전트로 C·C#·Java·Go·JS/TS·Rust 등과 Windows 환경까지 확장했습니다.
- **SWE-rebench**: 같은 모델을 SWE-bench Verified와 신선 과제에서 비교해 일부 모델의 점수가 오염으로 부풀 수 있음을 보였습니다. 파이프라인은 수집·환경 구성·검증을 자동화합니다.
- **Terminal-Bench**: 과제는 영어 지시문, 검증 테스트 스크립트, oracle 해답으로 구성되며 모든 테스트가 통과해야 성공입니다. 저장소는 harbor 프레임워크로 이전되었고, harbor는 `harbor run -d <dataset@version> -m <model> -a <agent>` 형태로 데이터셋·모델·에이전트를 각각 독립 인수로 받습니다. 즉 하네스를 고정하는 벤치마크가 아니라 어떤 하네스로 어떤 모델을 돌렸는지 공개하는 벤치마크입니다. Artificial Analysis는 이제 은퇴시킨 Terminal-Bench Hard 구성에서 최대 100 에피소드, 2시간 전역 타임아웃, 반복당 누적 입력 100만 토큰 상한을 적용했다고 공개했고 현재는 Terminal-Bench v2.1을 씁니다.
- **Aider Polyglot**: 리더보드 각 행이 실행 명령, 총 비용, 올바른 편집 형식 비율을 함께 싣습니다. 조사일에 열어 본 상위 행은 gpt-5 (high) 88.0%·$29.08이었고, 2026년 모델은 아직 올라와 있지 않았습니다.
- **LiveCodeBench**: 문제를 공개 시점별로 나눠 모델 학습 시점 이후 구간만 평가하는 방식이 오염 대책의 핵심입니다. 코드 생성뿐 아니라 자기수정, 코드 실행 예측, 테스트 출력 예측 시나리오를 따로 둡니다.
- **HumanEval·MBPP·EvalPlus**: HumanEval은 pass@k와 반복 샘플링(문제당 100 샘플)으로 난제 해결률을 올리는 효과를 처음 보고했습니다. EvalPlus는 테스트를 80배로 늘려 pass@k가 최대 19.3~28.9%p 과대평가되어 있었고 모델 순위가 뒤바뀔 수 있음을 보였습니다.
- **BigCodeBench**: 과제당 평균 테스트 5.6개와 평균 분기 커버리지 99%로 채점하며, docstring을 짧은 지시문으로 바꾼 Instruct 변형을 따로 둡니다. 60개 모델 최고 점수가 60% 수준으로 사람 97%와 큰 격차를 보였습니다.
- **SWE-Lancer**: 50달러 버그 수정부터 32,000달러 기능 구현까지 실제 지불액이 붙어 있고, 관리자 과제는 구현 제안 중 하나를 고르는 형태로 실제 매니저 선택과 대조합니다. 통일 Docker 이미지와 공개 스플릿 Diamond를 배포합니다. 다만 이 이미지는 실행 환경과 채점 절차를 통일하는 장치이고 에이전트 하네스를 규정하지는 않습니다.
- **MLE-bench**: 대회 공개 리더보드로 사람 기준선을 만들어 메달 등급으로 환산하고, 자원 스케일링(시간·시도)과 사전학습 오염의 영향을 별도 실험으로 다룹니다. o1-preview + AIDE 조합이 16.9%에서 동메달 이상이었습니다. 저장소는 "제출물을 만드는 에이전트에 어떤 가정도 하지 않도록 설계했다"고 밝히며 AIDE·MLAgentBench·OpenDevin 등 여러 에이전트를 함께 평가하고, 리더보드는 Agent 열과 LLM 열을 나눠 싣습니다. 비교 지침으로는 최소 3시드 반복과 자원 설정 공개(기본 24시간)를 권고합니다.
- **SkillsBench**: 같은 87개 과제를 스킬 없음과 큐레이트 스킬 조건으로 짝지어 18개 모델-하네스 조합에서 돌리고, task-macro pass rate가 33.9%에서 50.5%로 올랐습니다(+16.6pp, 정규화 이득 25.5%, 조합별 +4.1~+25.7pp). 87개 과제 중 13개는 스킬이 오히려 성능을 떨어뜨렸고(최대 -7.4pp), 원인은 불필요하게 무거운 파이프라인을 강제하거나 더 나은 기본 전략을 밀어내거나 디버깅할 수 없는 솔버로 유도하는 스킬이었습니다. 스킬 수는 1개 +18.0pp, 2~3개 +19.0pp, 4개 이상 +10.1pp이고 분량은 compact·standard(+19.0·+21.5pp)가 detailed(+14.5pp)·comprehensive(+0.7pp)를 앞섭니다. 저장소는 에이전트 실행 전에 oracle 해답이 통과해야 한다는 규칙을 명시합니다.
- **RepoBench**: 검색(R), 완성(C), 파이프라인(P) 세 과제로 나눠 크로스파일 컨텍스트 검색 능력과 다음 줄 예측을 분리 측정합니다.
- **Long Code Arena**: 6개 과제 모두 수동 검증 테스트셋과 평가 스위트, 오픈 베이스라인을 함께 제공하며 CI 빌드 수정처럼 실행 결과로 채점 가능한 과제를 포함합니다.
- **τ-bench**: 대화가 끝난 뒤 데이터베이스 상태를 목표 상태와 비교하는 방식이라 자유 서술 채점을 피합니다. 신뢰도 지표 pass^k를 도입했고, gpt-4o급 에이전트가 소매 도메인에서 pass^8 25% 미만이라는 결과로 반복 일관성 문제를 드러냈습니다.
- **τ²-bench**: 사용자도 도구를 쓰는 Dec-POMDP로 모델링하고, 원자 구성요소로 검증 가능한 과제를 프로그램 생성합니다. 단독 제어에서 이중 제어로 옮기면 성능이 크게 떨어졌습니다.
- **BrowseComp**: 작성자는 GPT-4o(브라우징 포함·제외), o1, 초기 deep research가 풀지 못하고 검색 5회 첫 페이지에 답이 없음을 확인해야 문항으로 채택했습니다. 문항당 64회 시도로 본 pass rate 분포에서 deep research가 16%는 항상 성공, 14%는 전부 실패였습니다. 정답이 단문이지만 채점은 문자열 비교가 아니라 grader 모델이 `correct: yes|no`를 생성하는 LLM 심판이며, 공식 구현은 그 패턴이 응답에 없으면 `no`로 처리합니다. 데이터셋 행은 canary 문자열을 키로 한 XOR로 암호화되어 배포됩니다.
- **Vending-Bench**: 실행당 2,000만 토큰을 넘는 장기 실행에서 같은 모델이 어떤 실행은 이익을 내고 어떤 실행은 무너지는 큰 분산을 보였으며, 실패가 컨텍스트 창 포화 시점과 상관이 없었습니다.
- **GAIA**: 466문항 중 300문항의 정답을 공개하지 않고 리더보드로만 채점해 오염과 과적합을 억제합니다. 사람은 92%, 당시 플러그인 장착 GPT-4는 15%였습니다.
- **GDPval**: 과제당 gold 세트 기준 최대 17개(전체 세트 38개) 참조 파일을 다루고, 산출물은 문서·슬라이드·도면·스프레드시트·멀티미디어입니다. 자동 채점기는 GPT-5-high 기반인데 유능한 OpenAI 모델의 산출물을 평가할 때 사람 전문가와의 상관이 낮아지며, 논문은 이를 모델이 자기 응답을 선호한다는 선행 연구(Panickssery et al. 2024)와 연결합니다. 220개 gold 과제 중 12개는 자동 채점기 한계로 채점 불가로 표시했습니다.
- **PaperBench**: 루브릭을 저자와 함께 만들어 재현 과제를 8,316개 채점 노드로 계층 분해했고, LLM 심판 자체를 평가하는 별도 벤치마크를 만들어 심판 성능을 측정했습니다. 최고 성적은 Claude 3.5 Sonnet(New) + 오픈소스 스캐폴딩의 21.0%였고 상위 ML 박사 기준선을 넘지 못했습니다.
- **Artificial Analysis Intelligence Index**: v4.1.1은 GDPval-AA v2, τ³-Banking, Terminal-Bench v2.1, SciCode, AA-LCR, AA-Omniscience, HLE, GPQA Diamond, CritPt로 구성되고, 지수 자체의 95% 신뢰구간을 ±1% 미만으로 보고합니다. GDPval-AA v2는 단일 심판을 세 연구소 프론티어 LLM 심판 패널로 교체하고 Elo를 사람 전문가 1000에 재기준화했습니다. AA-AnalystAgent는 문항당 5회 반복의 pass^5를 대표 지표로 쓰고 pass@1·pass@5를 함께 보고합니다.
- **Epoch ECI**: 여러 벤치마크에 걸쳐 평가된 모델을 연결점으로 삼아 문항 난이도와 모델 능력을 같은 척도에 올립니다. 공개 코드 저장소와 문서, 그리고 Google DeepMind 지원으로 작성된 논문을 함께 공개합니다.
- **METR 시간 지평**: 사람 전문가 소요 시간을 x축으로 로지스틱 성공 곡선을 적합해 50%·80% 지평을 구합니다. 현재 과제 스위트로는 16시간 이상 측정이 신뢰할 수 없다고 명시하고, 99% 지평은 문항 수 부족과 방법론 민감성 때문에 보고하지 않습니다.
- **LMArena·Code Arena**: 크라우드 사용자의 블라인드 pairwise 투표를 Bradley-Terry류 통계로 순위화하며, 논문 시점에 24만 표 이상을 모았고 크라우드 투표가 전문가 평가와 잘 일치함을 보고했습니다. 조사일에 두 URL 모두 arena.ai 도메인으로 이동했습니다.
- **GitHub Copilot 하네스 평가**: 모델·과제·컨텍스트 창·프롬프트 토큰 상한·추론 강도(medium)·도구 구성을 정규화하고 하네스만 바꿔 비교합니다. 100개 미만 소규모 벤치마크는 5회 독립 실행 후 최고 실행을 보고하고, TerminalBench 2.0 변동 분석에서는 조합마다 최소 5회 실행해 해결률·과제당 비용 평면에 ±1σ 타원을 그렸습니다. 인프라 장애는 재실행하지만 모델이 낸 오류는 제외하지 않습니다.

## 3. 이 레포 `bench/`에 대한 설계 시사점

현재 `bench/`는 과제 3건(`bugfix-python`, `multifile-refactor`, `search-and-answer`)을 후보 7개로 돌려 합격률과 실제 작업당 비용의 Pareto 전선을 냅니다. 격리 실행, fixture 해시 검사, `protected_paths`, 사전 검증(깨끗한 사본에서 `verify`가 통과하면 오류 종료)은 이미 위 벤치마크들의 핵심 장치와 같은 역할을 합니다. 아래는 추가로 가져올 요소입니다.

### 3-1. 공개된 해결 변경에서 과제 만들기

- 무엇을 가져오는가: 이미 해결되어 공개된 변경에서 역방향으로 과제를 만듭니다. 한 commit 또는 merge request가 (a) bug를 고치거나 기능을 넣고, (b) 새 test가 수정 전 실패·수정 후 통과하며, (c) 기존 test가 계속 통과하면 후보로 채택합니다. 원문 commit message를 그대로 과제에 복사하지 않고 기대 동작과 요구사항만 다시 씁니다.
- 어느 벤치마크의 어느 절차에서: SWE-bench의 이슈-PR 쌍 수집과 FAIL_TO_PASS/PASS_TO_PASS 구분, SWE-bench Pro의 커밋 스크래핑 후 사람 증강 절차.
- 이 레포에 맞게 어떻게 줄이는가: [GitLab](https://gitlab.com)의 공개 project에서 `glab`으로 확인할 수 있는 해결 change 중 작은 수만 선택합니다. Source license와 재배포 범위를 먼저 확인하고, issue·MR·commit의 사용자 이름이나 식별 metadata는 fixture에 복사하지 않습니다. `bench.py`의 clean-fixture preflight를 유지하고, oracle patch를 적용하면 `verify`가 통과하는지 과제 정의 시 확인합니다. Private project나 실제 work record는 public corpus의 입력으로 사용하지 않습니다.
- 근거 URL: https://arxiv.org/abs/2310.06770 , https://openai.com/index/introducing-swe-bench-verified/ , https://labs.scale.com/leaderboard/swe_bench_pro_public

### 3-2. 비코드 문서 산출물 채점

- 무엇을 가져오는가: 세 층으로 나눕니다. (1) 기계 검증 가능한 형식·사실 제약은 `search-and-answer`처럼 결정론적 verifier로 판정합니다. (2) 품질은 사람 기준 산출물과의 블라인드 pairwise 비교로 판정하고 better/as good as/worse 3단계와 직업별 루브릭을 씁니다. (3) 사람 비교를 매번 못 하므로 LLM 심판을 프록시로 두되, 심판 신뢰도를 수치로 남깁니다. 여기서 유념할 점은 "단문 정답 일치"조차 LLM 심판인 경우가 있다는 것입니다. BrowseComp 공식 구현은 정답이 단문인데도 grader 모델에게 `correct: yes|no`를 생성하게 하므로 채점 자체가 비결정적이고 심판 모델의 편향을 탄다는 뜻이며, 따라서 기계 검증 층은 문자열·구조 비교처럼 심판이 필요 없는 제약으로만 설계해야 합니다.
- 어느 벤치마크의 어느 절차에서: GDPval의 전문가 블라인드 pairwise와 win-rate, 루브릭 병기, 자동 채점기의 일치율 보고(자동 65.7% 대 사람 간 70.8%). PaperBench의 루브릭 계층 분해와 심판 평가용 별도 벤치마크. Artificial Analysis GDPval-AA v2의 3개 연구소 심판 패널과 Bradley-Terry Elo.
- 이 레포에 맞게 어떻게 줄이는가: public source와 처음부터 synthetic으로 작성한 기준 산출물만 사용합니다. 실제 report, customer document, employee identity, private issue를 redaction하거나 이름만 바꿔 기준 자료로 삼지 않습니다. Machine-checkable structure와 facts를 먼저 판정하고, quality judge가 필요하면 candidate와 reference의 blind pairwise를 사용합니다. Judge와 candidate가 같은 model family이면 `(self-judge)`를 표시하고, 표본 human review로 judge-human agreement를 측정한 범위에서만 quality score를 Pareto 축에 사용합니다. Position bias는 같은 pair의 순서를 바꿔 확인합니다.
- 근거 URL: https://cdn.openai.com/pdf/d5eb7428-c4e9-4a33-bd86-86dd4bcf12ce/GDPval.pdf , https://arxiv.org/abs/2504.01848 , https://artificialanalysis.ai/methodology/intelligence-benchmarking , https://arxiv.org/abs/2404.13076 , https://github.com/openai/simple-evals/blob/main/browsecomp_eval.py

### 3-3. 반복 실행과 pass^k

- 무엇을 가져오는가: 대표 지표를 "한 번 성공"에서 "여러 번 모두 성공"으로 옮깁니다. pass@1(반복 평균 합격률), pass@k(한 번이라도 성공), pass^k(k회 전부 성공)를 함께 계산해 능력 상한과 신뢰도를 분리합니다. 다만 τ-bench의 추정량은 `pass^k = E_task[C(c,k)/C(n,k)]`(과제당 n회 시행 중 c회 성공)이므로 표본 설계가 지표를 정합니다.
- 어느 벤치마크의 어느 절차에서: τ-bench의 pass^k 정의와 pass^8 결과. Artificial Analysis AA-AnalystAgent의 pass^5 대표 지표와 pass@1·pass@5 병기. Vending-Bench가 보여 준 실행 간 큰 분산. GitHub Copilot 평가의 조합당 최소 5회 실행과 ±1σ 타원.
- 이 레포에 맞게 어떻게 줄이는가: `default_repetitions`를 1에서 5로 올리는 대신, 반복은 전 후보에 균등하게 뿌리지 않고 단계적으로 씁니다. 1차로 후보×과제 1회씩 돌려 Pareto 후보를 좁히고, 2차로 살아남은 후보에만 반복을 채웁니다. 지표는 표본 크기에 맞춰 고릅니다. (a) Wilson 구간은 pass@1(반복 평균 합격률)에만 붙입니다. (b) pass^k는 n ≥ 2k인 표본에서만(예: n=10, k=5) 점추정으로 보고하고 구간은 붙이지 않습니다. n=k면 위 추정량이 0 또는 1로 퇴화하고, 그때 계산한 Wilson 구간은 pass^k가 아니라 pass@1의 구간입니다. (c) n ≥ 2k 표본을 모을 예산이 없으면 pass^k를 아예 보고하지 않고 "k회 전부 합격한 과제 수 / 전체 과제 수"만 적습니다. 보고서에는 Copilot 평가처럼 해결률·비용 평면에 실행 간 산포를 함께 적습니다. 다만 "최고 실행을 보고"하는 관행은 가져오지 않습니다(3-6 참조).
- 근거 URL: https://arxiv.org/abs/2406.12045 , https://artificialanalysis.ai/methodology/intelligence-benchmarking , https://arxiv.org/abs/2502.15840 , https://github.blog/ai-and-ml/github-copilot/evaluating-performance-and-efficiency-of-the-github-copilot-agentic-harness-across-models-and-tasks/

### 3-4. 비용·시간 보고 방식

- 무엇을 가져오는가: 비용을 과제당 단위로 정규화해 축으로 쓰고, 토큰 종류별 단가(입력·캐시 히트·캐시 쓰기·추론·출력)를 분리해 계산합니다. 시간과 상한(타임아웃·턴 수·토큰 상한)은 결과와 함께 반드시 명시합니다. 지출은 "합격당 비용"으로도 환산합니다.
- 어느 벤치마크의 어느 절차에서: Artificial Analysis의 과제당 비용·인덱스 전체 실행 비용 차트와 캐시 토큰 단가 반영. SWE-bench 공식 리더보드의 resolved vs cost·cost limit·step limit 축. Aider 리더보드의 실행 비용과 명령 병기. SWE-bench Pro 리더보드의 턴 상한 250 각주. Copilot 평가의 2시간 타임아웃과 과제당 평균 비용 축.
- 이 레포에 맞게 어떻게 줄이는가: `Catalog est/task`·session-recorded `Actual/task`·`Cost/pass` 구조를 유지하되, 각 행에 `timeout_seconds`와 최대 turn/request를 함께 싣습니다. Subscription/quota 후보는 현금 금액과 섞지 않고 `Quota/task`로 구분합니다. Cache cost는 실행 시점 OMP catalog를 사용하되 cache read와 write를 분리하고, [PRICING](PRICING.md)의 공식 문서 차이를 함께 밝힙니다.
- 근거 URL: https://artificialanalysis.ai/models , https://www.swebench.com/ , https://aider.chat/docs/leaderboards/ , https://labs.scale.com/leaderboard/swe_bench_pro_public

### 3-5. 오염 방지

- 무엇을 가져오는가: 세 가지를 조합합니다. (1) 과제와 정답을 공개 저장소에 두지 않는 보류 세트. (2) 과제 집합을 정기적으로 새로 만들어 교체하는 신선도 관리. (3) 공개해야 하는 문서에는 canary 문자열을 넣고 문항 본문을 평문으로 싣지 않기(BrowseComp는 문항·정답을 canary 키로 XOR 암호화해 배포합니다).
- 어느 벤치마크의 어느 절차에서: SWE-bench Pro의 copyleft·비공개 코드베이스 분리와 held-out 세트. SWE-bench-Live와 SWE-rebench의 정기 갱신 및 오염 실증. GAIA의 정답 300문항 비공개. BrowseComp의 canary 문자열과 예시 비공개 요청. Terminal-Bench 저장소의 canary 검사 CI.
- 이 레포에 맞게 어떻게 줄이는가: 공개 배포에는 처음부터 synthetic으로 만든 fixture와 공개 source에서 license를 확인한 과제만 둡니다. Private work, 실제 report, personal history는 held-out이라는 이유로 이 repository에 저장하지 않습니다. Public oracle이 답을 노출한다는 한계를 결과에 표시하고, 새 non-code task는 가능한 한 정답 문자열 대신 structure·invariant·behavior를 검증합니다. Canary는 공개 문항이 model input에 섞였는지 탐지하는 보조 장치로만 사용하며 비밀 보관 수단으로 취급하지 않습니다.
- 근거 URL: https://scale.com/blog/swe-bench-pro , https://swe-bench-live.github.io/ , https://arxiv.org/abs/2505.20411 , https://openai.com/index/browsecomp/ , https://arxiv.org/abs/2311.12983

### 3-6. 하네스 고정 비교의 의미

- 무엇을 가져오는가: "모델을 비교한다"와 "하네스를 비교한다"를 분리합니다. 모델 비교에서는 하네스와 그 설정(컨텍스트 창, 프롬프트 토큰 상한, 추론 강도, 도구 구성, 스킬, 타임아웃)을 고정하고 모델만 바꿉니다. 하네스 비교에서는 모델과 과제를 고정하고 하네스만 바꿉니다. 어느 쪽이든 설정을 명시해야 결과가 남습니다.
- 어느 벤치마크의 어느 절차에서: GitHub Copilot 평가가 같은 모델·같은 과제로 Copilot CLI 대 Claude Code·Codex CLI를 비교한 정규화 절차와, 그 결과 차이가 실행 간 변동 안에 있다는 결론. 반대로 하네스를 고정하지 않는 쪽의 대표가 Terminal-Bench(harbor가 `--agent`와 `--model`을 독립 인수로 받고 리더보드가 MODEL·AGENT를 분리)와 MLE-bench(에이전트를 가정하지 않는 설계, Agent·LLM 열 분리)입니다. SWE-bench Verified 문서는 같은 모델에서 스캐폴드에 따라 SWE-bench Lite 점수가 2.7%에서 28.3%까지 갈렸다고 기술합니다. SkillsBench는 짝지은 no-Skills 대 curated-Skills 비교로 조합을 고정한 채 한 변수만 바꾸는 예를 보여 줍니다.
- 이 레포에 맞게 어떻게 줄이는가: 현재 러너는 OMP 후보에 임시 오버레이를 쓰고 `agy` 후보에는 전역 규칙이 그대로 적용되는 비대칭이 있습니다. 이 비대칭을 보고서에 한 줄로 적고, 결과를 "모델 순위"가 아니라 "하네스+모델 조합 순위"로 표기합니다. 스킬·규칙의 효과를 알고 싶으면 SkillsBench식 짝 실행을 씁니다. 같은 과제·같은 모델에서 `--no-skills`와 기본 설정을 각각 돌려 차이를 보고합니다(OMP에는 이미 `--no-skills`와 `--skills <glob>`이 있습니다). 또한 Copilot 평가처럼 "5회 중 최고 실행"을 대표값으로 쓰지 않고 평균과 산포를 씁니다. 개인 벤치마크는 마케팅 수치가 아니라 다음 실행의 기본값을 고르기 위한 도구이므로 최고 실행 보고는 결정을 왜곡합니다.
- 근거 URL: https://github.blog/ai-and-ml/github-copilot/evaluating-performance-and-efficiency-of-the-github-copilot-agentic-harness-across-models-and-tasks/ , https://github.com/harbor-framework/harbor , https://github.com/openai/mle-bench , https://openai.com/index/introducing-swe-bench-verified/ , https://arxiv.org/abs/2602.12670

## 4. 하지 않을 것

- **수천 건 규모의 과제 집합**: SWE-bench 2,294건, SWE-bench Pro 1,865건, GDPval 1,320건은 전담 인력과 전문가 계약이 있는 조직의 규모입니다. 과제 5~8건으로는 절대 순위를 낼 수 없고, 그 사실을 인정한 채 "다음 실행의 기본 모델을 고른다"는 목적에 맞춰야 합니다. 신뢰구간이 넓다는 현재 README의 경고를 없애려고 과제 수를 늘리는 방향은 비용 대비 효과가 없습니다.
- **크라우드 심판과 Elo**: LMArena식 블라인드 투표는 표 수가 만 단위여야 의미가 생기고, 개인 한 명의 선호는 그냥 개인 선호입니다. 산출물 품질은 기준 산출물과의 pairwise로만 판정하고 Elo 척도는 쓰지 않습니다.
- **사람 다중 주석으로 과제 검증**: SWE-bench Verified의 3중 주석·93명 온보딩 절차는 재현할 수 없습니다. 대신 oracle 해답 통과, 사전 검증 실패, `protected_paths` 보존이라는 기계 검사로 대체합니다.
- **문항반응이론 기반 종합 지수**: ECI는 벤치마크 50종 이상과 모델 100종 이상의 교차 평가 데이터가 있어야 척도가 성립합니다. 과제 3~8건에서 단일 능력 척도를 추정하려는 시도는 노이즈를 지수로 포장하는 일입니다.
- **사람 기준 소요 시간 축(시간 지평)**: METR은 과제마다 사람 전문가 베이스라인 시간을 실측하고 부트스트랩으로 신뢰구간을 냅니다. 개인 과제마다 베이스라인을 여러 명에게 재는 것은 불가능하므로, 시간은 에이전트 벽시계 시간으로만 보고하고 "N시간짜리 과제를 푼다"는 해석은 하지 않습니다.
- **LLM 심판만으로 최종 순위 결정**: GDPval의 자동 채점기조차 사람 간 일치율보다 5%p 낮고, 유능한 자사 모델 산출물에서 상관이 더 낮아집니다. 심판 점수는 표본 사람 판정으로 검증된 범위에서만 쓰고, 검증되지 않은 과제는 기계 검증만으로 판정합니다.
- **최고 실행 보고와 인프라 실패 제외 관행의 무비판 수용**: Copilot 평가는 소규모 벤치마크에서 5회 중 최고 실행을 보고하고 인프라 이상을 제외합니다. 공개 비교에서는 방어할 수 있는 선택이지만, 개인 벤치마크에서 이를 따라 하면 폴백·공급자 부하·한도 소진 같은 실제 운영 실패가 지표에서 사라집니다. 그런 실패는 지금처럼 실패로 기록합니다.
