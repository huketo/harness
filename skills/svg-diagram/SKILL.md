---
name: svg-diagram
description: 문서에 넣을 SVG 다이어그램(구조, 흐름차트, 시퀀스, 상태 전이, 타임라인, 스윔레인, 포함 관계, 트리)을 그리거나 기존 SVG의 잘림·겹침·모바일 가독성을 고친다. Markdown의 .svg 파일, HTML 인라인 SVG, Word 삽입용 그림 모두 같은 규칙으로 만든다.
---

# SVG 다이어그램

그림은 인라인 SVG 또는 `.svg` 파일로 그린다. 텍스트가 문서에 남아 검색·복사되고, 외부 요청이 없고, 좌표를 직접 계산하므로 마크업만으로 검사할 수 있다.

호스트(HTML 템플릿, GitHub 렌더러, Word)가 SVG에 스타일을 주지 않는다. 스타일과 marker는 SVG 안에 들어 있어야 한다(self-contained). 호스트가 SVG `<text>`를 지우는 경우(LSOffice DEXT5)는 `lsoffice-post-writing`이 foreignObject 변형을 소유하고, 이 스킬의 나머지 규칙은 그대로 적용한다.

산문에만 있는 규칙은 깨진 그림을 내보낸다. 마크업으로 판정되는 규칙은 [`scripts/check.py`](scripts/check.py)가 검사하고, 렌더가 필요한 규칙은 브라우저 audit이 검사한다. 둘 다 통과한 그림만 전달한다.

## 작업 순서

