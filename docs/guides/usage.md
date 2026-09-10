# 상세 사용법

[문서 색인](../index.md) · [English overview](../../README.md) · [한국어 개요](../../README.ko.md)

이 문서는 명령의 세션·공용 상태 경계와 호스트에서 확인한 제약을 설명합니다. 명령은 저장소 루트에서 실행합니다. 설치 조건은 [설치 안내](installation.md)를 먼저 확인합니다. 모델 가용성과 공급자 동작은 설치 버전에 따라 달라집니다.

## AFK와 자율 결정

사람이 응답할 수 없을 때는 `herdr-hitl afk`를 실행합니다. `herdr-hitl afk --for 2h`처럼 기간을 정할 수 있고, `herdr-hitl here`로 해제하거나 `herdr-hitl away`로 메신저 수신 가능한 부재 상태를 선언할 수 있습니다. 상태 전환은 사람의 명령이며 에이전트가 대신 실행하지 않습니다.

AFK 중 `herdr-hitl channel`은 `afk`를 출력합니다. 명시적인 `--channel messenger`보다 우선하며 `ask`와 `notify`는 전송 전에 종료 코드 `6`으로 거절됩니다. 답변이나 `--default` 승인을 만들지 않습니다. 만료 뒤에는 기존 채널 설정을 따릅니다.

에이전트는 `herdr-hitl` 스킬의 자율 결정·쿼럼·유예 정책을 따릅니다. 범위 내 가역 결정은 근거로 처리하고, 중요한 기술적 갈림은 쿼럼으로 검토합니다. 사람만 결정할 수 있는 사항은 해당 작업만 유예하고 독립적인 승인 작업을 계속합니다. CLI 자체가 모델을 실행하거나 새 권한을 부여하지는 않습니다.

OMP 세션에서는 `harness-herdr` 확장이 내장 `ask` 도구를 기계적으로 막습니다. 모델이 `ask`를 호출하면 확장의 `tool_call` 훅이 `herdr-hitl channel -o json`을 먼저 실행하고, 채널이 `terminal`일 때만 통과시킵니다. `messenger`이면 `herdr-hitl ask`를 쓰라는 오류를, `afk`이면 질문·알림 없이 자율 결정·쿼럼·유예 정책을 적용하라는 오류를 도구 결과로 돌려주며, `herdr-hitl channel` 자체가 실패하거나 알 수 없는 채널을 내면 안전 방향으로 차단합니다. `herdr-hitl`이 설치되지 않은 환경(`ENOENT`)만 게이트 밖입니다. 시스템 프롬프트의 산문 지시가 지켜지지 않아도 `ask`가 사람 없는 화면으로 흘러가지 않게 하는 장치이며, `herdr-hitl ask`나 응답 본문의 질문에는 개입하지 않습니다. 검증은 `bun test omp/extensions/herdr/herdr.test.ts`입니다.

