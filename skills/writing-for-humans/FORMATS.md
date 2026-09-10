# 장르, 테마, 형식

[SKILL.md](SKILL.md) 3단계(골격)와 5단계(패키징)에서 읽는다. 본문 원본은 Markdown이고 그림 원본은 HTML이다. HTML·Word 문서와 그림용 SVG·PNG는 두 원본에서 만든다. 문장·근거·참조·용어 규칙은 SKILL.md가, 그림 설계는 `diagram-design`이 소유한다. 내보내기와 문서 테마 적용은 [문서 적용 규칙](../diagram-design/references/harness-documents.md)을 따른다.

## 장르

독자의 결정이 장르를 정한다. `genres/<장르>.md`를 복사해 시작하고, 골격의 절 순서와 표 열은 지킨다. `{{ }}` 자리표시자를 전부 채우거나 그 절을 지운다.

| 장르 | 독자의 결정 | 골격 | 기본 테마·스타일 |
|---|---|---|---|
| `report` | 결론을 믿고 행동할지 | 요약(질문·결론·근거·행동) → 발견별 주장·근거·영향 → 미확인 → 출처 | slate · reading |
| `postmortem` | 재발 방지책을 승인할지 | 요약 → 영향 표 → 타임라인(KST 절대 시각) → 근본 원인 → 대응 → 재발 방지 액션 표 → 잘 된 점과 운 → 미확인 | ember · reading |
| `design` | 이 설계로 갈지 | 결정 → 배경·제약 → 설계(그림·인터페이스) → 대안 비교표 → 결과와 영향 → 미결 → 출처 | slate · reading |
| `guide` | 절차를 따라 할 수 있는지 | 전제 조건 → 번호 절차(명령·출력 분리) → 확인 → 문제 해결 표 → 참고 | moss · compact |
| `brief` | 한 화면에서 승인·거절 | 요청+권고 첫 문단 → 배경 3줄 → 선택지 표 → 결정·기한·다음 행동 | ink · reading |
| `minutes` | 내가 맡은 액션이 무엇인지 | 결정 사항 → 액션 표(담당·기한) → 논의 → 미결 → 다음 회의 | slate · compact |
| `post` | 내 문제에 이 글이 답하는지 | 문제 묘사+약속 → 문제가 생기는 조건 → 원인 → 해결(전후 수치) → 정리 → 참고 | editorial · reading |

front matter의 `genre:`가 기본 테마·스타일을 정한다. `title`, `date`, `author`, `subject`(대상), `scope`(범위), `subtitle`(post)이 머리 정보가 된다.

## 테마와 스타일

테마는 색, 스타일은 읽기 환경이다. `html/shell.html` 안의 토큰이 정본이며 값은 전부 hex다. 렌더된 문자 대비는 모든 테마에서 5.3:1 이상으로 측정됐다(2026-09-09, 본문·muted·링크·note 라벨·인용 출처·SVG 라벨).

| 테마 | 용도 | 특징 |
|---|---|---|
| `slate` | 보고서, 설계, 회의록 | 흰 배경, 청회색 강조 `#1f4d7a` |
| `ember` | 장애 보고 | 갈색 강조 `#9a3412`, 따뜻한 패널. 위험색(적색)은 쓰지 않는다 |
| `moss` | 안내서, runbook | 녹색 강조 `#1e6b3a` |
| `ink` | 결재·공지·1페이지 요약 | 무채색, 명조 제목 |
| `editorial` | 기술 포스트 | 종이색 배경 `#fdfbf7`, 명조 제목, 본문 17px, 폭 680px |

| 스타일 | 용도 | 차이 |
|---|---|---|
| `reading` | 화면·모바일 공유 | 폭 820px, 16px/1.7 |
| `compact` | 참조 문서 | 폭 960px, 15px/1.6 |
| `print` | 결재·인쇄·PDF | 폭 720px, 명조 본문, 코드 줄바꿈, 링크 URL 병기. 인쇄 미디어 규칙(`@page` A4)은 모든 스타일에 공통 |

다크 테마는 두지 않는다. `color-scheme: only light`가 휴대폰 브라우저의 자동 반전에서 그림 색을 지킨다.

## Markdown

원본 그대로가 산출물이다. GitHub·GitLab에서 그대로 읽히는 문법만 쓴다: YAML front matter, `#` 제목, GFM 표, 코드 펜스(언어 표기), `> [!NOTE]`/`> [!WARNING]` 알림, 인용은 일반 `>`, 그림은 `![캡션](이름.svg)`.