1. **그릴지 판정** — [그릴 것](#그릴-것과-그리지-않을-것)에 해당하지 않으면 표나 문장으로 쓴다.
2. **계획 선언** — 그리기 전에 한 문단으로 적는다: [유형](#유형별-문법), 노드 목록, 화살표 목록, 강조할 노드 1~2개, [예산](#예산)을 넘겨서 뺄 것. 사용자가 있으면 이 문단을 보여 준 뒤 그린다. 요청이 유형·내용을 이미 못박았으면 생략한다.
3. **remove test** — 노드를 하나 빼도 이해되는가, 항상 같이 움직이는 노드 둘을 하나로 합칠 수 있는가, 배치로 드러나는 관계의 선을 지울 수 있는가, 모양·선 종류가 이미 말하는 라벨을 지울 수 있는가. 네 질문에 전부 "아니오"가 될 때까지 뺀다.
4. **좌표 계산** — [모바일 규칙](#모바일-규칙)으로 W 상한을 정하고, [좌표 규칙](#좌표-규칙)으로 격자·노드 폭·연결선 경로를 숫자로 먼저 적는다.
5. **마크업** — [마크업](#마크업) 형태로 쓴다.
6. **검수** — [검수](#검수) 전부를 통과시킨다.

## 그릴 것과 그리지 않을 것

구조(무엇이 무엇을 포함·참조하는가), 흐름(호출·데이터 이동 순서, 분기), 시간 관계, 상태 전이를 그린다.

값의 비교, 목록, 조건 대응은 표로 적는다. 3열 표로 같은 내용이 전달되면 표를 고른다. 문장 두 개로 정확히 전달되는 내용에는 그림을 만들지 않는다. 도형 하나짜리 그림은 문장이다.

## 예산

| 항목 | 상한 |
|---|---|
| 노드 | 9 |
| 화살표 | 12 |
| 강조(굵은 테두리·색) | 2 |
| 영역(zone) | 3 |
| 주석 callout | 2 |
| 범례 항목 | 실제로 쓴 선·테두리 종류 수와 같게 |

넘으면 개요 그림과 상세 그림으로 나눈다. 강조를 4개에 주고 싶다면 아직 무엇이 핵심인지 정하지 않은 것이다.

## 모바일 규칙

독자는 폭 360px 휴대폰에서도 연다. 페이지·figure 여백을 빼면 그림에 남는 폭은 약 300px이고, 그림은 그 폭에 맞춰 축소된다. **렌더 글자 크기 = 폰트 px × 300 / viewBox 폭 W** 가 11px 이상이어야 한다. 따라서 `W ≤ 폰트 px × 27`.

| 폰트 | W 상한 |
|---|---|
| 12px | 324 |
| 14px (기본) | 378 |
| 16px | 432 |

노드가 이 폭에 들어가지 않으면 열을 줄이고 세로로 쌓아 H를 늘린다. 가로 스크롤로 폭을 버는 방식은 쓰지 않는다. 데스크톱에서는 `max-width: Wpx`로 1:1 크기를 유지한다. 한글은 12px 아래에서 뭉개지므로 폰트를 줄이지 말고 라벨을 줄인다.

## 좌표 규칙

좌표를 먼저 정하고 마크업을 쓴다. 자동 배치가 없으므로 겹침과 잘림은 전부 계산 실수다.

**격자.** 좌표·크기·간격·폰트는 전부 4의 배수다. 기준값: 노드 높이 44, 행 간격 88, 노드 사이 가로 간격 60 이상, 여백 12. 같은 종류의 노드는 같은 폭·높이를 쓰고, 한 그림의 노드 폭은 두 종류까지만 둔다.

**텍스트 폭은 글자 단위로 잰다.** 전각 문자(한글·한자·전각 기호)는 1em, 그 외(라틴·숫자·공백·구두점)는 0.6em. 스크립트별로 세면 `주문 v2.1`의 `2`, `.`, `1`을 빠뜨린다. 노드 폭 = 폭 합계 × 폰트 px + 좌우 여백 각 12px 이상을 4의 배수로 올림. 두 줄이 필요하면 `<tspan>`으로 나누고 노드 높이를 24px 늘린다.

**노드.** `<text text-anchor="middle" dominant-baseline="central">`에 노드 중심 좌표를 준다. 노드 채움은 불투명(흰색)이어야 선이 비쳐 보이지 않는다. 이름은 본문 글꼴, 포트·명령·URL·필드 타입 같은 기술 부제만 `class="sub"` 고정폭 12px로 이름 아래 줄에 둔다. 색은 hex로만 적는다. `rgba()`와 `transparent`는 Office SVG 렌더러가 불투명 검정으로 칠한다.

**그리는 순서(z-order).** 영역 → 연결선 → 선 라벨 → 노드 → 범례 → callout. 선이 노드 아래로 들어가야 접점이 깨끗하다.

**연결선.**
- 같은 x 또는 y를 공유하는 노드 사이만 `<line>`. 그 외는 직교 elbow `<path class="edge">`. 대각선은 쓰지 않는다.
- elbow는 모서리를 반지름 8로 둥글린다. 오른쪽·아래로 가는 두 굽이 경로(`mid = (x1+x2)/2`):
  `M x1,y1 H mid-8 Q mid,y1 mid,y1+8 V y2-8 Q mid,y2 mid+8,y2 H x2`
  위로 가면 세로 부호를 뒤집는다. 목적지가 위·아래에 있으면 옆면이 아니라 위·아래 변에서 나가고 들어오는 한 굽이 L 경로를 쓴다.
- 노드 경계에서 6px 떨어져 시작하고 끝난다. 화살촉이 테두리를 덮으면 어느 노드에 붙는지 흐려진다.
- 같은 변에 선이 N개 붙으면 접점을 변 길이 L에 대해 `L × k / (N+1)` 위치에 두어 12px 이상 벌린다. 접점 하나를 두 선이 공유하지 않는다.
- 두 선이 겹치거나 같은 경로를 달리지 않는다. 평행하면 12px 이상 띄운다. 겹치게 되면 배치가 틀린 것이다.
- 교차가 불가피하면 덜 중요한 선(파선, 반환, 보조)에 반지름 8의 hop을 넣는다. 가로선이 세로선 x=cx를 넘을 때: `H cx-8 a 8,8 0 0,1 16,0 H x2`. 세로선이 가로선을 넘을 때: `a 8,8 0 0,0 0,16`. 둘 다에 넣지 않는다.
- 출발·도착이 아닌 노드 뒤를 지나지 않는다. 우회한다. 우회가 기하학적으로 불가능한 경우에만 파선으로 통과시키고 라벨을 보이는 쪽 끝에 두며, 화살촉은 진짜 목적지에만 붙인다.
- 선택·비동기·반환 흐름은 `class="dashed"`. 파선도 같은 경로 규칙을 따른다. 비동기(응답 없음)는 열린 화살촉 `marker-end="url(#…-open)"`, 반환은 파선이지만 채운 화살촉이다.

**선 라벨.** 14자 이내. 가로 구간 위 또는 세로 구간 옆에 선에서 6px 이상 띄워 둔다. `class="edge-label"`의 흰색 halo가 선을 가린다. 라벨이 자기 선을 덮거나 노드에 걸치면 실패다. 세로 쓰기(`writing-mode`)는 쓰지 않는다.

**영역(zone).** 같은 계층·신뢰 경계의 노드 2개 이상을 `class="zone"` rect로 묶는다. 영역 라벨은 왼쪽 위에 두고 첫 노드 위쪽까지 16px 이상 남긴다(영역 y = 첫 노드 y − 32).

**범례.** 그림 영역 안에 띄우지 않는다. 노드 아래에 hairline을 긋고 그 밑에 가로 한 줄로 둔다. `class="legend"`, H에 48을 더한다. 색을 썼으면 반드시 붙이고, 실선·파선·테두리 굵기만 썼으면 그 종류만 적는다.

**주석(callout).** 본문 도형이 직접 말할 수 없는 한 줄 논평만. `class="callout"` 텍스트를 여백(오른쪽 위·왼쪽 아래)에 두고, 파선 곡선 leader `M x,y Q cx,cy tx,ty`와 반지름 2의 착지 점으로 대상에 잇는다. 실선 leader는 흐름 화살표로 읽힌다. 도형에 붙일 수 있는 이름을 callout으로 대신하지 않는다.

**viewBox.** 콘텐츠 경계 + 여백 12px, 폭·높이 모두 4의 배수. `viewBox="0 0 W H"`와 `style` 속성만 지정하고 `width`·`height` 속성은 쓰지 않는다.

## 유형별 문법

모양이 종류를 말한다. 색으로 종류를 구분하지 않는다.

| 유형 | 문법 |
|---|---|
| **구조** | 상자 = 구성요소, 영역 = 계층·신뢰 경계, 실선 = 호출·참조, 파선 = 선택·비동기. HTTP·외부 호출은 `class="sub"`에 프로토콜·포트. |
| **흐름차트** | 타원(`rx=22`) = 시작·끝, 사각(`rx=4`) = 단계, 마름모 = 결정(출구 3개 이하, 넘으면 마름모를 나눔), 채운 점(`r=4`) = 분기 합류. 위→아래. 결정에서 나가는 화살표는 전부 라벨. 강조는 happy path 또는 가장 중요한 결정 하나. |
| **시퀀스** | 액터 상자를 위에 가로로, 각 액터에서 파선 lifeline이 내려온다. 메시지는 lifeline 사이 가로 화살표, 시간은 위→아래이며 위로 가는 화살표는 없다. 제어를 쥔 구간은 폭 8 활성 막대. 동기 호출 = 실선·채운 화살촉, 반환 = 파선·채운 화살촉, 비동기 = 파선·열린 화살촉. 분기(`alt`/`opt`/`loop`)는 참여 lifeline만 덮는 프레임 rect + 왼쪽 위 탭 + `[guard]`. 프레임은 그림당 1개, 중첩 없음. lifeline 5개·메시지 12개 이하. |
| **상태** | 상태 = 둥근 사각(`rx=8`), 시작 = 채운 점(`r=6`), 끝 = 이중 점(바깥 `r=8` 테두리 + 안 `r=5` 채움). 전이 라벨은 `event [guard] / action`에서 필요한 부분만. 자기 전이는 상태 위로 도는 곡선. 전이 수가 상태 수 × 2를 넘으면 상태 기계 둘이다. "어느 상태에서든"은 화살표를 전부 긋지 않고 주석 한 줄(`* → Error on timeout`). |
| **타임라인** | 가운데 가로 hairline, 시간 단위 눈금과 날짜 라벨은 아래. 사건 = 점(`r=4`), 라벨은 위·아래 교대로 두고 1px 세로 leader로 잇는다. 이정표 = 강조 점(`r=6`) + 굵은 라벨. **간격은 시간에 비례**하게 둔다. 균등하지 않은 간격을 보기 좋게 균등화하지 않고, 너무 빽빽한 구간은 축을 눈에 보이게 끊는다. |
| **스윔레인** | 레인 = 행위자 하나, 왼쪽 여백에 레인 라벨, 구분선은 hairline. 단계는 수행자의 레인 안에만 놓는다(두 레인에 걸친 단계 없음). 레인을 넘는 화살표가 핵심이므로 강조는 결합·지연을 만드는 handoff 하나. 왔다 갔다 하는 화살표는 단계 순서를 바꿔 편다. |
| **포함** | 겹 3~5개, 안쪽으로 갈수록 좁아지는 둥근 사각(`rx=8`), 겹 사이 padding은 가로 24·세로 32로 일정. 바깥은 옅은 테두리, 안쪽으로 갈수록 진하게, 가장 안쪽 하나만 강조. 계층이 아닌 내용은 넣지 않는다. |
| **트리** | 루트 위, 자식 아래(또는 루트 왼쪽). 부모에서 짧은 세로선 → 형제를 잇는 가로 버스 → 각 자식 윗변으로 짧은 세로선. 깊이 4·너비 5 이하. 단계를 건너뛰어 잇지 않는다. 강조는 루트 또는 핵심 잎 하나이지 둘 다는 아니다. |

## 의미 전달

- 색은 보조로만 쓴다. 실선과 파선, 테두리 굵기, 라벨로 의미를 구분한다. 흑백 인쇄에서도 구분이 남아야 한다.
- 그림자, 발광, 그라데이션은 쓰지 않는다. 테두리와 선 종류가 전부다.
- `<title>`은 `<svg>`의 첫 자식이고 60자 이내의 주제 이름이다. `<desc>`는 그림 없이 독자가 알아야 할 내용을 한 문장으로 적는다. 모양 설명("위에 상자 하나, 아래에 셋")이 아니라 내용 설명("게이트웨이가 요청을 인증 서비스로 넘기는 경로")이다. `aria-labelledby`가 둘의 id를 가리키고, id는 그림마다 다른 접두어를 붙인다(`gw-title`, `gw-desc`). 접두어 없는 `title`/`desc` id는 같은 페이지의 두 그림이 서로의 이름을 가져간다.
- 캡션(`<figcaption>` 또는 그림 아래 문단)에 그림이 보여주는 사실을 한 문장으로 적는다. 그림 없이 그 문장만 읽어도 결론이 전달되어야 한다.

## 마크업

아래 형태를 그대로 쓴다. 한 문서에 그림이 여럿이면 marker id, `url(#...)`, `<title>`/`<desc>` id의 접두어를 그림마다 다르게 둔다.

```html
<svg viewBox="0 0 344 140" role="img" aria-labelledby="gw-title gw-desc"
     xmlns="http://www.w3.org/2000/svg"
     style="display:block;width:100%;max-width:344px;height:auto;margin:0 auto">
  <title id="gw-title">요청 경로</title>
  <desc id="gw-desc">클라이언트 요청이 Gateway를 한 번 지나 인증 서비스로 전달되는 경로</desc>
  <style>
    text { font-family: -apple-system, "Segoe UI", "Noto Sans KR", "Apple SD Gothic Neo", sans-serif; font-size: 14px; fill: #16191d; }
    .sub { font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; font-size: 12px; fill: #5b6470; }
    .node rect, .node circle, .node polygon { fill: #fff; stroke: #16191d; stroke-width: 1.2; }
    .node.strong rect { stroke-width: 2.4; }
    .node.muted rect { stroke: #5b6470; stroke-dasharray: 4 3; }
    .zone rect { fill: #f6f8fa; stroke: #d7dce3; stroke-width: 0.8; }
    .zone text { font-size: 12px; fill: #5b6470; }
    line, path.edge { stroke: #16191d; stroke-width: 1.2; fill: none; }
    .dashed { stroke-dasharray: 5 4; }
    .edge-label { font-size: 12px; fill: #5b6470; paint-order: stroke; stroke: #fff; stroke-width: 3; stroke-linejoin: round; }
    .legend line.rule { stroke: #d7dce3; stroke-width: 0.8; }
    .legend text { font-size: 12px; fill: #5b6470; }
    .callout { font-size: 12px; font-style: italic; fill: #5b6470; }
    .callout-leader { stroke: #5b6470; stroke-width: 1; stroke-dasharray: 4 3; fill: none; }
  </style>
  <defs>
    <marker id="gw-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="#16191d" />
    </marker>
    <marker id="gw-open" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10" fill="none" stroke="#16191d" stroke-width="1.4" />
    </marker>
  </defs>
  <line x1="138" y1="70" x2="206" y2="70" marker-end="url(#gw-arrow)" />
  <text class="edge-label" x="172" y="58" text-anchor="middle">HTTPS</text>
  <g class="node">
    <rect x="12" y="48" width="120" height="44" rx="4" />
    <text x="72" y="70" text-anchor="middle" dominant-baseline="central">클라이언트</text>
  </g>
  <g class="node strong">
    <rect x="212" y="48" width="120" height="44" rx="4" />
    <text x="272" y="70" text-anchor="middle" dominant-baseline="central">Gateway</text>
  </g>
</svg>
```

호스트별 저장:
- **Markdown** — 위 `<svg>` 요소 앞에 `<?xml version="1.0" encoding="UTF-8"?>`를 붙여 `이름.svg`로 저장하고(`xmlns` 필수, 문자 `&`는 `&amp;`) `![캡션](이름.svg)`로 넣는다. `writing-for-humans`의 build.py가 HTML에서는 이 파일을 `<figure class="diagram">` 인라인 SVG로, Word에서는 옆의 `이름.png`로 바꾼다.
- **HTML을 손으로 쓸 때** — `<figure class="diagram">` 안에 인라인으로 넣는다.
- **Word** — `이름.svg` 옆에 브라우저에서 2배 배율로 스크린샷한 `이름.png`를 둔다. Office의 SVG 렌더러는 `<style>`·`paint-order`·`rgba()` 지원이 확인되지 않았고 `rgba()`는 검정으로 칠하는 것이 보고되어 있으므로 삽입은 PNG로 한다.

## 검수

1. **정적 검사** — `python3 <이 스킬 경로>/scripts/check.py <파일.svg>`가 아무것도 출력하지 않는다(HTML 인라인이면 `<svg>…</svg>` 블록을 임시 `.svg`로 잘라 검사한다). 접근성 계약, self-contained, 모바일 폭, 4px 격자, 글자 폭 대비 노드 폭, 선 라벨과 노드의 겹침, 예산을 잡는다.
2. **브라우저 audit** — 그림이 들어 있는 페이지(또는 `.svg` 파일 자체)를 열고 아래 함수의 반환값이 빈 배열이다. 실제 글리프 폭으로 잘림·겹침을 다시 잰다.
3. **이미지** — 각 SVG를 selector로 스크린샷해 노드와 화살표가 의도한 관계를 그리는지, 선이 다른 노드 뒤를 지나지 않는지, 라벨이 선에서 떨어져 있는지 직접 본다. 연결선 간격 6px는 렌더로만 판정된다.
4. **360px** — viewport 360px에서 SVG의 `getBoundingClientRect().width`를 재고, `폰트 × 그 폭 / W ≥ 11`을 확인한 뒤 스크린샷으로 글자가 읽히는지 본다.

```js
(() => {
  const issues = [];
  const box = (el) => el.getBoundingClientRect();
  const inside = (a, b, pad) =>
    a.left >= b.left + pad && a.right <= b.right - pad && a.top >= b.top + pad && a.bottom <= b.bottom - pad;
  const hits = (a, b) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
  for (const svg of document.querySelectorAll("svg")) {
    const name = svg.querySelector("title")?.textContent || svg.getAttribute("aria-label") || svg.id || "(제목 없는 svg)";
    const frame = box(svg);
    const texts = [...svg.querySelectorAll("text")].filter((t) => t.textContent.trim());
    for (const t of texts) {
      if (!inside(box(t), frame, -0.5)) issues.push({ svg: name, issue: "svg 밖으로 잘림", text: t.textContent });
    }
    for (const g of svg.querySelectorAll("g.node")) {
      const shape = g.querySelector("rect, circle, ellipse, polygon, path");
      if (!shape) continue;
      for (const t of g.querySelectorAll("text")) {
        if (!inside(box(t), box(shape), 3)) issues.push({ svg: name, issue: "노드 도형을 넘음", text: t.textContent });
      }
    }
    for (let i = 0; i < texts.length; i++) {
      for (let j = i + 1; j < texts.length; j++) {
        if (hits(box(texts[i]), box(texts[j])))
          issues.push({ svg: name, issue: "텍스트 겹침", text: `${texts[i].textContent} / ${texts[j].textContent}` });
      }
    }
    for (const t of svg.querySelectorAll("text.edge-label")) {
      for (const g of svg.querySelectorAll("g.node")) {
        if (hits(box(t), box(g))) issues.push({ svg: name, issue: "선 라벨이 노드와 겹침", text: t.textContent });
      }
    }
  }
  return issues;
})();
```

`노드 도형을 넘음`은 노드 폭 부족이다. 텍스트 폭을 다시 재고 폭과 그 열 이후의 좌표를 함께 늘린다. `텍스트 겹침`과 `선 라벨이 노드와 겹침`은 간격 부족이다. 라벨을 선의 반대쪽으로 옮기거나 행 간격을 늘린다.

## 출처

연결선 규칙, 접점 분산, hop, 예산, remove test, 글자 폭 계산, 유형별 문법, `<title>`/`<desc>` 계약, "규칙은 checker로 강제한다"는 원칙(ADR 0005), Office의 `rgba()` 동작은 [cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design) `dcd9317`(MIT, Copyright (c) 2025 Cathryn Lavery)에서 가져와 이 스킬의 self-contained·모바일 조건에 맞게 옮긴 것이다. 브랜드 토큰, 웹폰트, 39개 유형 참조, Mermaid·draw.io import, 애니메이션은 가져오지 않았다.
