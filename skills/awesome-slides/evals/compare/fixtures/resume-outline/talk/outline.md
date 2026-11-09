status: draft

## 1. 평균이 같아도 일부 요청은 훨씬 늦습니다
- Purpose: 관찰로 시작한다
- Evidence: A/B 평균 총시간 모두 100ms (synthetic)
- Visual: comparison
- Clicks: none
- PDF: final
- Notes: 두 구간의 평균이 같다는 사실부터 보여 준다
- Time: 1분30초

## 2. 응답 시간은 대기와 처리로 나뉩니다
- Purpose: 시간 분해 모델
- Evidence: total = queue_ms + service_ms
- Visual: diagram
- Clicks: 대기 → 처리 → 응답 순서로 공개
- PDF: steps
- Notes: 대기 시간이 보이지 않으면 처리 속도만 의심하게 된다
- Time: 2분

## 3. p95는 느린 쪽 5%의 경계입니다
- Purpose: p95와 nearest-rank 계산법
- Evidence: ceil(0.95 × N)번째 값
- Visual: code
- Clicks: 계산 줄 강조
- PDF: final
- Notes: 표본 20개에서 19번째 값이다
- Time: 2분

## 4. B의 p95는 460ms, A는 100ms입니다
- Purpose: 같은 축에서 A/B 비교
- Evidence: nearest-rank p95 A 100ms, B 460ms (synthetic)
- Visual: chart
- Clicks: none
- PDF: final
- Notes: 평균만 봤다면 놓쳤을 차이
- Time: 2분

## 5. 진단은 평균 → p95 → 분해 → 가설 순서입니다
- Purpose: 진단 순서 정리
- Evidence: 앞 장들의 흐름
- Visual: diagram
- Clicks: none
- PDF: final
- Notes: 다음 행동은 현재 서비스의 계측 위치 확인
- Time: 2분

## 6. 표본 40건의 합성 자료라 결론에는 한계가 있습니다
- Purpose: 한계
- Evidence: 합성, 작은 표본
- Visual: text
- Clicks: none
- PDF: final
- Notes: SLO나 통계적 유의성을 말하지 않는다
- Time: 1분30초
