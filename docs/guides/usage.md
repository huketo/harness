# 상세 사용법

[문서 색인](../index.md) · [English overview](../../README.md) · [한국어 개요](../../README.ko.md)

이 문서는 명령의 세션·공용 상태 경계와 호스트에서 확인한 제약을 설명합니다. 명령은 저장소 루트에서 실행합니다. 설치 조건은 [설치 안내](installation.md)를 먼저 확인합니다. 모델 가용성과 공급자 동작은 설치 버전에 따라 달라집니다.

## 계정·모델·보이는 실행

`bash install.sh`는 OMP 확장 네 개(accounts, profiles, herdr, native-compaction)와 `omp-profile`, `harness-run` 명령을 연결하고, 계정 선택·네이티브 압축을 위한 OMP 18.1.13 전용 런타임 호환 패치를 설치합니다. 인증 저장소를 복제하지 않습니다. 설치 후 OMP를 재시작합니다.

### 계정 선택

OMP에서 `/account`를 입력하면 현재 모델의 provider에 등록된 OAuth 계정 선택기가 열립니다. `/account list`로 목록을 보고 `/account 1`처럼 번호로 선택할 수도 있습니다. `/fresh` 등으로 대화 기록 ID와 모델 요청의 세션 ID가 달라진 상태에서도 `/account`는 실제 요청 ID에 선택을 적용합니다. `/account auto`는 자동 선택으로 돌립니다. API 키나 환경 변수 인증은 이 OAuth 계정 목록과 별개입니다.

`/account 1 --profile`은 현재 provider의 계정을 **공용으로 저장하고 다른 세션에도 일괄 적용**합니다. 같은 OMP agent 디렉터리를 사용하는 기존 세션과 새 세션이 대상이며, 기존 세션별 선택보다 우선합니다. 현재 세션은 즉시, 다른 세션은 다음 모델 요청 전(도구 실행 후 이어지는 요청 포함)에 반영합니다. 진행 중인 요청은 중단하지 않습니다. **호환 패치 설치 전부터 실행 중인 OMP는 재시작해야 합니다.** `/reload-plugins`만으로는 CLI 런타임이 갱신되지 않으며, 요청 ID를 제공하지 않는 런타임에서는 계정 변경을 거부하고 설치·재시작을 안내합니다.

`/account --profile`은 공용 계정 선택기, `/account list --profile`은 공용 선택 상태를 포함한 목록입니다. `/account auto --profile`은 공용 고정을 해제하고 다른 세션의 선택도 다음 요청 전 자동 선택으로 돌립니다. 이후 `/account 1` 같은 세션별 선택을 다시 사용할 수 있습니다. 공용 고정 중에는 `--profile` 없는 변경을 막고 해제 방법을 안내합니다.

저장 위치는 기본적으로 `~/.omp/agent/harness-accounts/<provider>.json`입니다. 계정 번호가 아니라 credential ID를 저장하므로 목록 순서 변경에 영향을 받지 않으며 토큰은 복사하지 않습니다. OMP 실행 옵션 `--profile`이나 `PI_CODING_AGENT_DIR`로 격리한 다른 인증 프로필은 변경하지 않습니다. 용도별 `/profile code` 등의 모델 프로필과는 별개입니다.

두 선택 방식 모두 OMP의 기존 `/session pin`을 사용하므로 인증 오류·한도 소진 시 본체가 다른 계정으로 전환할 수 있습니다. 과금을 한 계정으로만 제한하는 엄격한 잠금은 아닙니다. 기존 `task` 서브에이전트는 `Alt+A`의 Agent Hub에서도 조회·조종할 수 있습니다.

### 용도별 모델과 effort

```bash
omp-profile list
omp-profile show frontend
omp-profile selector code             # OMP의 provider/model:effort
omp-profile argv media                # AGY 등 실행기에 맞는 argv를 JSON으로 출력
```

OMP 안에서는 `/profile` 선택기 또는 `/profile code`로 용도를 선택합니다. `/effort high`는 **현재 세션의 현재 모델에만** 적용하며 공용 설정을 쓰지 않습니다. 같은 모델로 작업하는 다른 세션에는 영향을 주지 않고, 다음 요청에서도 유지됩니다. `/effort reset`은 이 세션의 임시 변경을 해제합니다. 세션별 변경은 대화 기록에 남아 같은 대화를 재개하면 복원되며, `/profile`로 용도를 명시적으로 다시 선택하면 해당 모델의 임시 변경을 해제하고 선택한 용도의 설정을 적용합니다.

