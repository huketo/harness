# awesome-interface 비교 평가 사례

이 문서는 `suite.json`(스위트 `awesome-interface-compare`, version 1)의 사례 설계를 설명합니다. 사람과 판정 설계를 위한 문서이므로 평가받는 에이전트에게는 보이지 않습니다. 실행기는 스킬의 `evals/` 디렉터리를 작업공간에 복사하지 않고(`scripts/skill-eval/lib/schema.ts`의 계약), fixture 디렉터리만 작업공간으로 복사합니다. 따라서 심은 결함의 정답 목록은 이 문서와 `suite.json`의 `expectations`에만 둡니다.

## 비교 구조

- arm `none`은 스킬 없이 실행합니다. arm `ai`는 이 저장소의 `skills/awesome-interface`를 씁니다. arm `emil-<skill>`은 `emilkowalski/skills`의 `skills/<skill>`을 커밋 `f1090bec277140d02ed202440185ad9d02ac1490`에서 읽습니다.
- 모든 사례에 `none`과 `ai`가 들어가고, upstream 스킬 16개는 각각 한 사례 이상에서 비교됩니다. `emil-design-eng`만 네 사례(`popover-motion`, `card-polish`, `new-screen`, `settings-review`)에 들어갑니다.
- `consent-copy-ko`는 upstream에 대응 스킬이 없어서 `none`과 `ai`만 비교합니다. 범위가 작은 일상 과제(문구만 수정)를 하나 포함하려는 목적도 있습니다.
- 프롬프트는 사람이 실제로 쓸 법한 증상과 범위만 말합니다. 심은 결함 대부분은 프롬프트에 나오지 않으며, 에이전트가 직접 찾아야 합니다.

## 가설과 사례의 연결

| 가설 | 검증하는 사례 |
| --- | --- |
| `break-ui`의 최악 데이터 카탈로그와 스키마 기반 값 선택이 `ai`의 `references/stress-test.md`보다 실제 깨짐을 더 많이 찾는다. | `stress-member-list` |
| `mobile-native`의 증상 표(100dvh/svh, 탭 하이라이트, theme-color, 당겨서 새로고침, 길게 누르기 선택)가 `ai`에 없다. | `mobile-shell` |
| `animation-performance`의 원인 목록(프레임마다 상태로 다시 그리기, 부모 CSS 변수로 자식 transform 구동)이 `ai`보다 진단을 잘한다. | `jank-drawer` |
| `remove-animations`의 제거 위험(제거 후 보이지 않는 요소, unmount 타이밍)과 '남긴 것' 보고가 `ai`에 없다. | `over-animated` |
| 편입된 `animate`, `emil-design-eng`, `review-animations`, `apple-design`은 `ai`와 차이가 작다. | `popover-motion`, `review-motion-patch`, `drag-sheet`, `card-polish`, `new-screen`, `settings-review` |
| `animate-expo`, `write-swift`, `ask-sonner`, `pick-ui-library`, `animation-vocabulary`는 `ai` 범위 밖이다. `ai`가 해가 되는지(웹 지침을 엉뚱하게 적용) 무관한지 본다. | `expo-press-sheet`, `swift-race`, `sonner-darkmode`, `library-pick`, `motion-name` |
| (편입하지 않은 나머지) `improve-animations`, `find-animation-opportunities`, `prototype`과 `ai`의 대응 기능을 비교한다. | `motion-audit`, `motion-opportunities`, `pricing-variants` |

기대 문장은 가설이 맞는지와 상관없이 사람에게 좋은 결과인지를 묻도록 썼습니다. 예를 들어 `mobile-shell`은 특정 스킬의 증상 표를 따랐는지가 아니라, 사용자가 말하지 않은 휴대폰 문제를 찾아 고쳤는지를 봅니다.

## 공통 판정 메모

- `render` 검사는 결과물을 바꾸는 UI 사례에만 둡니다. 검토만 하는 사례는 fixture가 그대로 남아야 하므로 렌더 결과로 arm을 구별할 수 없어서 넣지 않았습니다.
- 모든 fixture의 `index.html`은 커밋 시점에 320·390·1280px, 라이트·다크에서 콘솔 오류와 가로 넘침이 없습니다. 콘솔 오류 자체를 결함으로 심은 사례는 없습니다. `stress-member-list`의 넘침과 예외는 최악의 데이터를 넣어야 드러납니다.
- `render`의 `no-horizontal-overflow`는 문서 전체의 가로 스크롤만 봅니다. 카드 안에서 잘리거나 겹치는 문제는 판정자가 스크린숏으로 판단해야 합니다.
- `present`/`absent` 정규식은 여러 올바른 해법을 통과시키도록 넓게 썼습니다. 정규식이 통과해도 수정이 맞는지는 판정자가 봐야 합니다.
- 파일 glob(`*.css`, `**/*`, `**/*.tsx`, `Sources/**`)은 작업공간 루트 기준 POSIX 경로입니다. `*.css`는 루트 파일만, `**/*`는 하위 디렉터리까지 맞는다고 가정합니다. 채점기의 glob 구현이 이 가정과 다르면 해당 검사의 결과를 다시 확인해야 합니다.

