---
theme: default
title: 기다리는 시간을 먼저 줄인다
info: |
  합성 데이터로 설명하는 요청 처리 개선안. 실제 서비스 측정이나 성능 약속이 아닙니다.
  Template structure adapted from content-skills; see NOTICE.txt.
layout: AsCover
transition: slide-left
duration: 8min
presenter: dev
browserExporter: dev
colorSchema: light
fonts:
  provider: none
htmlAttrs:
  lang: ko
aspectRatio: 16/9
canvasWidth: 980
selectable: true
monaco: false
exportFilename: queue-decision
export:
  withClicks: false
---

<p class="as-eyebrow" v-motion :initial="{ opacity: 0, y: 10 }" :enter="{ opacity: 1, y: 0 }">ENGINEERING DECISION / SYNTHETIC EXAMPLE</p>

<h1 v-motion :initial="{ opacity: 0, y: 20 }" :enter="{ opacity: 1, y: 0 }">기다리는 시간을<br>먼저 줄인다</h1>

<p class="as-lead" v-motion :initial="{ opacity: 0, y: 20 }" :enter="{ opacity: 1, y: 0 }">처리 속도보다 대기열을 먼저 보는<br>요청 처리 개선안</p>

::aside::

**오늘의 판단**

작업자를 늘리기 전에<br>대기열을 제한한다.

<p class="as-eyebrow">8 MIN · 기술 검토용 예시</p>

<!--
00:00–00:45 · 45초
대상은 요청 처리 정책을 검토하는 엔지니어입니다. 오늘의 결정은 모든 요청을 무조건 받는 대신, 대기열이 가득 찼을 때 재시도를 안내하는 입구 제한 정책을 시험할지 여부입니다.
수치와 관찰은 전부 합성 예시이며 실제 서비스 결과가 아닙니다. 실제 적용 전에는 원본 추적 데이터와 거절률을 함께 확인해야 합니다.
-->

---
layout: AsEvidence
---

::header::

# 처리보다 대기가 더 오래 걸린다

::default::

<AsBreakdown caption="합성 요청 2건의 구간별 시간 · 막대는 같은 1,000 ms 척도" :scenarios="[{ title: '변경 전 요청', segments: [{ name: '대기', value: 700 }, { name: '처리', value: 300 }] }, { title: '제한 적용 후 수락된 요청', segments: [{ name: '대기', value: 200 }, { name: '처리', value: 300 }] }]" />

<p v-click class="as-takeaway">줄어든 <span v-mark.underline="1">500 ms</span>는 모두 <strong>대기 구간</strong>에서 나왔다.</p>

::footer::

합성 예시 · 두 요청의 비교이며 평균·백분위가 아닙니다. 거절된 요청은 다음 판단에 포함합니다.

<!--
00:45–01:40 · 55초
먼저 같은 척도의 전체 길이와 처리 구간 300 ms가 동일하다는 점을 짚습니다.
[click] 줄어든 500 ms는 전부 대기 구간에서 확보했습니다. 이 예시는 계산 구조를 설명할 뿐 전체 처리량의 개선을 보장하지 않습니다.
정적 PDF에서도 결론까지 온전히 보존됩니다. 전체 경험을 파악하려면 거절과 재시도 영향도 함께 살펴야 합니다.
-->

---
layout: AsEvidence
---

::header::

# 입구에서 제한하고, 결과까지 추적한다

::default::

<AsStageFlow :stages="[{ id: 'admit', name: '수락 판단', detail: '대기열 여유를 확인', metric: 'queue depth' }, { id: 'work', name: '작업 처리', detail: '수락한 요청을 실행', metric: 'service time' }, { id: 'observe', name: '결과 확인', detail: '재시도까지 묶어 관찰', metric: 'end-to-end time' }]" :highlight="['admit']" />

<v-clicks>

- **입구 제어**: 대기열 한도를 검사하여 <span v-mark.circle="1">수락</span> 여부를 경계에서 판정합니다.
- **작업 격리**: 허용된 요청만 작업자에게 전달하여 처리 지연을 방지합니다.
- **결과 관찰**: 거절된 요청의 재시도 대기를 포함한 전체 시간을 측정합니다.

