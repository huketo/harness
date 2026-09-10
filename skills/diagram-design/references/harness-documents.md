# 우리 문서에 적용하기

`writing-for-humans`의 Markdown·HTML·Word 문서에 그림을 넣을 때 읽는다. 독립적인 브랜드·슬라이드·웹용 그림은 원본 디자인 절차를 그대로 사용한다.

## 소유권과 우선순위

본문 장르·머리말·테마·캡션 위치는 [문서 형식](../../writing-for-humans/FORMATS.md)이 소유한다. 의미 패턴·유형별 문법·시각적 위계는 diagram-design이 소유한다. 이 문서는 문서에 들어가는 그림의 스타일과 출력만 조정한다. 모바일 요구가 있으면 [mobile.md](mobile.md)를 함께 읽는다.

이 분기에서는 아래 오프라인 폰트·문서 테마·정적 출력 규칙이 원본의 Google Fonts, 기본 브랜드 확인, HTML 페이지 외곽, export의 폰트 import보다 우선한다. 이미 선택된 문서 테마는 명시된 디자인 입력이므로 기본 브랜드를 다시 묻거나 설치된 style-guide.md를 바꾸지 않는다. 원본을 축약한 별도 도형 문법은 만들지 않는다.

## 문서 테마 적용

1. 문서의 장르·테마·스타일을 [FORMATS.md](../../writing-for-humans/FORMATS.md)에서 정한다. 보고·설계 문서는 기존 기본값을 사용한다.
2. [html/shell.html](../../writing-for-humans/html/shell.html)의 선택된 테마에서 값을 읽어 그림 HTML에 구체적인 hex 값으로 넣는다. 그림은 호스트 CSS 변수나 외부 스타일이 없어도 같은 의미로 읽혀야 한다.
3. 다음 역할 매핑을 적용한다. 색상 값의 정본은 shell.html이며 아래에는 값을 복제하지 않는다.

| diagram-design 역할 | 문서 토큰 |
|---|---|
| paper | --bg |
| paper-2, accent-tint | --panel |
| ink | --ink |
| muted, soft | --muted |
| rule, rule-solid | --line |
| accent, link | --accent |
| node-name | --font |
| title, editorial aside | --heading-font; 명조가 필요하면 --serif |
| 기술 sublabel | --mono; 한글은 --font fallback |

강조색은 여전히 1~2개 초점에만 쓴다. 외부 호출 여부는 프로토콜 라벨과 선 종류로도 드러내며, link와 accent가 같은 색이라는 이유로 모든 외부 호출을 강조하지 않는다. 타입 태그·기술 부제·영역·여백으로 원본의 위계를 유지한다. 읽히지 않는 태그는 작게 남겨두는 대신 이름과 합치거나 캡션으로 옮긴다.

시스템 폰트를 사용하고 Google Fonts 링크·CSS import·외부 이미지·스크립트를 넣지 않는다. 서로 다른 기기의 시스템 폰트는 글리프 폭이 다를 수 있으므로 최종 환경에서 확인한다. 웹폰트 충실도가 필요한 독립 브랜드 출력과 이 문서용 출력은 별도 산출물이다.

## 제작과 내보내기

1. 해당 유형 레퍼런스와 가까운 원본 템플릿을 읽고 그림 HTML을 만든다. [번들 갤러리](../assets/harness-gallery.html)는 한국어·문서 테마·좁은 폭을 적용한 예제이며 임의 내용에 대한 통과 보증은 아니다.
2. HTML의 그림에는 하나의 독립 SVG를 둔다. SVG의 style은 그림 ID 아래로 범위를 제한하거나 각 요소의 presentation 속성을 사용한다. `text`, `rect`, `.node` 같은 전역 선택자는 다른 인라인 그림에 영향을 주므로 쓰지 않는다. 모든 ID와 `url(#…)` 참조는 그림 접두어로 묶는다.
3. SVG에는 `xmlns`, `viewBox`, `role="img"`, 제목과 설명을 가리키는 `aria-labelledby`를 둔다. `<title>`을 첫 자식으로 두고 `<desc>`에 내용상 결론을 적는다. 필요한 스타일과 marker는 SVG 내부에 둔다. `display:block;width:100%;max-width:<설계 폭>px;height:auto`로 표시하고 최소 폭을 강제하지 않는다.
4. `python3 <diagram-design>/scripts/self_check.py 그림.html`과 모바일 검수를 수행한다. caption은 그림 없이도 결론을 전달한다. 문서 제목·메타데이터·요약 카드는 본문이 이미 소유하므로 SVG에 중복해서 넣지 않는다.
5. [export.md](export.md)의 SVG 추출·XML escaping·Office 색상 정규화를 사용하되, 이 분기에서는 Google Fonts `@import`를 추가하지 않는다. 그림 HTML에서 선택한 SVG만 추출하여 같은 이름의 `.svg`로 저장한다. 여러 SVG가 있으면 ID로 대상을 명시하고 각각 내보낸다.
6. 본문 Markdown은 `![사실을 설명하는 캡션](그림.svg)`로 참조한다. `writing-for-humans/scripts/build.py`가 기존 필터로 SVG를 인라인한다. 그림을 수정할 때는 그림 HTML을 고치고 다시 내보낸다.
7. Word가 필요하면 같은 HTML의 SVG 요소를 브라우저에서 2배 배율로 캡처하여 `.svg` 옆에 같은 이름의 `.png`를 둔다. 브라우저는 `document.fonts.ready` 뒤 캡처한다. 문서 형식의 PNG 요구는 export 요청으로 취급한다. 브라우저 도구가 있으면 그 도구를 사용하며 Python Playwright만을 필수 설치로 간주하지 않는다.

본문 Markdown은 문장의 정본, 그림 HTML은 그림의 정본이다. SVG·PNG·문서 HTML·Word는 파생 산출물이다. SVG를 별도로 편집하여 두 원본을 만들지 않는다.

## 삽입 뒤 검수

독립 예제에서 통과해도 문서의 figure 여백 때문에 더 축소될 수 있다. 문서를 빌드한 뒤 360px과 1280px에서 실제 SVG 폭, 모든 글자의 화면상 크기, 잘림·겹침·연결 의미를 다시 확인한다. 모바일 판정과 증거 기록은 [mobile.md](mobile.md)가 소유한다. 두 그림을 같은 페이지에 넣는 경우에도 제목 ID와 CSS가 서로 간섭하지 않아야 한다.

문서 HTML에서 `document.scripts.length`가 0이고 `performance.getEntriesByType('resource')`가 빈 배열인지 확인한다. 이 검사는 외부 폰트를 막는 문서용 계약이며 일반 브랜드 출력의 허용 범위를 바꾸지 않는다. PNG 존재와 Word 패키징 확인은 실제 Word 앱에서의 레이아웃 검증과 구분하여 보고한다.

