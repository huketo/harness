# Linux 샌드박스 SDK 경계

이 스킬은 `cua==0.1.6`, `cua-sandbox==0.8.0`을 사용하는 래퍼를 배포한다. 아래는 해당 버전을 대상으로 한 구현상의 제약이며 다른 버전의 호환성을 약속하지 않는다. 공개본에서 실행 검증한 결과를 뜻하지 않는다.

- `Image.linux(kind="container")`는 공개 이미지 `public.ecr.aws/k5j5w0x5/cua-ubuntu-24.04:docker-latest`를 사용한다. SDK 버전 핀과 달리 이 이미지 태그는 가변이므로 이미지 내용이나 다운로드 크기는 고정하지 않는다.
- SDK Docker 런타임은 computer-server API(8000, 인증 없는 root 셸)와 noVNC(6080)를 `-p`로 게시한다. 래퍼의 `LoopbackPublish`는 자신의 프로세스 안에서 포트 인자를 `127.0.0.1:`로 바꿔 다른 호스트에 직접 게시하지 않도록 한다. 원격 전달이나 터널은 별도 권한이 필요한 외부 노출이다.
- SDK 런타임이 생성 전에 같은 이름의 컨테이너를 제거할 수 있으므로 `up`은 같은 이름이 이미 있으면 거부한다. 작업별 고유 이름을 사용한다.
- 래퍼는 `Sandbox.create`와 `Sandbox.connect`에 `telemetry_enabled=False`를 넘긴다.
- 로컬 전송의 표시 URL 대신 `url` 명령이 Docker의 게시된 6080 포트를 읽어 noVNC 주소를 만든다.
- 키 이름은 `Return` 대신 `enter`처럼 소문자 형식을 사용한다.

의존성은 공개 [cua 프로젝트](https://github.com/trycua/cua)의 패키지이며 이 저장소에 SDK 소스나 컨테이너 이미지를 편입하지 않는다. 패키지·이미지 자체의 라이선스와 배포 조건은 해당 프로젝트가 소유한다.