`/effort low --profile`은 선택한 용도의 **공용 저장값**을 바꾸고 현재 세션의 임시 변경을 해제합니다. 같은 용도를 사용하는 다른 세션에도 적용될 수 있지만, 그 세션에 별도 임시 effort가 있으면 그것을 우선합니다. `/effort reset --profile`은 공용 용도 저장값을 해제합니다. 공용값은 `~/.omp/agent/harness-profiles-state.json`, 용도 정본은 `omp/profiles.json`입니다. 기존 공용 모델 기본값과 `omp-profile effort set` CLI의 명시적 저장 동작은 유지합니다.

내장 `smol`·`mid`·`slow` 역할은 기존 서브에이전트와의 호환에만 사용합니다. 이 용도 프로필은 인증·세션 전체를 격리하는 OMP의 `--profile` 옵션과 다릅니다.

Fable 5.1·Astra는 high를 비교 시작값으로 둡니다. Opus 5·Sol은 코딩 high와 일반 작업 medium을 구분하고 Luna는 max를 사용합니다. Flash에는 기계적 작업·검색·미디어·자동화 프로필을, AGY Opus 4.6에는 명시적인 fallback 프로필을 둡니다. 실제 이름과 최종 모델·effort는 `list`·`show` 출력이 정본입니다. 확정되지 않은 “최적 effort”나 서로 다른 실행기 사이의 강도 동등성을 주장하지 않습니다.

