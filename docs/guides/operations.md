# 소유자 운영 절차

[문서 색인](../index.md) · [설치 안내](installation.md) · [공개 배포 정책](../public-release.md)

> **일반 설치 절차가 아닙니다.** 이 문서는 소유자가 개인 워크스테이션에서 선택적으로 실행하는 흐름과 안전 경계를 설명합니다. 배포본에는 cron 일정이 없고, 외부 쓰기나 원격 게시를 자동으로 활성화하지 않습니다.

명령은 저장소 루트에서 실행합니다. 인증된 서비스 조회, 모델 호출, 원격 쓰기, 일정 등록은 각각 별도의 외부 효과입니다. 명령 이름이나 `--dry-run`만 보고 읽기 전용이라고 가정하지 않습니다.

## 비용 감사

`herdr/cron/cost-audit.mjs`는 로컬 OMP 통계에서 비용·캐시 사용을 분석하고 AGY `automation` 프로필에 이미 생성된 결과의 해석만 맡깁니다. 통계와 설정 변경을 모델에 위임하지 않으며 결과는 무시되는 `var/` 아래에 둡니다.

```bash
bun herdr/cron/cost-audit.mjs
```

이 명령은 로컬 상태와 모델 접근을 요구할 수 있습니다. 카탈로그 환산 비용과 실제 청구액을 구분하고, 한 시점의 결과를 전체 환경의 절감 보장으로 해석하지 않습니다. 계산 경계는 [비용 감사 문서](../../skills/cost-audit/README.md)와 [가격 근거](../PRICING.md)를 참고합니다.

## 일일보고 초안과 수동 제출

공개 `daily-report` 스킬은 다음 흐름만 제공합니다.

1. [GitLab](https://gitlab.com) 활동은 인증된 `glab`과 저장소의 collector로 모읍니다.
2. 기존 iCal/`khal` collector로 회의·출장·외근·휴가 등 사용자가 선택한 일정 입력을 모읍니다.
3. 수집 근거에 있는 사실만 사용해 초안을 작성하고, GitLab 항목과 일정 항목을 사용자가 대조합니다.
4. 사용자가 자신의 [Daou Office](https://daouoffice.com) tenant UI를 열어 초안을 직접 입력하고 최종 내용을 검토한 뒤 제출합니다.

실제 명령과 필요한 입력은 [daily-report 스킬](../../skills/daily-report/SKILL.md)이 소유합니다. Harness는 Daou Office CLI, API 경로, 인증 구현, 자동 제출, 제출 영수증 검증을 제공하지 않습니다. 로그인, tenant 선택, 내용 수정, 제출은 사용자 작업입니다.

수집 결과와 초안에는 개인 일정과 작업 내용이 들어갈 수 있으므로 `var/` 등 로컬 비추적 경로에만 둡니다. 공개 예제는 처음부터 합성 자료로 작성합니다. 실제 보고서를 이름만 바꾸어 fixture나 문서 예제로 만들지 않습니다.

## Google Calendar 미러

일일보고 스킬은 사용자가 선택한 Google Calendar의 **비공개 iCal 주소**를 읽을 수 있습니다. `collect_calendar.py`가 UID별 vdir 미러를 만들고 `khal`이 반복 일정을 전개합니다. OAuth 클라이언트나 GCP 프로젝트를 만드는 방식이 아닙니다.

```bash
uv tool install --python 3.13 khal
bash skills/daily-report/scripts/link_google_calendar.sh --check
bash skills/daily-report/scripts/link_google_calendar.sh
```

비공개 iCal 주소 자체가 자격증명입니다. 주소는 스크립트가 사용하는 사용자 설정 파일에만 두며 저장소, 스냅샷, 로그, 문서에 복사하지 않습니다. 피드 특성과 알려진 제한은 [calendar setup](../../skills/daily-report/references/calendar-setup.md)에 있습니다.

## 호스트 동기화의 격리 경계

`herdr/cron/host-sync.mjs`는 개인 호스트에서 선택한 공개 가능한 설정의 변경을 검토하기 위한 guard입니다. 실행 전에 [REPO의 격리 경계](../REPO.md#harness-host-sync의-격리-경계)를 읽습니다.

핵심 경계는 다음과 같습니다.

- 사람이 작업 중인 원본 checkout을 전환·stash·reset·rebase하지 않습니다.
- 편집 후보는 별도 작업공간에 만들고 코드의 허용 목록 밖 변경을 거부합니다.
- 예시 스냅샷에서 개인 호스트 상태를 자동 복원하거나, 호스트 파일을 공개본으로 일괄 복사하지 않습니다.
- 검사 뒤 원본이나 원격이 바뀌면 자동으로 합치거나 덮어쓰지 않고 중단합니다.
- 원격 게시 여부는 소유자의 별도 결정입니다. 이 문서는 기본 브랜치로 직접 게시하는 레시피를 제공하지 않습니다.

분산된 `herdr/cron/jobs.snapshot.yaml`은 `version: 1`과 빈 `jobs` 목록만 가지므로 예약 실행을 설치하거나 재현하지 않습니다. 실제 일정을 만든다면 공개본 밖의 로컬 설정에서 각 작업의 입력, 비용, 권한, 알림, 실패 처리를 검토합니다.

## AGY 권한 설정

`agy/settings.snapshot.json`은 개인 설정 선택을 보여 주는 예시이며 복원 입력이 아닙니다. 포함된 `always-proceed` 정책은 승인 대화를 생략하는 개인 선택이므로 새 환경의 보안 기본값으로 권장하지 않습니다. 파일 도구의 allow/deny 설정은 임의 shell 접근을 격리하는 샌드박스가 아닙니다.

AGY를 Herdr나 비대화형 흐름에서 실행할 때에는 작업공간과 모델을 명시적으로 확인합니다. `harness-run`은 프로필의 모델 ID를 실행 인자로 전달하지만 전역 AGY 설정을 안전하게 바꾸거나 권한을 축소한다고 주장하지 않습니다.

## 스냅샷 유지관리

스냅샷은 사람이 최소 공개 필드만 골라 작성하고 검토합니다. 홈 디렉터리의 설정 파일을 통째로 복사하는 갱신 절차를 사용하지 않습니다.

- `omp/config.snapshot.yml`과 `agy/settings.snapshot.json`은 공개 가능한 비교 예시만 유지합니다.
- `third-party/skills.lock.json`과 `herdr/plugins.manifest.json`에는 공개 접근 가능한 의존성과 필요한 핀만 둡니다.
- `herdr/cron/jobs.snapshot.yaml`은 빈 일정 상태를 유지합니다.
- 자격증명, 절대 개인 경로, trusted workspace, 비공개 URL, 실제 일정, 실행 기록은 스냅샷에서 제외합니다.

스냅샷을 바꾼 뒤에는 diff에서 새 키와 값을 직접 검토합니다. 무시되는 호스트 파일도 강제 추가하면 공개될 수 있으므로 `.gitignore`를 승인 경계로 취급하지 않습니다.
