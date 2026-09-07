# SVG 다이어그램

보고서의 그림은 인라인 SVG로 그린다. 텍스트가 문서에 남아 검색·복사되고, 외부 파일 요청이 없고, 좌표를 직접 계산하므로 렌더 결과를 프로그램으로 검사할 수 있다.

## 그릴 것과 그리지 않을 것

구조(무엇이 무엇을 포함·참조하는가), 흐름(호출·데이터 이동 순서), 시간 관계(무엇이 언제 일어나는가), 상태 전이를 그린다.

값의 비교, 목록, 조건 대응은 표로 적는다. 문장 두 개로 정확히 전달되는 내용에 다이어그램을 만들지 않는다.

## 좌표 규칙

좌표를 먼저 정하고 마크업을 쓴다. 자동 배치가 없으므로 겹침과 잘림은 전부 계산 실수다.

- **격자에 배치한다.** 노드 폭·높이와 열·행 간격을 상수로 정해 모든 노드에 같은 값을 쓴다. 기준값: 노드 높이 44, 열 간격 200, 행 간격 90.
- **텍스트 폭을 추정해 노드 폭을 정한다.** 13px 기준 라틴 문자·숫자·공백은 글자당 약 7px, 한글은 글자당 약 13px. 노드 폭 = 추정 텍스트 폭 + 좌우 여백 각 12px 이상. 두 줄이 필요하면 `<tspan>`으로 나누고 노드 높이를 24px 늘린다.
- **중앙 정렬로 좌표를 하나만 계산한다.** `<text text-anchor="middle" dominant-baseline="central">`에 노드 중심 좌표를 준다.
- **화살표는 노드 경계에서 시작하고 끝낸다.** 중심 좌표에서 노드 폭·높이의 절반을 뺀 지점에 6px 간격을 더한다. 화살촉이 노드 테두리를 덮으면 관계가 어느 노드에 붙는지 이미지에서 흐려진다.
- **viewBox는 콘텐츠 경계 + 여백 12px.** `viewBox="0 0 W H"`만 지정하고 `width`·`height` 속성은 쓰지 않는다. 크기는 `template.html`의 `.diagram svg` 규칙이 정한다.
- **viewBox 폭 W는 720 이하로 둔다.** 데스크톱에서 본문 폭 780px에 거의 1:1로 들어가고, 휴대폰에서는 `.diagram`이 최소 480px로 가로 스크롤되어 축소 배율이 0.67 이상 유지된다. W가 더 크면 13px 텍스트가 휴대폰에서 읽히지 않는다. 노드가 4열을 넘으면 행을 나눠 세로로 쌓고 H를 늘린다.
- **`<g class="node">` 안에 도형을 먼저, 텍스트를 뒤에 둔다.** audit이 이 구조로 텍스트가 도형을 넘는지 검사한다.
- **선 위에 놓는 라벨에는 halo를 준다.** `class="edge-label"`이 `paint-order: stroke`와 흰색 stroke로 선을 가린다.

## 의미 전달

- 색은 보조로만 쓴다. 실선과 파선, 테두리 굵기, 라벨로 의미를 구분한다. 흑백 인쇄에서도 구분이 남는지 확인한다.
- 색을 쓸 때는 범례를 붙인다. 범례 없는 색은 독자가 해석할 수 없다.
- `<figcaption>`에 다이어그램이 보여주는 사실을 한 문장으로 적는다. 그림 없이 그 문장만 읽어도 결론이 전달되어야 한다.
- `<svg role="img" aria-label="...">`로 그림의 내용을 적는다. audit 결과에 이 라벨이 식별자로 쓰인다.

## 마크업

`marker`와 `.node`, `.edge-label` 스타일은 `template.html`에 이미 들어 있다. 다이어그램은 아래 형태로 쓴다.

```html
<figure class="diagram">
  <svg viewBox="0 0 460 140" role="img" aria-label="요청이 게이트웨이를 지나 인증 서비스로 전달되는 경로">
    <g class="node">
      <rect x="12" y="48" width="120" height="44" rx="4" />
      <text x="72" y="70" text-anchor="middle" dominant-baseline="central">클라이언트</text>
    </g>
    <g class="node">
      <rect x="212" y="48" width="120" height="44" rx="4" />
      <text x="272" y="70" text-anchor="middle" dominant-baseline="central">Gateway</text>
    </g>
    <line x1="138" y1="70" x2="206" y2="70" marker-end="url(#arrow)" />
    <text class="edge-label" x="172" y="58" text-anchor="middle">HTTPS</text>
  </svg>
  <figcaption>클라이언트 요청은 Gateway를 한 번 통과한 뒤 인증 서비스로 전달된다.</figcaption>
</figure>
```

## audit

렌더한 페이지에서 아래 함수를 실행한다. 반환값이 빈 배열이어야 한다. 빈 배열은 잘림·넘침·겹침이 없다는 뜻이고, 관계가 맞게 그려졌는지는 스크린샷 이미지로 따로 판단한다.

```js
(() => {
  const issues = [];
  const box = (el) => el.getBoundingClientRect();
  const inside = (a, b, pad) =>
    a.left >= b.left + pad && a.right <= b.right - pad && a.top >= b.top + pad && a.bottom <= b.bottom - pad;
  const hits = (a, b) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
  for (const svg of document.querySelectorAll("svg")) {
    const name = svg.getAttribute("aria-label") || svg.id || "(라벨 없는 svg)";
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
  }
  return issues;
})();
```

`노드 도형을 넘음`은 노드 폭 부족이다. 텍스트 폭 추정을 다시 하고 폭과 그 열 이후의 좌표를 함께 늘린다. `텍스트 겹침`은 간격 부족이거나 라벨 위치가 노드와 충돌한 것이다. 라벨을 선의 반대쪽으로 옮기거나 행 간격을 늘린다.
