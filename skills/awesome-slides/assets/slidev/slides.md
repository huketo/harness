---
theme: default
title: 기다리는 시간을 먼저 줄인다
info: |
  합성 데이터로 설명하는 요청 처리 개선안. 실제 서비스 측정이나 성능 약속이 아닙니다.
  Template structure adapted from content-skills; see NOTICE.txt.
layout: AsCover
colorSchema: light
aspectRatio: 16/9
canvasWidth: 980
fonts:
  provider: none
htmlAttrs:
  lang: ko
presenter: dev
browserExporter: dev
monaco: false
selectable: true
duration: 6min
exportFilename: queue-decision
export:
  withClicks: false
---

<p class="as-eyebrow">ENGINEERING DECISION / SYNTHETIC EXAMPLE</p>

# 기다리는 시간을<br>먼저 줄인다

<p class="as-lead">처리 속도보다 대기열을 먼저 보는<br>요청 처리 개선안</p>

::aside::

**오늘의 판단**

작업자를 늘리기 전에<br>대기열을 제한한다.

<p class="as-eyebrow">6 MIN · 기술 검토용 예시</p>

<!--
00:00–00:40 · 40초
대상은 요청 처리 정책을 검토하는 엔지니어다. 오늘의 결정은 모든 요청을 받는 대신, 대기열이 찼을 때 재시도를 안내하는 제한을 시험할지 여부다.
수치와 관찰은 전부 합성 예시이며 실제 서비스 결과가 아니다. 실제 적용 전에는 원본 추적 데이터와 거절률을 함께 확인해야 한다.
-->

---
layout: AsEvidence
---

::header::

# 처리보다 대기가 더 오래 걸린다

::default::

<AsBreakdown caption="합성 요청 2건의 구간별 시간 · 막대는 같은 1,000 ms 척도" :scenarios="[{ title: '변경 전 요청', segments: [{ name: '대기', value: 700 }, { name: '처리', value: 300 }] }, { title: '제한 적용 후 수락된 요청', segments: [{ name: '대기', value: 200 }, { name: '처리', value: 300 }] }]" />

<p v-click class="as-takeaway">줄어든 500 ms는 모두 <strong>대기 구간</strong>에서 나왔다.</p>

::footer::

합성 예시 · 두 요청의 비교이며 평균·백분위가 아니다. 거절된 요청은 다음 판단에 포함한다.

<!--
00:40–01:40 · 60초
먼저 같은 척도의 전체 길이와 처리 구간 300 ms가 같다는 점을 짚는다.
[click] 대기 구간만 700 ms에서 200 ms로 줄었다. 이 예시는 계산 구조를 설명할 뿐 처리량 개선이나 인과관계를 증명하지 않는다.
정적 PDF에서는 결론까지 보인다. 전체 사용자 경험은 거절과 재시도까지 봐야 한다는 질문으로 다음 장을 연결한다.
-->

---
layout: AsEvidence
---

::header::

# 입구에서 제한하고, 결과까지 추적한다

::default::

<AsStageFlow :stages="[{ id: 'admit', name: '수락 판단', detail: '대기열 여유를 확인', metric: 'queue depth' }, { id: 'work', name: '작업 처리', detail: '수락한 요청을 실행', metric: 'service time' }, { id: 'observe', name: '결과 확인', detail: '재시도까지 묶어 관찰', metric: 'end-to-end time' }]" :highlight="['admit']" />

<p class="as-takeaway">대기열이 가득 차면 <strong>재시도 시점</strong>을 안내한다.</p>

::footer::

화살표는 처리 순서다. 수락되지 않은 요청은 작업 단계로 들어가지 않고 호출자에게 돌아간다.

<!--
01:40–02:35 · 55초
입구, 작업, 관찰을 왼쪽부터 설명한다. 강조는 변경 위치이지 다른 단계가 덜 중요하다는 뜻이 아니다.
입구 제한은 부하를 없애지 않는다. 호출자가 재시도를 어떻게 처리하는지 확인해야 하며, 최종 완료 시간에 재시도 대기를 포함한다.
-->

---
layout: AsSplit
---

::header::

# 경계에서는 빠르게 응답한다

::default::

<<< @/snippets/admission.ts {all|4-7|all}

::right::

## 대기열 길이 ≥ 한도

수락하지 않고<br>**1초 뒤 재시도**를 안내한다.

## 대기열 길이 < 한도

작업을 수락한다.

::footer::

설명용 TypeScript · 실제 구현에는 원자적 수락 판단과 호출자의 재시도 정책이 필요하다.

<!--
02:35–03:35 · 60초
원본 코드는 snippets/admission.ts에서 직접 가져온다. 슬라이드에 별도 복사본을 유지하지 않는다.
[click] 경계값과 재시도 응답을 강조한다. 이 함수는 정책의 설명이며 동시성 안전한 큐 구현이 아니다.
[click] 전체 코드로 돌아온다. 정적 출력에서도 양쪽 분기와 설명이 남는다.
-->

---
layout: AsEvidence
---

::header::

# 관찰과 해석을 나눠야 변경을 검증할 수 있다

::default::

<AsCaseStory saw="합성 추적에서 대기 700 ms, 처리 300 ms를 기록했다." meant="이 요청에서는 대기 구간이 전체 시간의 70%다." changed="대기열 한도를 두고, 초과 요청에는 재시도를 안내한다." verified="같은 입력 부하에서 거절률과 재시도 포함 완료 시간을 비교한다." rollback="완료 시간이 악화되거나 합의한 거절률을 넘을 때" />

::footer::

검증은 다음 실험의 계획이다. 변경의 효과가 입증되었다는 뜻이 아니다.

<!--
03:35–04:40 · 65초
관찰은 숫자, 해석은 숫자가 뜻하는 것, 변경은 우리가 조정하는 값이다. 이 셋을 한 문장으로 합치면 가설을 사실로 읽기 쉽다.
검증 행은 완료된 결과가 아니라 앞으로 할 비교다. 실제 실험에서는 입력 부하, 요청 구성, 관찰 기간, 반복 횟수를 맞춘다.
-->

---
layout: AsSplit
---

::header::

# 수락된 요청만 빨라져서는 충분하지 않다

::default::

| 합성 시나리오 | 변경 전 | 변경 후 |
| :--- | ---: | ---: |
| 입력 요청 | 100건 | 100건 |
| 수락 | 100건 | 95건 |
| 즉시 거절 | 0건 | 5건 |
| 재시도 후 완료 | 미관찰 | 미관찰 |

::right::

<p class="as-eyebrow">NEXT EXPERIMENT</p>

## 같은 부하로 비교한다

**완료 시간과 거절률**을<br>하나의 판단으로 묶는다.

다음 검토에서는 재시도까지<br>포함한 추적을 가져온다.

::footer::

합성 집계 · 앞의 2건 추적과는 별도 예시다. 95% 수락은 95% 완료를 의미하지 않는다.

<!--
04:40–06:00 · 80초, 질문 포함
표의 모수는 각 시나리오 입력 100건이다. 앞 장의 개별 요청 시간과 통계적으로 연결한 데이터가 아니다.
95건 수락만으로 성공률을 주장할 수 없다. 미관찰을 0으로 바꾸지 않는다.
결정 요청: 재시도 포함 완료 시간과 거절률을 수집하는 제한된 비교 실험을 설계한다. 실제 임계값과 실행 승인은 운영 맥락에서 별도로 정한다.
-->