## 사례별 설계

### stress-member-list

- 측정하려는 것: 컴포넌트를 고치지 않은 채 최악의 데이터를 만들어 실제로 깨지는 곳을 얼마나 많이, 얼마나 근거 있게 찾는지 봅니다.
- fixture `member-list`: `member-list.js`(컴포넌트), `styles.css`, `demo-data.js`, `schema.js`(데이터 계약), `index.html`(미리보기), 아바타 SVG 3개입니다. 데모 데이터로는 모든 폭에서 깨지지 않습니다.
- 심은 결함:
  1. `.email`이 `white-space: nowrap`이고 `.who`에 `min-width: 0`이나 줄바꿈 규칙이 없습니다. 긴 이메일은 320px에서 문서를 넘칩니다(긴 이메일 한 건으로 약 213px 넘침을 확인했습니다).
  2. `initials()`가 `name.split`을 호출해서 이름이 없는 회원(스키마상 optional)에서 `TypeError`를 던지고 목록 전체가 그려지지 않습니다. 이모지로 시작하는 이름은 서로게이트 쌍의 반쪽을 씁니다(현재 `.initials`는 `display: none`이라 보이지 않지만 예외는 그대로 발생합니다).
  3. `title`이 없으면 "undefined"가 표시되고, `avatar`가 없으면 `src="undefined"`로 깨진 이미지가 나옵니다. 아바타 이미지에는 오류 대체 처리가 없습니다.
  4. `lastActive()`가 손으로 만든 문자열이어서 null이면 "20000 days ago" 같은 값, 미래 시각이면 "-3 days ago", 방금이면 "0 days ago"가 나옵니다.
  5. 모든 값을 `innerHTML`로 넣기 때문에 이름의 HTML이 해석됩니다(`<img onerror>` 실행을 확인했습니다).
  6. 헤더가 `${n} members`라서 "1 members"가 나오고, 0명일 때 빈 상태가 없습니다. 좌석 수에 천 단위 구분이 없습니다.
  7. `.name`이 `height: 18px; overflow: hidden`이라 겹친 발음 구별 기호(베트남어 등)와 두 줄 이름이 잘립니다. 상태 배지는 `nowrap`이라 긴 이름과 경쟁합니다.
  8. 행 동작 버튼(•••)이 `opacity: 0`이고 `:hover`에서만 보입니다. 터치 기기에서는 보이지 않고, 키보드 포커스 때도 보이지 않습니다.
  9. 아바타에 `object-fit`이 없어 비율이 다른 업로드 이미지가 찌그러집니다(스키마 주석에 "any aspect ratio"가 있습니다).
- 기계 검사의 한계: `component-untouched`는 컴포넌트를 고치지 않았는지만 봅니다. 이스케이프 문제를 포함한 발견의 수와 정확성은 판정자가 최종 응답과 작업공간의 시험 파일로 판단합니다. 렌더링을 실제로 했는지는 transcript로 확인해야 합니다.

### mobile-shell

- 측정하려는 것: 사용자가 말한 증상 두 가지(탭바 가림, 남는 눌린 색) 외에 휴대폰에서 웹 티가 나는 문제를 얼마나 찾아 고치는지 봅니다.
- fixture `mobile-shell`: 장보기 메모 PWA 셸(`index.html`, `app.css`, `app.js`, `manifest.webmanifest`)입니다.
- 심은 결함:
  1. `.app { height: 100vh }`라서 주소창이 나타나고 사라질 때 탭바가 밀립니다(사용자가 말함).
  2. `.icon-btn`, `.chip`, `.row`, `.add`, `.tab`의 `:hover`가 hover 미디어 쿼리 없이 걸려서 터치 뒤 남습니다(사용자가 말함).
  3. 입력창 글자가 13px이어서 iOS가 입력 시 확대합니다.
  4. `-webkit-tap-highlight-color`가 없어 탭할 때 회색·파란 깜빡임이 생깁니다.
  5. 뷰포트 메타에 `viewport-fit=cover`가 없고 탭바에 `env(safe-area-inset-bottom)`이 없습니다.
  6. `theme-color` 메타가 없고 manifest의 `theme_color`는 흰색 고정이라 다크 모드 상태 표시줄과 맞지 않습니다.
  7. `overscroll-behavior`가 없어 목록 스크롤이 문서로 이어지고 당겨서 새로고침이 걸립니다.
  8. 버튼 글자에 `user-select: none`이 없어 길게 누르면 글자가 선택됩니다.
  9. 눌렀을 때의 `:active` 피드백이 없습니다.