- 경로를 지정받지 않았으면 `docs/<주제-kebab>.md`. README는 저장소 루트.
- 그림 HTML과 내보낸 `.svg`는 문서와 같은 디렉터리에 둔다. SVG는 [문서 적용 규칙](../diagram-design/references/harness-documents.md)의 외부 요청 없는 내보내기 계약을 지킨다. 캡션이 alt가 되고, HTML에서는 `<figcaption>`이 된다.
- `공개` 독자면 링크는 절대 URL. `내부` 독자면 저장소 상대 링크를 쓸 수 있다.
- **강조 닫는 기호 앞에 문장부호가 오면 그 뒤에 한글을 붙이지 않는다.** CommonMark는 닫는 `**` 바로 앞이 문장부호(백틱, 괄호, 따옴표, 콜론, 느낌표)이고 바로 뒤가 한글이면 닫는 기호로 보지 않아 `` **`config.json`**을 ``, `**(중요)**입니다`, `**항목:**설명`이 기호 그대로 출력된다. `**볼드**입니다`처럼 앞이 글자면 정상이다. 고치는 방법: 문장부호를 강조 밖으로 낸다(`**항목**: 설명`), 조사까지 강조 범위에 넣는다(`` **`config.json`을** ``), 그대로 둬야 하면 `<strong>`을 쓴다. `_`·`__`는 한글과 붙으면 항상 실패하므로 강조에는 `*`·`**`만 쓴다.
- 제목 `#`, 목록 `-`, 인용 `>` 뒤에는 공백 하나. 목록과 코드 블록 앞뒤에는 빈 줄.
- 열 6개를 넘는 표는 나눈다. 코드 줄은 80자 이내.

검수: 렌더된 결과(원격 저장소 파일 페이지)를 1280px과 360px에서 본다. 표 가로 스크롤 외에 잘리는 요소가 없고, 그림 안 글자가 360px에서 읽힌다. 본문에 `**`·`*`·`_`가 문자 그대로 남지 않았다(원본에서 `[^\w\s가-힣]\*\*[가-힣]`와 `_[가-힣]` 검색). 모든 링크를 실제로 연다. `{{`가 남아 있지 않다.

## HTML

파일 하나를 복사하거나 첨부하면 그대로 재현되는 single-file HTML.

```bash
python3 <이 스킬>/scripts/build.py 문서.md --to html [--theme …] [--style …] [--out 경로]
```

`html/shell.html`(CSS 인라인, 스크립트 없음)과 `html/filters.lua`(SVG 인라인, 알림 → `.note`, 표 → `.table-wrap`, 출처 목록 → `.sources`)를 거친다. `## ` 절이 6개 이상이면 목차가 붙는다. pandoc 3이 없으면 shell.html을 복사해 `$body$` 자리에 본문을 손으로 옮기되, 위 필터가 하는 변환을 같은 클래스로 재현한다.

검수: 브라우저 도구로 `file://<절대경로>`를 열고 전부 확인한다.

1. **외부 요청 0건** — `performance.getEntriesByType('resource').map(r => r.name)`이 빈 배열이다.
2. **스크립트 0건** — `document.scripts.length`가 0이다.
3. **링크** — `[...document.querySelectorAll('a[href]')].filter(a => !a.getAttribute('href').startsWith('#')).map(a => a.href)`로 모아 각 URL을 실제로 연다. `공개` 문서에 `file:`·상대 경로·사내 호스트·로그인 필요 URL이 있으면 본문 인용으로 바꾼다.
4. **그림** — `diagram-design`의 self-check와 [모바일 검수](../diagram-design/references/mobile.md)를 통과한 그림을 넣고, 삽입된 페이지에서 다시 확인한다. 독립 HTML의 통과는 figure 여백이 추가된 문서의 통과를 뜻하지 않는다.
5. **반응형** — 1280px에서 표·코드·그림이 잘리지 않는다. 360px에서 가로 스크롤이 생기는 요소가 `.table-wrap`, `<pre>`뿐이다: `[...document.querySelectorAll('body *:not(svg *)')].filter(el => el.scrollWidth > el.clientWidth + 1).map(el => el.getAttribute('class') || el.tagName)`. 두 폭 모두 전체 스크린샷으로 확인한다.
6. **print 스타일이나 인쇄 목적이면** 인쇄 미디어로 한 번 더 렌더해 코드가 줄바꿈되고 페이지 밖으로 나가지 않는지 본다.

## Word

```bash
python3 <이 스킬>/scripts/build.py 문서.md --to docx [--out 경로]
```

- 그림은 `이름.svg` 옆에 같은 이름의 `이름.png`를 둔다. `diagram-design`의 [문서 적용 규칙](../diagram-design/references/harness-documents.md)에 따라 검증한 그림 HTML에서 SVG 요소만 2배 배율로 캡처한다. 필터가 Word에는 이 PNG를 넣는다. PNG가 없으면 pandoc이 `rsvg-convert`를 찾다 실패하므로 반드시 만든다.
- 제목은 pandoc이 `Heading N` 스타일로 넣어 탐색창이 동작한다. 표는 열 6개까지, 코드 줄은 80자 이내.
- 링크는 본문에 URL이 보이게 둔다. 인쇄본에서는 하이퍼링크가 사라진다.
- 사후 편집(표 서식, 그림 위치, 결재 양식 삽입)은 `officecli` 스킬로 한다.

검수: `officecli view <file> <mode>`로 본문 순서·제목 계층·그림·표를 확인한다. `officecli validate`는 pandoc 산출물의 요소 순서(`pStyle`·`b`·`jc` 등)를 스키마 위반으로 33건 안팎 보고하는데, 이는 pandoc 3.1 writer의 알려진 출력이며 Word가 여는 데 지장이 없다는 것은 이 환경에서 실측하지 못했다. 결재·외부 전달 전에는 Word에서 한 번 연다.

