---
theme: default
title: ⟨덱 제목⟩
info: ⟨한 줄 설명⟩
layout: AsCover
transition: slide-left
colorSchema: light
fonts:
  provider: none
htmlAttrs:
  lang: ko
aspectRatio: 16/9
canvasWidth: 980
selectable: true
monaco: false
routerMode: hash
preloadImages: false
favicon: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Crect width='16' height='16' rx='3' fill='%23222'/%3E%3C/svg%3E"
export:
  withClicks: false
---

<p class="as-eyebrow">⟨행사 · 날짜⟩</p>

# ⟨청중이 기억할 결론 한 문장⟩

<p class="as-lead">⟨결론을 받쳐 주는 부제⟩</p>

::aside::

**⟨오늘 요청하는 것⟩**

⟨결정·승인·행동 한 줄⟩

<!--
⟨첫 문장으로 말할 내용, 이 발표의 범위, 다음 장으로 넘어가는 이유⟩
-->

---
layout: section
---

# ⟨섹션 제목⟩

<!--
⟨이 섹션이 답하는 질문⟩
-->

---
layout: AsEvidence
---

::header::

# ⟨근거가 받치는 주장형 제목⟩

::default::

| ⟨항목⟩ | ⟨기준⟩ | ⟨비교⟩ |
| --- | --- | --- |
| ⟨값⟩ | ⟨값⟩ | ⟨값⟩ |

::footer::

⟨출처 · 기간 · 측정/합성 구분⟩

<!--
⟨표를 읽는 순서와 결론, 단서⟩
-->

---
layout: AsSplit
pdf: steps
---

::header::

# ⟨코드가 보여 주는 동작⟩

::default::

<<< @/snippets/example.ts ts {all|2-3|all}

::right::

<v-clicks>

- ⟨해석 1⟩
- ⟨해석 2⟩

</v-clicks>

::footer::

⟨파일 경로 · 버전⟩

<!--
⟨코드를 설명하는 순서⟩
[click] ⟨강조한 줄에서 말할 것⟩
[click] ⟨전체로 돌아와 정리할 것⟩
-->

---
layout: quote
---

# "⟨인용문⟩"

⟨출처⟩

<!--
⟨인용을 꺼내는 이유⟩
-->

---
layout: center
---

# ⟨마지막에 남길 요청 또는 결론⟩

<!--
⟨질문을 받기 전에 정리할 한 문장⟩
-->
