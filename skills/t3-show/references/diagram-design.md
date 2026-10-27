# diagram-design 결과물을 스레드에 띄우기

`diagram-design`이 만든 독립 HTML을 `html_render` 프레임에 맞춘다. 그림의 종류와 구성은 `diagram-design`이 정하고, 스레드 테마가 팔레트를 소유하므로 그 스킬의 style guide 확인(§0)은 건너뛴다.

## 변환

1. 외부 폰트 `<link>`·`@import`, `body`의 배경·padding·`min-height: 100vh`·중앙 정렬, 페이지 제목 `h1`, SVG의 `min-width`를 지운다. 제목은 `html_render`의 `title`로 옮긴다.
2. 캔버스 전체를 덮는 `<rect width="100%" height="100%">`와 점 격자 배경을 지운다.
3. 색과 글꼴을 아래 표대로 바꾼다. 그다음 `grep -E '#[0-9a-fA-F]{3,8}\b|rgba?\('`로 남은 고정 색이 없는지 확인한다. 상태를 뜻하는 색은 `--success`, `--warning`, `--destructive`, `--info`로 옮긴다.
4. viewBox를 실제 내용의 경계로 줄인다. 프레임은 데스크톱 728px, 휴대폰 약 360px이고 좌우 여백이 없다. 이 폭을 [`diagram-design`의 mobile.md](../../diagram-design/references/mobile.md)에 정해진 글자 크기 계산에 넣는다. 728px에서 11px에 못 미치면 viewBox를 더 줄이거나 배치를 세로로 바꾼다. 휴대폰 글자 크기는 사람이 모바일을 요구했을 때만 판정한다.

SVG의 `fill`·`stroke`·`font-family` 속성에 `var()`와 `color-mix()`를 그대로 써도 적용된다. `--font-sans`에 한글 글꼴이 없어도 한글은 시스템 대체 글꼴로 표시된다.

## 색·글꼴 매핑

| `diagram-design` 역할 | T3 값 |
|---|---|
| paper 캔버스 | 지운다 |
| paper 라벨 마스크 | `var(--background)` |
| paper-2, 흰 노드 면 | `var(--card)` |
| ink | `var(--foreground)` |
| muted, soft | `var(--muted-foreground)` |
| rule, ink의 반투명 `rgba` | `color-mix(in srgb, var(--foreground) N%, transparent)`; N은 원래 alpha보다 조금 높인다 |
| accent | `var(--primary)` |
| accent-tint | `color-mix(in srgb, var(--primary) 12%, transparent)` |
| link | `var(--info)` |
| sans, serif 글꼴 | `var(--font-sans)` |
| mono 글꼴 | `var(--font-mono)` |

브랜드 profile을 입힌 그림도 같은 역할 이름으로 대응시킨다. 강조색을 한두 곳의 초점에만 쓰는 원래 위계는 그대로 유지한다.

변환본은 T3가 주입하는 테마 변수에 기대므로 독립 파일로 열면 색이 빠진다. 파일이 필요하면 변환 전 원본을 넘긴다.