- 함정: `user-scalable=no`나 `maximum-scale=1`로 확대를 막는 해법은 접근성 회귀이므로 `zoom-not-disabled`가 실패시킵니다.
- 기계 검사의 한계: 기계 검사는 렌더와 확대 차단 여부만 봅니다. 뷰포트 높이와 hover 처리는 해법이 여러 가지(CSS 단위, JS 높이 계산, 미디어 쿼리)이므로 판정자가 판단합니다. 4~8번 발견과 데스크톱 회귀 여부는 판정자가 diff로 판단합니다. 실제 기기 확인은 어느 arm도 할 수 없으므로, 확인했다고 주장하면 기대 문장 5번이 실패해야 합니다.

### jank-drawer

- 측정하려는 것: 버벅임의 실제 원인을 진단하고 동작을 보존하며 고치는지 봅니다.
- fixture `jank-drawer`: 프로젝트 240개가 든 서랍(`index.html`, `drawer.css`, `drawer.js`)입니다.
- 심은 결함:
  1. 서랍이 `width: 0 → 320px`로, 본문이 `margin-left`로 열립니다. 레이아웃 속성 애니메이션이 페이지 전체를 매 프레임 다시 배치합니다.
  2. `.content`, `.drawer`, `.backdrop`에 `transition: all`이 있습니다.
  3. 서랍의 `box-shadow`가 전환됩니다(매 프레임 다시 그리기).
  4. 배경의 `backdrop-filter: blur(36px)`가 전환됩니다(큰 반경의 블러).
  5. 끌기 거리를 `document.documentElement`의 `--drag-x`로 쓰고, 서랍과 240개 `li`가 이 변수를 읽습니다. 루트 변수 변경이 문서 전체의 스타일 재계산을 일으킵니다.
  6. `pointermove`마다 `setState → render()`가 240개 목록을 `innerHTML`로 다시 만듭니다(React의 프레임마다 setState와 같은 구조입니다).
- 부수 결함: 닫힌 서랍은 `width: 0; overflow: hidden`일 뿐이라 안의 버튼과 항목에 키보드 포커스가 갑니다. 판정자는 이 문제를 찾았으면 가산할 수 있지만 기대 문장에는 넣지 않았습니다.
- 기계 검사의 한계: 렌더만 기계로 봅니다. 레이아웃 속성 애니메이션을 없앴는지, 프레임마다 다시 그리는 문제를 고쳤는지는 판정자가 diff로 봅니다.

### over-animated

- 측정하려는 것: 필요 없는 모션을 가려 줄이되, 제거 때문에 생기는 회귀를 피하는지 봅니다.
- fixture `over-animated`: 주문 대시보드(`index.html`, `styles.css`, `app.js`)입니다.
- 줄여야 할 모션: 통계 숫자 카운트업(업무 정보), 필터를 바꿀 때마다 반복되는 행 순차 등장(90ms 간격), 표 행 hover 확대, 통계 카드 hover 들림과 확대, 탭 밑줄의 튀는 곡선(500ms, `left`·`width`), `/` 단축키로 여는 검색 팔레트의 400ms 튀어나오는 등장, 제목 등장.
- 제거 위험(심은 함정):
  1. 제목 `.reveal`과 통계 카드 `.stat`은 `opacity: 0`에서 시작합니다. 애니메이션만 지우고 시작 상태를 남기면 보이지 않습니다. 통계 카드는 IntersectionObserver가 `is-visible`을 붙여야 보입니다.
  2. 상세 패널 닫기가 `transitionend`를 기다려 `hidden`을 설정하고 포커스를 옮깁니다. 전환을 지우면 이 이벤트가 오지 않아 패널이 숨겨지지 않습니다.
  3. 검색 팔레트가 등장 길이에 맞춘 `setTimeout(…, 400)`으로 입력창에 포커스합니다. 등장을 지우면 이 지연도 지워야 합니다.