컨텍스트는 실행 중 모델의 실제 한도와 출력 여유를 기준으로 관리합니다. 네이티브 압축 지원과 다른 제공자로의 이동은 구분하며, 이동 전 읽을 수 있는 인계문을 사용합니다. 긴 대화에서 `/model`로 바로 바꾸기보다 `/profile`의 보호된 전환을 사용합니다. AGY의 내부 압축 설정은 OMP에서 조절할 수 없습니다. 모델별 공식 근거와 그 한계는 [FACTS 8절](../FACTS.md#8-모델-프로필컨텍스트-정책의-근거-2026-09-07)에 있습니다.

### 네이티브 compaction

`omp/extensions/native-compaction`이 지원 모델의 자동·수동 압축을 처리합니다. 기존 공급자·모델 선택자와 OMP 인증을 유지합니다.

- **OpenAI Codex(Astra·Sol·Luna):** 실제 Codex가 지원하는 V2 Responses 압축을 사용합니다. 현재 경로의 standalone `/responses/compact`는 실측에서 404를 반환했습니다.
- **일반 OpenAI Responses:** standalone `/responses/compact`의 반환 창 전체를 보존합니다. reasoning·도구 호출·결과를 필터링하지 않습니다.
- **Claude:** `compact-2026-01-12` / `compact_20260112`로 서버 압축을 요청하고, `pause_after_compaction`으로 결과를 확정한 뒤 다음 요청에 같은 블록을 재전송합니다. 재전송에도 베타와 전략이 필요합니다. 별도 압축 없이 읽을 수 있는 handoff로 대체하지 않습니다.

```text
/native-compact           # 지금 네이티브 압축
/native-compact portable  # 다른 공급자로 이동할 읽기 가능한 인계문
/profile frontend        # 필요하면 portable 변환 후 모델 전환
```

Claude의 네이티브 압축에는 최소 50,000 입력 토큰이 필요합니다. 짧은 대화·API 오류·취소를 압축 성공으로 표시하지 않으며, 원본 대화를 유지합니다. 압축 상태는 세션에 청크와 무결성 해시로 저장하여 OMP의 긴 문자열 잘림을 피하고 재개 시 복원합니다. 압축 사용량은 compaction 엔트리의 `details.usage`와 `details.totals`에 기록합니다. Claude는 `usage.iterations`를 합산하며, 이 별도 압축 비용을 기존 `omp stats`의 메시지 비용 총액에 자동 합산하지는 않습니다.

`bash install.sh`는 확장 링크와 **OMP 18.1.13 전용 호환 패치**를 설치합니다. 압축 관련 패치는 압축 이벤트만 180초까지 허용하고, 이미 압축된 짧은 대화도 portable 변환 훅에 도달하게 합니다. 같은 설치 경로가 위 계정 선택의 요청 세션 ID도 확장에 제공합니다. 확장의 인증·API 작업 제한은 합계 170초입니다. CLI 번들과 SDK 소스 원본은 각각 `.harness-native-original`로 보존합니다. 다른 버전·예상과 다른 코드에는 적용하지 않습니다.

```bash
bun omp/native-runtime.ts --check
```

**설치 후 실행 중인 OMP는 재시작해야 합니다.** OMP 업그레이드 후에는 호환 패치와 회귀 검사를 다시 확인해야 합니다. 전역 75%와 OpenAI 프로필 유휴 경계 70% 정책은 바꾸지 않았습니다. 실제 API·세션 검증 범위는 [FACTS](../FACTS.md#네이티브-compaction-구현검증)에 기록합니다.


### Herdr에서 실행하고 재사용하기

명령을 전부 Herdr로 보내지 않습니다. **실행이 오래 걸리거나, 사람이 진행을 확인해야 하거나, 사람이 함께 조작할 필요가 있는 경우**에 사용합니다. 짧은 조회·변환·검증은 기존 도구로 직접 실행하며 빌드·테스트도 예외가 아닙니다. Herdr 경로를 선택하면 현재 cwd를 유지하고 사용자 포커스를 빼앗지 않는 새 탭을 만듭니다.

```bash
harness-run --help
harness-run command --name dev --detach -- bun run dev
harness-run agent --profile code --name implementation
harness-run agent --profile media --name media-reader
harness-run list
harness-run read implementation
harness-run send implementation "앞선 작업의 검증 결과를 설명해 주세요."
harness-run wait dev --timeout 60000  # 대기 만료는 서버를 종료하지 않음
harness-run agent --profile code --name implementation --resume  # 종료한 프로세스의 대화 재개
```

이 도구로 띄운 독립 에이전트는 기존 `task`를 다른 창에 옮겨 놓은 것이 아닙니다. 별도의 대화이므로 브리프나 인계문을 명시적으로 전달합니다. 완료된 페인은 자동으로 닫지 않습니다. `--detach`는 실행 핸들만 반환하며 준비 완료를 보장하지 않습니다. 실행 중에도 `read`·`send`·`wait`를 사용할 수 있고, PTY를 통해 사람도 같은 터미널에 입력할 수 있습니다. 실행별 종료 상태·전체 로그는 `~/.local/state/harness-run/`에 보존하며 도구 응답은 로그의 마지막 64KiB로 제한합니다(`XDG_STATE_HOME`이 있으면 그 경로 사용). AGY 무인 실행은 print 프로세스의 종료 코드와 JSON `SUCCESS`를 모두 확인합니다. 상세 인자는 `harness-run --help`에서 확인합니다.

## WSL에서 Windows Chrome 쓰기

`playwright-cli`와 OMP의 `browser` 도구는 기본으로 WSL 안의 헤드리스 Chromium을 띄웁니다. 창이 보이고 로그인 상태가 남는 브라우저가 필요하면 `windows-chrome` 스킬이 Windows 호스트의 Chrome을 `http://127.0.0.1:9222`로 노출합니다.

```bash
node skills/windows-chrome/scripts/windows-chrome.js start   # 브릿지 + Chrome, 엔드포인트 출력
playwright-cli -s=win attach --cdp=http://127.0.0.1:9222
node skills/windows-chrome/scripts/windows-chrome.js stop    # Chrome 닫고 브릿지 내림
```

Windows 쪽 전제는 Chrome과 Node.js(`node.exe`) 두 가지뿐이며 방화벽 규칙, `netsh portproxy`, mirrored 네트워킹은 필요 없습니다. 헤디드 Chrome이 `127.0.0.1`에만 듣고 WSL→호스트 연결을 방화벽이 막기 때문에, 브릿지는 연결마다 Windows `node.exe` 릴레이를 interop으로 띄워 stdio로 잇습니다. Chrome은 `%LOCALAPPDATA%\windows-chrome\default` 전용 프로필을 씁니다. Chrome 136부터 기본 프로필에서는 원격 디버깅이 거부되기 때문입니다. 포트를 WSL 9222·Windows 19222로 나눈 이유와 실측값은 [FACTS](../FACTS.md) 7절에 있습니다.