CLI·판단 정책 정본은 [herdr-hitl](https://github.com/huketo/herdr-hitl)이고 이 저장소는 검증한 플러그인 커밋과 스킬 해시를 기록합니다.

## 계정·모델·보이는 실행

`bash install.sh`는 OMP의 `profiles`와 `herdr` 확장 두 개와 `omp-profile`, `harness-run` 명령을 연결합니다. 이전 `harness-accounts`와 `harness-native-compaction` 링크는 이 체크아웃이 소유한 링크로 확인될 때만 제거합니다. 다른 파일·디렉터리·심링크는 충돌로 보존하며 dry-run에서는 아무것도 제거하지 않습니다. 설치 후 이미 로드된 OMP 프로세스를 다시 시작합니다.

### 계정 선택

OMP에서 `/session pin`을 사용하면 OMP에 등록된 OAuth 계정 중 현재 세션에서 사용할 계정을 직접 선택할 수 있습니다. 이 기능은 OMP 본체가 제공하며 별도 Harness 확장이나 런타임 패치가 필요하지 않습니다. 선택은 세션마다 수동으로 수행하며 Harness는 계정 선택을 다른 세션에 저장하거나 동기화하지 않습니다.

설치기는 OMP의 인증 저장소, 기존 선호 상태, 세션 transcript를 복제하거나 변경하지 않습니다. 이전 accounts 확장이 남긴 공용 선호 상태도 그대로 두지만 더 이상 적용하지 않습니다. API 키와 환경 변수 인증은 OAuth 계정 선택과 별개이며, 실제 인증 실패와 한도 처리 방식은 OMP 본체가 결정합니다. 기존 `task` 서브에이전트는 `Alt+A`의 Agent Hub에서도 조회·조종할 수 있습니다.

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

Fable 5.1·Astra는 medium, Opus 5·Sol은 코딩 high와 일반 작업 medium, Luna는 max를 사용합니다. Flash의 기계적 작업·검색·미디어·자동화 프로필은 high입니다. AGY Opus 4.6 Thinking의 `fallback` 프로필은 별도 effort 선택을 지원하지 않습니다. 실제 이름과 최종 모델·effort는 `list`·`show` 출력이 정본입니다. 확정되지 않은 “최적 effort”나 서로 다른 실행기 사이의 강도 동등성을 주장하지 않습니다.

컨텍스트는 실행 중 모델의 실제 한도와 출력 여유를 기준으로 관리합니다. 네이티브 압축 지원과 다른 제공자로의 이동은 구분하며, 이동 전 읽을 수 있는 인계문을 사용합니다. 긴 대화에서 `/model`로 바로 바꾸기보다 `/profile`의 보호된 전환을 사용합니다. AGY의 내부 압축 설정은 OMP에서 조절할 수 없습니다. 모델별 공식 근거와 그 한계는 [FACTS 8절](../FACTS.md#8-모델-프로필컨텍스트-정책의-근거-2026-09-07)에 있습니다.

### 내장 자동 압축

관리 설정은 OMP 내장 압축의 여섯 가지 정책 키를 다음 값으로 고정합니다.

| 키 | 값 |
| --- | --- |
| `compaction.enabled` | `true` |
| `compaction.methodOrder` | `remote`, `handoff`, `soft` |
| `compaction.keepRecentTokens` | `40000` |
| `compaction.thresholdPercent` | `75` |
| `compaction.thresholdTokens` | `-1` |
| `compaction.handoffSaveToDisk` | `true` |

일반 자동 압축과 수동 `/compact`는 별도 Harness native hook 없이 OMP 본체가 처리합니다. `remote`, `handoff`, `soft`는 순서대로 시도되며, 한 방법이 필요한 공간을 확보하면 다음 방법은 실행하지 않습니다. Remote compaction과 handoff 요약은 공급자 API를 호출하여 비용이 발생할 수 있습니다.

프로필 확장은 같은 공급자에서 이어지는 일반 입력을 선제 압축하지 않습니다. 모델 전환 때에는 대상 모델의 컨텍스트와 출력 budget을 확인합니다. OMP 내장 `openaiRemoteCompaction` 상태를 유지한 채 공급자를 넘는 경우에는 읽을 수 있는 `soft` 인계문을 만든 뒤 전환합니다.

```text
/compact
/profile frontend
```

설치기는 인증 정보, 선호 상태, 세션 transcript, 백업을 변경하지 않습니다. 다만 기존 `harnessNativeCompaction` 상태의 replay와 `/native-compact portable` 이전 경로는 제거되었습니다. 해당 상태에 의존하는 기존 transcript가 디스크에 남아 있어도 세션 재개를 보장하지 않습니다. 새 정책을 적용한 뒤에는 기존 OMP 프로세스를 다시 시작합니다.

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

## 인터페이스 개선과 검토

[`awesome-interface`](../../skills/awesome-interface/SKILL.md)는 제품 UI의 접근성·배치·문구·타이포그래피·색상·시각적 완성도를 다룹니다. 작은 요청은 필요한 전문 문서만 읽고, 전체 검토는 여섯 영역을 모두 검토합니다.

- “awesome-interface로 이 오류 문구만 고쳐 주세요.”
- “이 화면을 전체 검토하되 수정하지 마세요.”
- “현재 브랜치의 UI 변경을 리뷰하고 회귀를 구분해 주세요.”
- “이 컴포넌트의 긴 문구·좁은 화면 스트레스 테스트를 해주세요.”
- “원본을 유지하면서 두 디자인 대안을 비교하게 해주세요.”

리뷰만 요청하면 소스를 수정하지 않습니다. 변경 리뷰·스트레스·대안 생성·외부 UI 설명은 해당 작업을 명시적으로 요청했을 때만 수행합니다. 이 구분은 스킬 내부의 행동 조건이며 호스트가 기능별 호출을 강제 차단한다는 뜻은 아닙니다. 기존 색상 표기·토큰·컴포넌트를 유지하며 마이그레이션은 별도 요청이 필요합니다.

설치는 기존 `install.sh`의 스킬 링크 경로를 사용합니다. 이미 설치된 `better-*`, `interface-review`, `break`, `variant`, `explain-interface`를 교체할 때에는 먼저 수정본과 참조를 탐색 경로 밖에 백업하고 설치 관리자의 등록 여부를 확인합니다. 등록된 항목은 관리자의 제거 명령을 사용하고, 미등록 사본은 백업 후 탐색 경로에서 옮깁니다. 새 스킬과 이전 사본을 함께 활성화하지 않습니다. 설치 직후 기존 대화의 목록은 그대로일 수 있으므로 새 세션에서 확인합니다.

검증용 합성 입력과 기대 동작은 [`evals/evals.json`](../../skills/awesome-interface/evals/evals.json)에 있습니다. 각 사례는 `files`의 fixture를 같은 상대 경로로 배치한 격리 작업공간에서 실행합니다. 실제 모델 응답과 캡처는 버전 관리하지 않습니다.