- 남겨야 할 것: 주석에 2025-08 사용성 테스트 결과로 기록된 체크 표시 그리기 모션(`.saved .tick`)과 짧은 토스트 페이드입니다. 상세 패널의 350ms 슬라이드는 유지와 축소가 모두 타당합니다.
- 기계 검사의 한계: 기록된 체크 표시 모션은 이유를 밝히면 바꿀 수 있으므로(기대 문장 4번) 기계로 보존을 강제하지 않습니다. 요소가 보이는지는 스크린숏으로, 패널 닫기와 포커스 타이밍은 diff로 판정자가 확인해야 합니다. 렌더 검사의 스크린숏은 로드 직후라 IntersectionObserver 이후 상태와 다를 수 있습니다.

### popover-motion

- 측정하려는 것: 애니메이션이 없는 메뉴에 열림·닫힘 모션을 더할 때의 품질과, `hidden` 속성 기반 토글에 닫힘 모션을 붙이는 구현의 정확성을 봅니다.
- fixture `popover`: 위쪽 공유 메뉴(아래로 열림, 오른쪽 정렬)와 아래쪽 더보기 메뉴(위로 열림, 오른쪽 정렬)입니다. 키보드 조작(첫 항목 포커스, 화살표, Esc 후 포커스 복귀, 바깥 클릭 닫기)이 이미 있습니다.
- 쟁점: 기준점이 메뉴마다 달라야 합니다(`top right`와 `bottom right`). `hidden`을 바로 설정하면 닫힘 모션이 보이지 않으므로 닫힘 처리 방식을 바꿔야 하며, 이때 닫히는 메뉴의 항목에 포커스가 남거나 빠른 재열기에서 상태가 꼬이는 회귀가 생기기 쉽습니다. `scale(0)`, `ease-in`, 긴 길이, 움직임 감소 누락이 흔한 실수입니다.
- 기계 검사의 한계: 렌더만 기계로 봅니다. 시작 크기와 곡선은 여러 선택이 타당하므로 판정자가 봅니다. 움직임 감소 처리는 CSS 미디어 쿼리와 JS `matchMedia` 모두 타당하므로 판정자가 봅니다. 빠른 재열기와 포커스는 렌더 검사가 상호작용하지 않으므로 판정자가 코드로 판단해야 합니다.

### review-motion-patch

- 측정하려는 것: 모션 변경 패치를 검토할 때 실제 회귀를 정확히 짚고, 도입된 문제와 기존 문제를 구분하는지 봅니다.
- fixture `motion-patch`: 기준 코드 `toast.css`, `toast.js`와 `change.patch`입니다. 패치는 `git apply --check`로 기준 코드에 깨끗이 적용됩니다.
- 패치가 도입한 문제:
  1. 등장이 `scale(0)`에서 시작하고 `ease-in` 500ms로 느려졌습니다. `transform-origin: center`입니다.
  2. `prefers-reduced-motion` 블록을 삭제했습니다.
  3. 쌓임 위치를 `--offset` transform 대신 `style.bottom`으로 바꾸고 `transition: all`을 걸어 레이아웃 속성을 애니메이션합니다.
  4. 등장이 transition에서 `@keyframes`(fill `both`)로 바뀌었습니다. 등장과 닫힘이 서로 다른 메커니즘을 쓰게 되어, 등장 중 닫기 같은 중단 동작을 예측하기 어려워졌습니다. 이 항목은 브라우저에서 확인하지 않은 설계 위험이므로, 지적한 arm에는 근거를 요구합니다.
  5. 제거가 `transitionend` 대신 고정 `setTimeout(500)`에 기댑니다.
  6. 오류 토스트에 무한 흔들림(`infinite`)을 추가했습니다. 선택자 우선순위 때문에 열린 상태에서는 등장 애니메이션에 덮이고 닫힐 때 흔들리는 엉뚱한 동작도 생깁니다.
- 좋은 변경: 닫히는 토스트에 `pointer-events: none`을 둔 것은 개선입니다. 이것을 문제로 지적하면 정확성 점수를 깎습니다.
- 기존 문제(패치와 무관): 토스트 컨테이너에 `role="status"`·`aria-live`가 없고, hover 중 자동 닫힘을 멈추지 않습니다. 이것을 패치 판정의 근거로 삼으면 기대 문장 4번이 실패합니다.
- 기계 검사의 한계: 기존 fixture 파일의 무변경만 기계로 봅니다. 지적의 위치와 근거, 판정의 타당성은 판정자가 봅니다.

### motion-audit