</v-clicks>

::footer::

화살표는 처리 순서입니다. 수락되지 않은 요청은 작업 단계로 들어가지 않고 호출자에게 돌아갑니다.

<!--
01:40–02:35 · 55초
입구, 작업, 관찰의 세 단계를 왼쪽부터 차례로 짚습니다. 강조 표시는 정책의 개입 위치를 나타냅니다.
[click] 첫째, 입구에서 대기열 여유를 즉시 확인합니다.
[click] 둘째, 작업 단계로 진입하는 작업 수를 통제합니다.
[click] 셋째, 관찰 단계에서 재시도 비용까지 합산해 최종 영향을 평가합니다.
-->

---
layout: AsEvidence
transition: slide-up
---

::header::

# 수락 판단 코드가 3단계로 진화한다

::default::

````md magic-move
```ts
export function admit(
  queueDepth: number, limit: number,
) {
  return { accepted: true }
}
```
```ts
export function admit(
  queueDepth: number, limit: number,
) {
  if (queueDepth >= limit)
    return { accepted: false }
  return { accepted: true }
}
```
```ts
export function admit(
  queueDepth: number, limit: number,
) {
  if (queueDepth >= limit)
    return {
      accepted: false, retryAfterMs: 1000,
    }
  return { accepted: true }
}
```
````

::footer::

단계별 정책 변경 · snippets/admission.ts 의 실제 구조와 정확히 일치합니다.

<!--
02:35–03:35 · 60초
수락 함수가 안전한 형태로 발전하는 세 단계를 살펴봅니다. 처음에는 들어오는 모든 요청을 무조건 수락했습니다.
[click] 대기열 길이를 검사해 한도를 넘으면 거절하는 조건을 추가했습니다.
[click] 단순 거절에 그치지 않고 호출자가 언제 다시 시도해야 할지 재시도 대기 시간을 안내합니다.
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

수락하지 않고<br>**1초 뒤 재시도**를 안내합니다.

## 대기열 길이 < 한도

작업을 즉시 수락합니다.

::footer::

설명용 TypeScript · 실제 구현에는 원자적 수락 판단과 호출자의 재시도 정책이 필요합니다.

<!--
03:35–04:30 · 55초
원본 코드는 snippets/admission.ts 파일에서 직접 임포트하여 슬라이드에 동기화합니다.
[click] 한도 도달 조건과 1초 후 재시도 안내 반환부를 집중 조명합니다.
[click] 다시 전체 제어 흐름으로 돌아옵니다. 정적 출력에서도 양쪽 분기 설명이 명확하게 보존됩니다.
-->

---
layout: AsEvidence
---

::header::

# 대기열이 가득 차면 즉시 재시도를 안내한다

::default::

<AsDemoMedia
  src="/demo-admission.mp4"
  poster="/demo-admission.poster.jpg"
  caption="합성 시뮬레이션 · 실제 서비스 화면이 아니다"
  fallback="대기열이 한도에 닿는 순간 새 요청은 수락되지 않고 재시도 안내를 받는다. 수락된 요청만 처리 단계로 넘어간다."
/>

::footer::

합성 시뮬레이션 클립 (8초) · 실제 서비스 화면이 아니며 사용 시 자체 데모로 교체해야 합니다.

<!--
04:30–05:30 · 60초
대기열 한도 6과 처리 시간 300 ms를 가정한 시뮬레이션 화면입니다.
[click] 비디오를 재생하면 요청이 밀려들 때 대기열이 6칸에 도달하고, 초과된 요청은 대기열에 쌓이지 않은 채 즉시 1초 뒤 재시도 안내를 받습니다.
정적 PDF와 비디오 미지원 환경에서도 하단 fallback 문장으로 핵심 동작이 전달됩니다.
-->

---
layout: AsEvidence
---

::header::

# 관찰과 해석을 나눠야 변경을 검증할 수 있다

::default::

<AsCaseStory saw="합성 추적에서 대기 700 ms, 처리 300 ms를 기록했다." meant="이 요청에서는 대기 구간이 전체 시간의 70%다." changed="대기열 한도를 두고, 초과 요청에는 재시도를 안내한다." verified="같은 입력 부하에서 거절률과 재시도 포함 완료 시간을 비교한다." rollback="완료 시간이 악화되거나 합의한 거절률을 넘을 때" />

