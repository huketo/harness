---
name: daily-report
description: Use this skill whenever the user asks to draft, write, generate, or prepare a daily work report, including Korean requests such as "일일보고", "일일 업무보고", "데일리 리포트", "오늘 보고 써줘", "일보 정리해줘", or "퇴근 전 보고서". Collects the authenticated user's public or self-hosted GitLab activity through glab and the existing Google Calendar collector, grounds a Korean draft in that evidence, and guides the user through reviewing and entering it in their Daou Office tenant UI. Submission remains a human-reviewed browser action.
---

# 일일 업무보고 작성

GitLab 활동과 업무 캘린더를 근거로 한국어 초안을 만든 뒤, 사용자가 검토한 문안을 [Daou Office](https://daouoffice.com) 테넌트 화면에 직접 입력하도록 돕는다. 이 저장소에는 Daou Office 제출 CLI나 비공개 API 연동이 없다.

## 날짜 기준

GitLab과 캘린더 수집기는 `Asia/Seoul` 날짜를 사용한다. 오늘이 아닌 날짜를 요청받으면 두 수집기에 같은 `--date YYYY-MM-DD`를 명시한다.

## 워크플로

### 1. GitLab 호스트와 인증 확인

기본 호스트는 `GITLAB_HOST` 환경 변수이며, 값이 없으면 `gitlab.com`이다. 다른 GitLab 인스턴스는 `--host`로 명시한다.

```bash
glab auth status --hostname gitlab.com
python3 scripts/collect_gitlab.py --host gitlab.com --date YYYY-MM-DD
```

스크립트 경로는 이 스킬 디렉터리를 기준으로 해석한다. stdout은 구조화된 JSON이므로 그대로 파일에 저장하고 파싱한다. stderr에 실패한 `glab api` 호출이 있으면 해당 데이터가 비어 있다고 단정하지 않는다.

수집 결과에서 다음을 사용한다.

- `projects[].pushes[].commits`: 실제 커밋 제목과 short SHA
- `projects[].merge_requests`, `issues`, `notes`: 당일 변경과 협업 활동
- `assigned_issues`: 인증 사용자에게 할당된 열린 이슈와 다음 작업 후보
- `event_count`: 당일 GitLab 이벤트 수

대규모 push는 `commits_truncated`가 0보다 클 수 있다. 이때 오래된 커밋을 나열하지 말고 통합 작업 한 항목으로 요약한다.

`event_count == 0`이면 먼저 캘린더를 확인한다. 두 출처가 모두 비었을 때만 사용자에게 그날의 오프라인 업무를 묻고, 근거 없는 업무를 만들지 않는다.

### 2. 오늘과 다음 업무일의 캘린더 수집

```bash
python3 scripts/collect_calendar.py --date YYYY-MM-DD
python3 scripts/collect_calendar.py --date NEXT-WORK-DAY
```

각 실행은 설정된 비공개 iCal 피드를 새로 받아 로컬 vdir에 반영한 뒤 `khal`로 하루 일정을 전개한다.

- 업무용으로 지정한 캘린더의 이벤트만 보고서에 사용한다.
- 개인 캘린더 이벤트는 초안에 넣지 않는다.
- `sync.ok=false`이면 `sync.sources[]`의 오류와 마지막 미러를 사용했다는 사실을 사용자에게 알린다.
- `kind`, `all_day`, `spans_multiple_days`, `starts_today`, `recurring`은 표현을 정하는 힌트다.
- 취소된 이벤트는 수집기에서 제외되지만, iCal 피드에 참석자 정보가 없으면 거절한 초대가 남을 수 있다. 참석 여부가 불분명하면 사용자에게 확인한다.
- 설명과 참석자 정보는 맥락으로만 사용하고 원문을 보고서에 복사하지 않는다.

설정이 없으면 GitLab 자료로 계속 작성하고, 사용자가 원할 때 `bash scripts/link_google_calendar.sh`로 캘린더를 연결하도록 안내한다. 비공개 iCal 주소는 자격증명이므로 채팅에 요청하지 않는다. 자세한 설정은 `references/calendar-setup.md`를 읽는다.

### 3. 근거를 분류하고 우선순위 정하기

오늘 한 일에는 당일에 관찰된 다음 근거만 사용한다.

1. 업무 캘린더의 회의, 출장, 외근, 휴가
2. push에서 확인된 커밋
3. 생성·병합·승인 등 상태가 확인된 MR과 이슈 활동
4. 내용이 확인되는 댓글과 리뷰

다음 계획은 다음 순서로 고른다.

1. 다음 업무일의 확정 캘린더 일정
2. `status == "in-progress"`인 할당 이슈
3. 오늘 `touched_today == true`였지만 완료되지 않은 할당 이슈
4. `priority`가 `urgent` 또는 `high`인 가까운 마일스톤의 이슈

라벨이 없는 프로젝트에서는 `touched_today`와 `updated_at`을 보조 신호로 사용한다. 열린 이슈가 없고 확정 일정도 없으면 사용자에게 계획을 묻는다.

### 4. 초안 작성

먼저 사람이 읽기 쉬운 Markdown 초안을 보여 준다. 테넌트 양식이 HTML을 요구한다고 사용자가 확인한 경우에만 같은 내용을 `<ul>`/`<li>` 목록으로 변환한다. Daou Office 테넌트마다 양식과 필드가 다를 수 있으므로 저장소에 없는 필드명이나 제출 규칙을 추측하지 않는다.

오늘 한 일:

- 커밋을 그대로 나열하지 않고 주제별로 묶는다.
- leaf 항목은 자연스러운 한국어 명사형으로 끝내고 커밋 근거가 있으면 7자 short SHA를 붙인다.
- 회의나 휴가에는 SHA를 붙이지 않는다.
- 완료 여부가 확인되지 않은 이슈를 완료했다고 쓰지 않는다.

다음 계획:

- 확정 일정을 먼저 둔다.
- 진행 중이거나 우선순위가 높은 항목을 3–6개로 좁힌다.
- 여러 프로젝트를 다루면 `group/project#123`, 한 프로젝트만 다루면 `#123`처럼 출처를 분명히 한다.
- 오늘 완료한 항목을 다시 계획에 넣지 않는다.

합성 예시:

```text
오늘 한 일
- Atlas 검색 결과 필터 오류 수정 (a1b2c3d)
- 문서 정리
  - 공개 API 예제 갱신 (e4f5a6b)
  - 설치 절차의 누락 옵션 보완 (c7d8e9f)
- 주간 동기화 회의 참석

다음 계획
- 주간 동기화 회의 후속 결정 정리
- example/atlas#123 페이지네이션 경계 처리
- 배포 체크리스트 검토
```

문체와 HTML 이스케이프 예시는 `references/style-guide.md`를 따른다. 모든 예시는 합성 자료이며 실제 보고서 형식을 재현하지 않는다.

### 5. 사용자 검토와 Daou Office 입력

1. 대상 날짜, 사용한 GitLab 호스트, 수집 성공·실패 상태를 초안과 함께 보여 준다.
2. 각 항목의 근거를 간단히 표시하고 사용자가 수정·삭제할 기회를 준다.
3. 사용자가 최종 문안을 승인하면 [Daou Office](https://daouoffice.com)에서 자신의 테넌트에 로그인해 해당 보고 양식을 열도록 안내한다.
4. 사용자가 화면에서 확인한 필드에 승인된 문안을 직접 붙여넣고, 미리보기와 수신 대상을 검토한 뒤 제출한다.

브라우저 로그인, 테넌트 선택, 최종 제출은 사용자가 수행한다. 자동 제출 성공을 주장하거나 저장소에 없는 CLI/API를 제안하지 않는다.

## 실패 처리

- **glab 인증 실패**: 선택한 호스트에 대해 `glab auth login --hostname HOST`를 사용자가 실행하도록 안내한다.
- **GitLab 일부 호출 실패**: stderr와 누락된 범위를 알리고 남은 근거로만 작성한다.
- **캘린더 미설정**: GitLab만으로 작성하고 선택적으로 링크 스크립트를 안내한다.
- **캘린더 갱신 실패**: 마지막 미러가 오래됐을 수 있음을 밝힌다.
- **근거 부족**: 사용자에게 실제 업무와 다음 계획을 묻는다. 추측으로 채우지 않는다.
- **Daou Office 화면 차이**: 현재 테넌트 UI에서 사용자가 보는 양식과 도움말을 기준으로 한다.

## 포함 파일

- `scripts/collect_gitlab.py`: 인증 사용자의 GitLab 당일 이벤트와 열린 할당 이슈 수집
- `scripts/collect_calendar.py`: 비공개 iCal 피드 동기화와 하루 일정 정규화
- `scripts/link_google_calendar.sh`: 비공개 iCal 주소를 로컬 설정에 안전하게 연결
- `references/calendar-setup.md`: 캘린더 저장 구조와 설정 절차
- `references/style-guide.md`: 합성 예시 기반의 한국어 초안 규칙