- 측정하려는 것: 여러 파일에 흩어진 모션을 감사하고, 다른 사람이 따라 할 수 있는 우선순위 계획을 쓰는지 봅니다. 코드를 고치지 않아야 합니다(계획 문서를 새 파일로 남기는 것은 허용합니다).
- fixture `motion-app`: 팀 일정 앱(`index.html`, `styles/base.css`, `styles/components.css`, `js/menu.js`, `js/tabs.js`, `js/modal.js`)입니다.
- 심은 결함:
  1. 공통 곡선 변수 `--ease: ease-in`을 드롭다운, 모달, 탭 표시줄, 버튼이 씁니다.
  2. 모달이 `scale(0)`에서 500ms로 등장하고, 포커스를 `setTimeout(500)`으로 늦춥니다. 닫힘 모션은 없습니다.
  3. 드롭다운이 600ms로 등장하며 닫힘 모션과 기준점이 없습니다.
  4. 탭 표시줄이 `left`·`width`를 애니메이션합니다.
  5. 탭을 바꿀 때마다 일정 목록이 120ms 간격으로 순차 등장합니다(이번 주 탭은 24개라 약 3초).
  6. 토스트가 `bottom`을 keyframes로 애니메이션하고, 다시 띄울 때 강제 리플로로 재시작합니다(중단 불가).
  7. 버튼에 `transition: all`과 hover 들림이 있으며 hover 가능 기기로 제한하지 않았고, 눌림 피드백이 없습니다.
  8. 앱 어디에도 `prefers-reduced-motion`이 없습니다.
- 기록된 결정: 첫 방문 안내 그림의 4초 등장은 주석에 브랜드 팀 요청으로 기록되어 있습니다. 이것을 결함으로 몰면 기대 문장 4번이 실패합니다.
- 기계 검사의 한계: `source-untouched`는 소스 파일만 봅니다. 계획의 구체성과 우선순위는 판정자가 봅니다.

### motion-opportunities

- 측정하려는 것: 정적인 화면에서 모션을 넣을 곳과 넣지 말아야 할 곳을 가려내는지 봅니다. 수정은 금지입니다.
- fixture `settings-static`: 워크스페이스 설정 화면입니다.
- 좋은 후보: 스위치 손잡이(`left`가 순간 이동하며 색도 즉시 바뀜), 고급 설정 펼침(`hidden` 토글로 높이 점프), 도메인 삭제(행이 즉시 사라져 아래가 튐), 저장 상태 문구 전환입니다.
- 넣지 말아야 할 곳: `/` 단축키 검색 포커스, 입력할 때마다 바뀌는 검색 필터링, 사용량 표 숫자(정보 확인)입니다.
- 기계 검사의 한계: 기존 fixture 파일의 무변경만 기계로 봅니다(메모 같은 새 파일 추가는 막지 않습니다). 제안의 질과 제외 판단은 판정자가 봅니다.

### drag-sheet

- 측정하려는 것: 끌어서 닫는 시트의 속도 처리, 다시 잡기, 포인터 수명 주기를 바르게 고치는지 봅니다.
- fixture `drag-sheet`: 필터 바텀 시트(`index.html`, `sheet.css`, `sheet.js`)입니다.
- 심은 결함:
  1. 놓는 속도를 `Math.abs(전체 거리) / 전체 시간`으로 구해서 늦은 튕김과 방향을 잃습니다. 임계값 2.5px/ms는 거의 도달할 수 없습니다(사용자가 말한 "휙 내려도 안 닫힘").
  2. `animateTo()`가 `currentY`를 목표값으로 즉시 바꾸므로, 닫히는 중에 다시 잡으면 화면 위치가 아닌 목표 위치에서 시작해 순간 이동합니다(사용자가 말함).
  3. 닫힘 완료를 `setTimeout(300)`으로 처리하므로, 다시 잡은 뒤에도 이전 콜백이 시트를 숨깁니다.
  4. 포인터 캡처와 `touch-action`이 없어 터치에서 브라우저 스크롤이 끌기를 가로채고, `pointercancel` 처리도 없어 끌기 상태가 남습니다. 다른 포인터를 구분하지 않습니다.
  5. 위로 끌면 제한 없이 올라가 시트가 화면 아래에서 떨어집니다.
  6. 닫힘이 고정 300ms `ease`이고 놓는 속도를 이어받지 않습니다. 움직임 감소 대응이 없습니다.
- 부수 결함: Esc로 닫히지 않고 열 때 포커스가 시트로 가지 않습니다. 사용자가 요청하지 않았으므로 가산 요소로만 봅니다.
- 기계 검사의 한계: 렌더 검사는 시트를 열지 않으므로 끌기 동작을 확인하지 못합니다. 판정자는 diff로 속도 계산, 다시 잡기, 취소 경로를 확인해야 합니다.

### motion-name