::footer::

검증은 다음 실험의 계획입니다. 변경의 효과가 완전히 입증되었다는 뜻이 아닙니다.

<!--
05:30–06:20 · 50초
관찰된 숫자와 해석, 그리고 우리가 제어하려는 변경 사항을 엄격히 구분합니다.
의도적으로 모션을 배제하여 정적인 상태에서 데이터와 설계 가설을 차분하게 검토합니다.
검증 기준과 롤백 임계값을 미리 합의해야 프로덕션 환경의 위험을 통제할 수 있습니다.
-->

---
layout: AsSplit
transition: fade
---

::header::

# 수락된 요청만 빨라져서는 충분하지 않다

::default::

<v-switch :at="0">
  <template #0>

  ### 변경 전 · 무제한 대기열

  | 합성 지표 | 측정값 |
  | :--- | ---: |
  | 입력 요청 | 100건 |
  | 즉시 수락 | 100건 |
  | 즉시 거절 | 0건 |
  | 최대 대기 지연 | 3,200 ms |
  | 재시도 후 완료 | 해당 없음 |

  </template>
  <template #1>

  ### 변경 후 · 입구 제한 적용

  | 합성 지표 | 측정값 |
  | :--- | ---: |
  | 입력 요청 | 100건 |
  | 즉시 수락 | 95건 |
  | 즉시 거절 (재시도 안내) | 5건 |
  | 최대 대기 지연 | 1,800 ms |
  | 재시도 후 완료 | 5건 중 4건 |

  </template>
</v-switch>

::right::

<p class="as-eyebrow">POLICY COMPARISON</p>

## 지연 상한과 수락률을 함께 평가한다

<strong>수락률 95%</strong>와 <strong>지연 상한</strong>을<br>하나의 판단으로 묶습니다.

재시도 대기 시간을 포함한 전체 사용자 체감 지연을 비교해야 합니다.

::footer::

합성 집계 · 100건 기준 시뮬레이션 수치이며 실제 프로덕션 통계가 아닙니다.

<!--
06:20–07:10 · 50초
변경 전에는 100건을 모두 받았지만 최대 대기 시간이 3,200 ms까지 치솟았습니다.
[click] v-switch로 전환된 변경 후 표를 보면 5건을 즉시 거절하고 재시도를 유도하여 최대 대기를 1,800 ms로 묶었습니다.
수락률 숫자만 보지 않고 재시도 완료율과 전체 지연을 함께 검토해야 합니다.
-->

---
layout: two-cols
---

<p class="as-eyebrow">NEXT EXPERIMENT</p>

# 다음 검증 과제

실제 환경 검증을 위해 세 가지 측정을 순차 진행합니다.

<v-clicks>

- **재시도 완료율**: 1초 후 재요청의 정상 처리율 측정
- **종단간 지연**: 재시도 대기를 포함한 사용자 체감 시간 확인
- **적정 한도 산출**: 작업자 처리 용량에 맞춘 대기열 크기 도출

</v-clicks>

::right::

<p class="as-eyebrow">DECISION REQUIRED</p>

# 오늘의 결정 요청

**카나리 배포 승인**

대기열 제한 정책을 전체 트래픽의<br>5%에 카나리로 우선 시험합니다.

<div class="as-decision-box" v-click>

### 합의 임계값
- p99 대기 시간 1,800 ms 이하 유지
- 재시도 포함 최종 완료율 99.5% 이상 유지

</div>

<p class="as-eyebrow" style="margin-top: 24px;">합성 데이터 검토 완료 · 8 MIN</p>

<!--
07:10–08:00 · 50초
내장 two-cols 레이아웃으로 다음 과제와 최종 결정을 한눈에 비교합니다.
[click] 좌측에서 재시도 완료율,
[click] 종단간 사용자 지연,
[click] 최적의 큐 한도를 순차 도출합니다.
[click] 우측의 카나리 배포 합의 기준을 확인하고 실행 승인을 요청합니다.
-->
