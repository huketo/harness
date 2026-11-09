# 근거와 SDK 경계

## Windows 호스트 driver (2026-09-29, WSL2 Ubuntu 24.04)

### 이 스킬이 MCP가 아니라 CLI를 쓰는 이유

Windows `cua-driver` 0.30.4의 `mcp` 서버는 도구 59개를 광고하며 `tools/list` 스키마는 176,595자다(0.23.2는 57개, 158,626자). MCP로 상시 등록하면 모든 요청과 서브에이전트 요청에 약 4만 토큰이 실린다. CLI(`cua-driver call`)는 필요할 때만 비용이 든다. 다만 CLI 호출은 매번 새 전송 lease다. 0.30.4에서는 앞 호출의 `element_token`이 다음 호출에서 `stale_element_token`으로 거부된다(0.23.2는 통과). 호출마다 같은 `session` 라벨을 주면 유지되므로, `scripts/cua-win`은 스키마에 `session`이 있는 도구(59개 중 38개)에만 이 라벨을 넣는다. `session`을 선언하지 않은 도구는 `additionalProperties: false`다. WinForms 테스트 창에서 별도 호출의 `click`이 `count`를 올렸고, `type_text`는 `effect: confirmed`였다.

### WSLg는 대상이 아니다

WSL의 Linux `cua-driver` 0.30.4로 WSLg를 확인한 결과는 다음과 같다.

- X11(XWayland): `list_windows`가 빈 목록을 반환한다. WSLg의 창 관리자는 `_NET_SUPPORTED`로 7개 항목만 알리고 `_NET_CLIENT_LIST`를 비워 둔다. `get_desktop_state`는 rootless XWayland에서 `GetImage` BadMatch로 실패한다. 창 id를 직접 알면 창 하나의 캡처만 된다.
- Wayland(`CUA_DRIVER_RS_ENABLE_WAYLAND=1`): `health_report` 기준 foreign-toplevel·screencopy·virtual-pointer·libei가 모두 없다.

## Linux 샌드박스 SDK 경계

이 스킬은 `cua==0.1.6`, `cua-sandbox==0.8.0`을 사용하는 래퍼를 배포한다. 아래는 해당 버전을 대상으로 한 구현상의 제약이며 다른 버전의 호환성을 약속하지 않는다. 공개본에서 실행 검증한 결과를 뜻하지 않는다.

- `Image.linux(kind="container")`는 공개 이미지 `public.ecr.aws/k5j5w0x5/cua-ubuntu-24.04:docker-latest`를 사용한다. SDK 버전 핀과 달리 이 이미지 태그는 가변이므로 이미지 내용이나 다운로드 크기는 고정하지 않는다.
- SDK Docker 런타임은 computer-server API(8000, 인증 없는 root 셸)와 noVNC(6080)를 `-p`로 게시한다. 래퍼의 `LoopbackPublish`는 분리된 `-p HOST_PORT:CONTAINER_PORT` 형식만 `127.0.0.1:`로 바꾸고, 다른 publish 옵션이나 매핑은 Docker 실행 전에 거부한다. 이 argv 경계는 `scripts/test_cua_sandbox.py`가 SDK import와 subprocess 전송만 대체하여 검증하며 실제 컨테이너 실행 검증은 아니다. 원격 전달이나 터널은 별도 권한이 필요한 외부 노출이다.
- SDK 런타임이 생성 전에 같은 이름의 컨테이너를 제거할 수 있으므로 `up`은 같은 이름이 이미 있으면 거부한다. 작업별 고유 이름을 사용한다.
- 래퍼는 `Sandbox.create`와 `Sandbox.connect`에 `telemetry_enabled=False`를 넘긴다.
- 로컬 전송의 표시 URL 대신 `url` 명령이 Docker의 게시된 6080 포트를 읽어 noVNC 주소를 만든다.
- 키 이름은 `Return` 대신 `enter`처럼 소문자 형식을 사용한다.

의존성은 공개 [cua 프로젝트](https://github.com/trycua/cua)의 패키지이며 이 저장소에 SDK 소스나 컨테이너 이미지를 편입하지 않는다. 패키지·이미지 자체의 라이선스와 배포 조건은 해당 프로젝트가 소유한다.