- 측정하려는 것: 말로 묘사한 효과의 이름을 정확히 대고, 구현을 맡길 요청 문장을 쓰는지 봅니다. fixture가 없습니다.
- 기대 용어: 첫째는 Layout animation(FLIP), 둘째는 Shared element transition(유사어 container transform, view transition), 셋째는 Number ticker 또는 rolling digits(odometer)입니다. 셋째에서 Tabular numbers를 함께 언급하면 좋지만 필수는 아닙니다.
- 기계 검사의 한계: 이 사례에는 기계 검사가 없습니다. 같은 효과도 영어·한국어 표기와 동의어(container transform, 컨테이너 트랜스폼 등)가 여러 가지라서, 용어의 정확성은 판정자가 판단합니다.

### library-pick

- 측정하려는 것: 기존 의존성을 확인하고 작업마다 하나씩 근거 있게 고르는지 봅니다. 설치와 수정은 금지입니다.
- fixture `react-deps`: `package.json`만 있습니다. React 19, Tailwind 4, `@radix-ui/react-dialog`, `react-window`, `zustand`, `clsx`가 이미 있습니다.
- 쟁점: 가상 목록은 이미 설치된 `react-window`를 그대로 쓰는 판단과, 다른 라이브러리로 바꾸되 이유와 비용을 밝히는 판단이 모두 허용됩니다. 설치된 것을 무시하고 새 라이브러리를 단정하면 기대 문장 2번이 실패합니다. 확인하지 않은 버전이나 유지보수 상태를 단정하는지도 봅니다.
- 기계 검사의 한계: 기존 fixture 파일의 무변경만 기계로 봅니다(메모 같은 새 파일 추가는 막지 않습니다).

### pricing-variants

- 측정하려는 것: 원래 디자인을 남긴 채 뚜렷하게 다른 세 안을 만들고, 한 화면에서 비교하게 하는지 봅니다.
- fixture `pricing`: 요금제 카드 세 장(`index.html`, `tokens.css`, `pricing.css`)입니다. 토큰은 녹색 브랜드와 다크 모드 값을 가집니다.
- 쟁점: 색만 바꾼 변형, 원래 디자인의 손실, 가격·기능의 변경이나 지어낸 혜택("가장 인기", 할인율 등), 외부 폰트 사용, 키보드로 조작할 수 없는 전환기를 봅니다. 요금제 정보에는 "연간 결제 시 2개월 무료"가 이미 있으므로 이 문구를 쓰는 것은 지어낸 것이 아닙니다.
- 기계 검사의 한계: 가격 보존은 문자열이 아니라 화면에 표시된 값으로 판정자가 봅니다(숫자 데이터를 서식화하는 해법도 타당합니다). 세 안의 차이와 시각 품질은 판정자가 스크린숏과 diff로 판단합니다. 렌더 검사는 기본으로 보이는 안만 찍습니다.

### sonner-darkmode

- 측정하려는 것: Sonner 문제의 원인을 정확히 짚고 고치는지 봅니다. 렌더링할 수 없는 Next.js 소스만 있습니다.
- fixture `sonner-app`: `app/layout.tsx`(next-themes, 클래스 기반), `app/page.tsx`, `components/SettingsDialog.tsx`, `components/ThemeToggle.tsx`, `package.json`입니다.
- 심은 결함:
  1. 두 `<Toaster />` 모두 `theme`이 없어 기본값 `light`로 고정됩니다.
  2. 앱은 `ThemeToggle`로 수동 전환을 하므로, `theme="system"`은 운영체제 설정만 따라가서 사용자가 고른 테마와 어긋날 수 있습니다. `resolvedTheme`을 넘겨야 합니다.
  3. 페이지의 Toaster가 `relative isolate`인 `<main>` 안에 있어 쌓임 맥락에 갇히고, 포털로 body에 붙은 z-100 오버레이 뒤에 깔립니다.
  4. 설정 모달 안에 두 번째 Toaster가 있습니다. transform이 걸린 `Dialog.Content` 안이라 위치가 어긋나고, 두 Toaster가 같은 토스트를 중복 표시하며, 모달을 닫으면 진행 중인 `toast.promise`가 Toaster와 함께 사라집니다.
- 기계 검사의 한계: 테마 전달은 컴포넌트 이름(별칭 import 포함)과 관계없이 판정자가 기대 문장 2번으로 봅니다. Toaster가 하나만 남았는지, `isolate`를 지웠는지 루트로 옮겼는지도 diff로 판단합니다.

### expo-press-sheet

