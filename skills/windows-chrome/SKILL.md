---
name: windows-chrome
description: WSL에서 Windows 호스트의 Chrome을 CDP로 붙여 쓴다. 사용자가 Windows 쪽 Chrome, 실제 창이 보이는 브라우저, 로그인 상태가 남는 브라우저로 자동화·확인을 하자고 하거나, playwright-cli·OMP browser 도구를 호스트 Chrome에 attach해야 할 때 사용한다.
---

# Windows Chrome

WSL 안의 `playwright-cli`와 OMP `browser` 도구는 기본으로 Linux 헤드리스 Chromium을 띄운다. 이 스킬은 대신 Windows 호스트의 Chrome을 `http://127.0.0.1:9222`(CDP)로 노출한다. 창이 Windows 화면에 뜨고, 프로필이 디스크에 남아 로그인 상태가 유지되며, 사용자가 직접 개입할 수 있다.

## 순서

1. **연결** — 브릿지와 Chrome을 올리고 엔드포인트를 얻는다. 이미 떠 있으면 그대로 재사용한다.

   ```bash
   node scripts/windows-chrome.js start [url]     # ~/.agents/skills/windows-chrome/scripts/windows-chrome.js
   ```

   성공 출력은 `endpoint:`, `browser:`, `websocket:` 세 줄이다. 이후 모든 클라이언트는 `endpoint:` 값(`http://127.0.0.1:9222`)만 쓴다.

2. **attach** — 작업용 실제 탭을 먼저 정하고 도구별로 엔드포인트를 넘긴다. 기존 사용자 탭을 이동시키는 경우에는 그 탭의 사용 승인이 있어야 한다.

   ```bash
   playwright-cli -s=win attach --cdp=http://127.0.0.1:9222
   # 새 탭을 띄울 때
   playwright-cli -s=win open https://example.com
   ```

   ```javascript
   const tab = await browser.open({
     name: "win-review",
     app: { cdp_url: "http://127.0.0.1:9222", target: "https://example.com/review" },
   });
   console.log(await tab.url()); // 작업용으로 준비된 실제 탭인지 확인한 뒤 조작한다.
   ```

   `playwright-cli` 사용법은 `playwright-cli` 스킬을 따른다. 헤디드 브라우저라 포커스가 보장되지 않으므로 `type` 대신 ref나 locator를 받는 `fill`·`click`을 쓴다.

   OMP의 `name`은 도구 핸들 이름이지 Chrome 탭 ID가 아니다. 같은 CDP 엔드포인트에서 이름만 바꿔 열면 같은 실제 탭을 다시 채택할 수 있다. `app.target`은 URL/제목 부분 문자열이므로 작업용 탭 하나만 식별하는 값을 쓴다. 여러 작업을 나눌 때는 실제 탭을 각각 준비하고 서로 다른 target을 지정한다. `url`을 함께 넘기면 채택한 탭을 이동시키므로 대상 확인 전에는 생략한다.

   스크린샷에서 `The attached browser tab is not visible`이 나오면 URL/대상과 가시성을 확인한다. 사용자가 보고 있는 다른 탭의 픽셀을 읽지 않도록 하는 보호다. 작업 대상이 맞는지 해결한 뒤 공식 `tab.screenshot()`을 다시 쓰며, raw Puppeteer screenshot으로 보호를 우회하지 않는다.

3. **해제** — 작업이 끝나면 세션만 떼고 Chrome은 남긴다. 사용자가 브라우저를 닫아 달라고 할 때만 `stop`을 쓴다.

   ```bash
   playwright-cli -s=win close-session     # 브라우저는 그대로 두고 CLI 세션만 정리
   node scripts/windows-chrome.js stop     # Chrome을 닫고 브릿지를 내린다
   ```

   OMP에서는 `await tab.close()`로 관리 핸들을 해제한다. CDP로 붙은 실제 Chrome 탭은 닫지 않는다.

`status`는 브릿지와 Chrome의 상태를 보여 주며, 종료 코드 0은 연결 가능, 2는 브릿지만 살아 있음, 3은 둘 다 없음이다.

## 동작 방식

브릿지는 WSL의 `127.0.0.1:9222`에서 듣고, 연결마다 Windows `node.exe` 릴레이를 WSL interop으로 띄워 stdin/stdout을 Windows `127.0.0.1:19222`(Chrome)에 잇는다. 네트워크를 쓰지 않으므로 방화벽 규칙, `netsh portproxy`, mirrored 네트워킹, 관리자 권한이 필요 없다. 브릿지 프로세스는 `~/.local/state/windows-chrome/bridge-9222.{pid,log}`로 관리된다.

Chrome은 `%LOCALAPPDATA%\windows-chrome\<profile>`을 전용 프로필로 쓴다. Chrome 136부터 기본 프로필에서는 원격 디버깅이 거부되므로 사용자의 평소 Chrome 프로필은 쓸 수 없다. 처음 한 번 사이트에 로그인하면 이후에는 유지된다.

포트가 둘인 이유는 WSL의 localhost 포워딩이다. WSL 프로세스가 9222에서 들으면 `wslrelay.exe`가 Windows `127.0.0.1:9222`를 차지하므로, Chrome을 같은 포트에 두면 Chrome이 `::1`로 밀려나고 릴레이가 브릿지로 되돌아오는 루프가 생긴다. Chrome이 돌려주는 `ws://` URL은 요청의 `Host` 헤더로 만들어지므로 클라이언트 쪽 포트가 9222여도 그대로 브릿지로 향한다.

## 환경 변수

| 변수 | 기본값 | 뜻 |
| --- | --- | --- |
| `WINDOWS_CHROME_PORT` | `9222` | WSL 쪽 엔드포인트 포트 |
| `WINDOWS_CHROME_HOST_PORT` | `PORT + 10000` | Windows Chrome의 `--remote-debugging-port` |
| `WINDOWS_CHROME_PROFILE` | `default` | `%LOCALAPPDATA%\windows-chrome\` 아래 프로필 이름 |
| `WINDOWS_CHROME_EXE` | 자동 탐색 | `chrome.exe`의 WSL 경로 |
| `WINDOWS_NODE_EXE` | 자동 탐색 | Windows `node.exe`의 WSL 경로 |

## 실패 사례

- **`Chrome did not expose ... within 30s`** — 같은 프로필의 Chrome 창이 원격 디버깅 없이 이미 열려 있으면 새 실행이 그 창으로 흡수된다. 사용자에게 그 창을 닫아 달라고 한 뒤 다시 `start`한다. 다른 원인은 `~/.local/state/windows-chrome/bridge-9222.log`에서 확인한다.
- **`node.exe not found`** — Windows에 Node.js가 없다. 설치하거나 `WINDOWS_NODE_EXE`로 경로를 준다. Linux `node`는 Windows 소켓에 닿지 못하므로 대체가 안 된다.
- **`cannot listen on 127.0.0.1:9222`** — 다른 프로세스가 포트를 쓴다. `WINDOWS_CHROME_PORT`를 바꾸고 attach 주소도 같이 바꾼다.
- **Linux Chromium이 필요한 경우** — 헤드리스 스크린샷, 병렬 세션, CI 재현처럼 창이 필요 없는 작업은 이 스킬을 쓰지 않고 `playwright-cli open`이나 OMP `browser.open`의 기본 경로를 쓴다.
