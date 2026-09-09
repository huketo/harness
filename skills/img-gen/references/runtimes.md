# 네이티브 실행

이 스킬은 이미지 API 클라이언트를 새로 구현하지 않는다. 현재 런타임의 제공된 이미지 도구를 사용한다. 도구 스키마가 이 문서보다 우선하며 지원하지 않는 옵션을 프롬프트 바깥의 인자로 만들어 전달하지 않는다.

## OMP

`generate_image`가 제공되면 그 도구를 사용한다. 장치로 제공되는 설치에서는 먼저 `read xd://generate_image`로 스키마를 읽고 `write xd://generate_image`에 JSON을 전달한다.

검증된 OMP 18.1.15 도구는 `subject`, `aspect_ratio`, `image_size`, `provider` 등을 받는다. 예:

```json
{
  "subject": "최종 이미지 프롬프트",
  "aspect_ratio": "1:1",
  "image_size": "1024x1024",
  "provider": "openai"
}
```

이 도구의 `model` 필드는 노출되지 않았다. 응답의 `Provider: openai-codex`와 `Model: gpt-6-astra`는 네이티브 라우팅 정보이며 실제 이미지 모델이 GPT Image 2.5라는 증거로 사용하지 않는다. 결과 파일의 실제 크기도 확인한다.

이미지 도구가 비활성화되어 있으면 이를 설명하고 한 번의 세션에만 적용하는 동봉 설정으로 OMP를 시작할 수 있다. 아래 경로는 설치 위치에 맞게 해석한다.

```bash
omp --config ~/.agents/skills/img-gen/assets/omp-native.yml
```

설정은 이미지 도구 노출만 켜며 인증이나 모델 기본값을 바꾸지 않는다. 실행 중인 세션에 도구가 자동 추가되었다고 가정하지 않는다. 영구 활성화는 사용자가 설치 효과를 승인했을 때만 `omp config set generate_image.enabled true`로 적용한다.

## Codex

현재 제공된 네이티브 이미지 도구를 사용한다. 검증된 Codex 0.153.4에서는 `image_gen.imagegen`이 `prompt`, `referenced_image_paths`, `num_last_images_to_include`를 제공했다. 생성은 `prompt`, 편집은 실제 원본의 참조 경로 또는 도구가 지원하는 이전 이미지 참조를 함께 전달한다.

도구에 없는 API `model`, `quality`, `size` 인자를 임의 추가하지 않는다. 필요 구도는 프롬프트로 표현하되 실제 결과 크기와 모델 식별 가능 여부는 별도로 확인한다. 네이티브 도구가 없으면 API 키를 요구하거나 다른 스킬의 API 스크립트로 조용히 전환하지 말고 가용 기능을 보고한다.

Codex는 `~/.agents/skills/img-gen/SKILL.md`를 발견할 수 있다. 설치 후 새 세션에서 스킬을 명시하여 발견과 실제 생성 모두 확인한다. 외부 결과 디렉터리를 쓰는 CLI 실행은 필요한 writable root만 허용한다.

```bash
codex --sandbox workspace-write --add-dir /absolute/output/directory
```

## AGY

AGY는 비교용 또는 사용자가 요청한 Google 네이티브 생성 경로다. 검증된 대화 모델은 `gemini-3.8-flash-high`이며, 이는 이미지 백엔드 이름이 아니다.

현재 `generate_image`는 `Prompt`, `ImageName`, `AspectRatio` 같은 필드를 제공한다. 실제 스키마에서 입력 이미지와 편집 지원을 확인한 뒤 사용한다. 반환 이미지의 경로와 실제 파일 형식을 확인한다.

`gemini-3.8-flash-high`로 실행했다는 사실만으로 결과를 Nano Banana 2라고 확정하지 않는다. 응답·도구에서 이미지 백엔드가 식별되지 않으면 `AGY 네이티브 · 이미지 모델 버전 미확인`으로 표시한다.

## 공통 증거

결과별로 runtime, 대화 모델/effort, 실제 이미지 모델 확인 여부, 최종 도구 입력, 결과 파일, 오류, 검수 메모를 구분한다. 옵션과 시간은 관측된 것만 기록한다. 프로세스 종료나 Herdr의 idle/done은 이미지 파일과 검수가 완료되었다는 증거가 아니다.

실제 모델 선택을 강제해야 하는 요청에는 지원되는 공식 API가 대안이지만, 별도 인증과 과금 경로 변경을 먼저 합의한다. 구독 네이티브 경로의 실행을 공식 API 모델 지정과 동등하게 설명하지 않는다.

## 모델 지정의 확인 한계

프롬프트에 이미지 모델명을 적는 것은 백엔드 선택이 아니다. [OMP issue #11322](https://github.com/can1357/oh-my-pi/issues/11322)가 다루는 hosted request의 `tools[].model` 필드도 요청값과 실제 응답을 구분해야 한다. 네이티브 인증을 재사용하는 확장으로 이 필드를 주입할 수는 있지만, 서버가 선택을 수용한다는 보장은 없다.
특정 모델에 종속된 요청 주입이나 인증 래퍼를 이 스킬에 추가하지 않는다. OMP/Codex가 네이티브 도구에 기능을 추가하면 현재 스키마를 읽고 그대로 적용한다. 실제 특정 이미지 모델이 필수인 요청이라면 도구·응답·원본 출처에서 확인 가능한 경로가 확보될 때까지 해당 생성 작업을 보류한다.