- 측정하려는 것: React Native에 맞는 방식으로 누름 피드백과 시트 모션을 고치는지, 그리고 웹 지침을 잘못 끌어오지 않는지 봅니다. 렌더링할 수 없는 소스만 있습니다.
- fixture `expo-app`: Expo SDK 54, Reanimated 4, Gesture Handler, expo-haptics가 설치된 `package.json`과 `app/_layout.tsx`, `app/index.tsx`, `components/PlanCard.tsx`, `components/FilterSheet.tsx`입니다.
- 심은 결함:
  1. `PlanCard`의 `Pressable`에 눌림 상태 피드백이 없습니다.
  2. `FilterSheet`가 core `Animated` + `PanResponder`를 쓰고, `onPanResponderMove`에서 `setDragY`로 프레임마다 React 상태를 갱신합니다.
  3. 시트를 `height`(JS 드라이버, `useNativeDriver: false`)와 `top`으로 움직입니다.
  4. 닫힘을 거리(시트 높이의 절반)로만 판단합니다.
  5. 루트에 `GestureHandlerRootView`가 없습니다.
  6. 움직임 감소 대응과 선택 확정 햅틱이 없습니다(햅틱은 가산 요소입니다).
- 기계 검사의 한계: 이 사례에는 기계 검사가 없습니다. 웹 지침을 끌어왔는지, 이미 설치된 패키지만 썼는지, Reanimated API를 올바르게 썼는지는 판정자가 봅니다.

### swift-race

- 측정하려는 것: 범위 밖 대조군입니다. `ai`가 이 요청에서 무관하게 남는지, 해가 되는지(화면 디자인을 건드리는 등) 봅니다. 렌더링할 수 없는 소스만 있고, 이 저장소의 실행 호스트에는 Swift 툴체인이 없습니다.
- fixture `swift-feed`: `Package.swift`(tools 6.2, Swift 6 모드), `Sources/Feed/{Post,ImageCache,FeedStore,FeedView}.swift`입니다.
- 심은 결함:
  1. `FeedStore`가 MainActor에 격리되지 않았고, `Task.detached` 안에서 `posts`와 `isLoading`을 바꿉니다. 오류 경로만 `DispatchQueue.main.async`를 씁니다.
  2. `ImageCache`가 동기화 없는 딕셔너리를 `@unchecked Sendable`로 덮었습니다.
  3. `image(for:)`가 캐시 확인 → `await` 다운로드 → 저장 순서라서 같은 URL을 동시에 두 번 받습니다.
  4. task group 자식 작업이 `self.images`를 동시에 씁니다.
  5. `Post`는 변경 가능한 클래스인데 `like()`가 수정한 뒤 detached 작업으로 넘깁니다.
  6. `.refreshable`이 동기 `refresh()`를 호출해 새로고침 표시가 즉시 끝납니다(가산 요소입니다).
- 기계 검사의 한계: 이 사례에는 기계 검사가 없습니다. 테스트 파일 추가 같은 정당한 변경을 막지 않기 위해서입니다. `@unchecked Sendable`을 `Mutex`와 함께 남기는 해법은 타당할 수 있어서 금지 패턴으로 넣지 않았습니다. 빌드 성공 주장은 판정자가 최종 응답에서 확인합니다.

### card-polish

- 측정하려는 것: 기능과 정보 구성을 지키면서 카드의 세부 품질을 얼마나 끌어올리는지 봅니다.
- fixture `product-card`: 실시간 경매 카드 3장(`index.html`, `card.css`, `card.js`, SVG 이미지)입니다. SVG에 `preserveAspectRatio="none"`을 넣어 래스터 이미지처럼 늘어나게 했습니다.
- 심은 결함:
  1. 900ms마다 바뀌는 입찰가에 고정폭 숫자가 없어 폭이 흔들리고, `$1240`처럼 천 단위 구분이 없습니다.
  2. "1 bids", "1 watchers" 복수형 오류가 있습니다.
  3. 상대 시간이 20초 전이면 "0 minutes ago", 400일 전이면 "9600 hours ago"입니다.
  4. 판매자 아바타(가로·세로로 긴 원본)가 `object-fit` 없이 28px 원에 들어가 찌그러집니다.
  5. 상품 사진 비율이 4:3, 2:3, 12:5로 달라 카드 높이가 들쭉날쭉합니다.
  6. 1px 회색 테두리와 `0 10px 30px rgba(0,0,0,.35)` 그림자가 겹쳐 표면이 탁합니다.
  7. 보조 글자 `#999`가 흰 배경에서 대비가 약 2.8:1입니다.
  8. 버튼에 `transition: all 0.4s`와 `scale(1.05)` hover가 있고, 눌림 피드백이 없으며, 대문자와 넓은 자간을 씁니다. 큰 제목도 자간이 넓습니다.
- 기계 검사의 한계: 숫자 폭 고정과 아바타 비율은 해법이 여러 가지(`tabular-nums`, 고정폭 글꼴, `object-fit`, `flex-shrink`)이므로 판정자가 스크린숏과 diff로 판단합니다. 그림자와 대비 개선, 위계는 판정자가 스크린숏으로 판단합니다.

