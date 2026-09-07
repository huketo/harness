# Google Calendar 일정 수집

일일 업무보고에 필요한 회의, 출장, 외근, 휴가를 Google Calendar의 비공개 iCal 피드에서 읽는다. 비공개 iCal 주소는 캘린더 내용을 읽을 수 있는 자격증명이므로 로컬에서만 다룬다.

## 구조

```text
Google Calendar
  -> 비공개 iCal 주소로 HTTPS GET
  -> collect_calendar.py가 UID별 vdir 항목으로 분할
  -> khal이 반복 일정과 시간대를 전개
  -> 하루 일정 JSON
```

- `collect_calendar.py`는 각 피드를 메모리에 받은 뒤 로컬 미러를 조정한다. 수신 실패 시 기존 미러는 유지된다.
- 한 iCal 피드에 여러 UID가 들어 있으므로 수집기가 이벤트별 파일로 나눈다.
- 같은 UID의 반복 일정과 `RECURRENCE-ID` 예외는 같은 파일에 둔다.
- `khal`은 반복 규칙과 시간대를 처리하며 미러를 읽기 전용으로 연다.
- 수집기는 취소된 일정을 제외하고 제목과 카테고리로 `meeting`, `trip`, `leave`, `allday`, `event`를 분류한다.

## 의존성

Python 표준 라이브러리와 `khal`이 필요하다.

```bash
uv tool install --python 3.13 khal
```

## 캘린더 연결

캘린더마다 한 번 다음 절차를 수행한다.

1. Google Calendar에서 설정을 연다.
2. 연결할 캘린더의 **캘린더 통합**에서 **iCal 형식의 비공개 주소**를 복사한다.
3. 터미널에서 `bash scripts/link_google_calendar.sh`를 실행한다.
4. 업무용인지 구분할 수 있는 라벨을 입력하고 비공개 주소를 붙여넣는다. 주소 입력은 화면에 표시되지 않는다.
5. 스크립트가 피드를 확인하고 로컬 설정과 미러를 만든 뒤 `khal`에서 읽히는지 확인한다.

`work`, `personal`처럼 목적이 드러나는 라벨을 사용한다. 보고서 초안에는 업무용으로 선택한 캘린더만 포함한다.

비공개 주소를 Google Calendar에서 재설정하면 이전 주소가 무효가 된다. 같은 라벨로 링크 스크립트를 다시 실행해 교체한다.

## 로컬 파일

- `~/.config/daily-report/calendars.conf`: `label = private-ical-url` 형식. 파일 권한은 600, 상위 디렉터리는 700이다. `DAILY_REPORT_CALENDARS`로 경로를 바꿀 수 있다.
- `~/.config/khal/config`: 로컬 vdir을 `readonly = True`로 읽는다. `KHAL_CONFIG`로 경로를 바꿀 수 있다.
- `~/.local/share/calendars/<label>/`: UID별 `.ics` 파일과 표시 이름을 저장하는 미러다.

비공개 주소가 든 설정 파일과 미러는 저장소에 커밋하지 않는다.

## 수집기 출력 해석

```bash
python3 scripts/collect_calendar.py --date 2026-01-15
python3 scripts/collect_calendar.py --calendar work --date 2026-01-15
python3 scripts/collect_calendar.py --no-fetch --date 2026-01-15
```

주요 필드:

- `date`, `timezone`: 요청한 날짜와 `Asia/Seoul` 시간대
- `sync.ok`: 모든 선택 피드의 갱신 성공 여부
- `sync.skipped`: `--no-fetch`로 갱신을 건너뛰었는지 여부
- `sync.sources[]`: 라벨별 갱신 결과, 생성 시각, 파일 변경 수, 오류
- `events[]`: 정규화된 일정
- `dropped`: 취소되었거나 거절 상태로 식별되어 제외된 일정 수

`sync.ok=false`여도 지난 미러에서 이벤트가 나올 수 있다. 이 경우 최신 일정이라고 단정하지 말고 갱신 실패와 오류를 함께 알린다.

일정에는 `calendar`, `kind`, `title`, `start`, `end`, `all_day`, `spans_multiple_days`, `starts_today`, `recurring`, `status`, `partstat`, `location`, `description`, `organizer`가 포함될 수 있다. 제목과 카테고리에 기반한 `kind`는 초안 표현을 돕는 힌트이며 최종 판단은 일정 내용을 따른다.

Google의 iCal 피드가 참석자 정보를 제공하지 않으면 `partstat`가 비어 있고 사용자가 거절한 초대도 일반 일정처럼 보일 수 있다. 참석 여부가 중요한 항목은 사용자에게 확인한다.

## 상태 확인과 문제 해결

```bash
bash scripts/link_google_calendar.sh --check
khal printcalendars
khal list today today
python3 scripts/collect_calendar.py --no-fetch
```

- **no calendars configured**: 링크 스크립트로 캘린더를 하나 이상 등록한다.
- **HTTP 401/403/404**: 비공개 주소가 재설정되었거나 접근할 수 없다. Google Calendar에서 새 주소를 복사해 같은 라벨로 다시 연결한다.
- **네트워크 오류**: 기존 미러는 유지된다. 최신 여부를 사용자에게 알린다.
- **일정 누락**: 올바른 업무 캘린더를 연결했는지, 요청 날짜와 라벨이 맞는지, `sync.sources[].generated_at`이 최근인지 확인한다.
- **khal 없음**: 위 설치 명령으로 설치한 뒤 링크 스크립트를 다시 실행한다.