### new-screen

- 측정하려는 것: 짧은 제품 설명만으로 과제에 맞는 화면을 만드는 시각 품질을 봅니다.
- fixture `room-booking`: 사내 도구 토큰 `tokens.css`(보라색 브랜드, 상태색 `--ok`·`--warn`·`--busy`, 다크 모드)와 빈 `index.html`입니다.
- 쟁점: 비어 있는 회의실을 먼저 찾게 하는 위계, 색에만 기대지 않는 상태 구분, 토큰 사용, 사내 도구에 맞는 밀도(마케팅 히어로 같은 과장 없음), 그럴듯한 예시 데이터, 외부 자원 없음을 봅니다.
- 기계 검사의 한계: `uses-tokens`는 토큰 변수를 하나라도 썼는지만 봅니다(대체값이 있는 `var(--bg, #fff)`도 인정합니다). 시각 품질은 판정자가 1280px과 320px의 라이트·다크 스크린숏으로 판단해야 합니다.

### settings-review

- 측정하려는 것: 화면 전체 검토의 정확성, 범위, 근거를 봅니다. 수정은 금지입니다.
- fixture `settings-review`: 기존 `evals/fixtures/settings.html`을 `index.html`로 복사하고 두 가지를 더했습니다(버튼의 `transition: all .3s ease-in`, 저장 버튼 hover `scale(1.08)`).
- 심은 결함:
  1. 닫기 아이콘 버튼에 접근 가능한 이름이 없습니다.
  2. '오류가 발생했습니다.'가 저장 전부터 `role="alert"`로 보이며, 원인과 해결 방법이 없습니다.
  3. 닫기 버튼이 실제로 닫지 않고 상태 문구만 바꿉니다. 저장을 누르면 항상 실패 문구가 나와서 위의 오류 문구와 겹칩니다.
  4. `transition: all`과 `ease-in`, hover 확대가 있고 눌림 피드백이 없습니다.
  5. 다크 모드 대응이 없고 색이 하드코딩되어 있습니다(가산 요소입니다).
- 기계 검사의 한계: 기존 fixture 파일의 무변경만 기계로 봅니다(메모 같은 새 파일 추가는 막지 않습니다).

### consent-copy-ko

- 측정하려는 것: 범위가 작은 일상 과제입니다. 문구만 고치는 범위를 지키면서 한국어 문구 품질을 높이는지 봅니다.
- fixture `consent`: 기존 `evals/fixtures/consent.html`을 그대로 `index.html`로 복사했습니다.
- 심은 결함: 영어 배지(`Location access`), 종결어미 혼용(해요체와 합니다체), 할인을 놓친다는 위협, 근거 없는 '안심' 주장, 의미 없는 '확인' 버튼, 모욕적인 거절 버튼("아니요, 할인은 필요 없어요"), 조건 다섯 개를 한 문장에 넣은 쿠폰 문구, 구분 기호 없는 금액(3000원, 15000원)입니다.
- 기계 검사의 한계: 변경 범위(index.html)와 두 버튼의 보존만 기계로 봅니다. 손실 위협 표현, 한 화면 한 언어, 새 문구가 사실에 맞는지는 판정자가 봅니다.

## 기계 검사 원칙 (1회차 리뷰 반영)

기계 검사는 프롬프트가 명시한 범위 제한(검토만, 문구만, 패키지 추가 금지)과 해법에 관계없이 틀린 결과(넘침, 콘솔 오류, `transition: all`)만 봅니다. 특정 구현 방식을 요구하는 검사와 프롬프트에 없는 파일 범위 제한은 두지 않고, 그런 판단은 기대 문장으로 판정자에게 맡깁니다.

외부 자원 사용(CDN, 웹 폰트)은 기계 검사로 보지 않습니다. 일반 링크와 자원 로드를 정규식으로 구별하기 어렵고, 채점기의 렌더러가 외부 요청을 모두 막으므로 판정자는 스크린숏과 diff로 판단합니다. 같은 이유로 Sonner의 Toaster 위치와 `stress-member-list`의 이스케이프 지적도 기대 문장으로만 판정합니다.

`transition: all` 금지, `scale(0)` 금지, 레이아웃 속성 전환 금지 같은 스타일 규칙과, 특정 문자열(파일 이름, 단어, package.json 전체)을 요구하거나 금지하는 검사도 두지 않습니다. 일부 스킬의 규칙과 같은 문장이라 특정 arm에 유리하거나, 표기만 다른 올바른 해법을 떨어뜨리기 때문입니다.
