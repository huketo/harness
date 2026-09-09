# C2PA로 생성 출처 확인

도구가 실제 이미지 모델을 반환하지 않을 때 원본 파일의 C2PA 매니페스트를 검사한다. 메타데이터를 보존한 원본을 대상으로 하며, 화면 캡처·리사이즈·재인코딩한 사본을 원본처럼 검사하지 않는다.

## 도구와 실행

공식 [c2patool 설치 안내](https://github.com/contentauth/c2pa-rs/blob/main/cli/README.md)를 따른다. 배포 바이너리는 공식 release의 checksum을 확인한다. 이미 설치된 도구가 있으면 재사용하며, 없다는 이유로 출처를 추정하지 않는다.

```bash
c2patool --version
c2patool /absolute/path/to/original.png
c2patool /absolute/path/to/original.png trust \
  --trust_anchors https://raw.githubusercontent.com/c2pa-org/conformance-public/refs/heads/main/trust-list/C2PA-TRUST-LIST.pem
```

마지막 명령은 공식 신뢰 목록을 네트워크로 읽는다. 배치에서는 한 번 내려받은 PEM 파일 경로를 재사용하고 출처·확인 시점을 남긴다. 매니페스트 검사에 `--manifest`, `--create`, `--update`를 사용하지 않는다. 이 옵션들은 출처를 읽는 것이 아니라 새 기록을 작성한다.

## 판독

최상위 `active_manifest`가 가리키는 매니페스트를 읽는다. 참조 이미지인 ingredients의 모델을 현재 결과 모델로 오인하지 않는다.

| 필드 | 의미 |
| --- | --- |
| `claim_generator_info` | 매니페스트를 작성한 소프트웨어. 이미지 생성 모델과 같다고 가정하지 않는다. |
| `assertions`의 `c2pa.actions*` → `c2pa.created` → `softwareAgent` | 생성 동작에 기록된 이름·버전. 존재하는 값만 인용한다. |
| `digitalSourceType` | AI 생성 등 출처 유형. 특정 모델을 증명하지 않는다. |
| `signature_info` | 서명자 정보. 문자열 존재만으로 신뢰 검증을 대신하지 않는다. |
| `validation_results` / `validation_state` | 서명·데이터 해시·신뢰 체인 검증 결과. exit 0만 확인하지 않는다. |

기본 실행의 `Valid`와 공식 신뢰 목록을 적용한 `Trusted`는 구별한다. `claimSignature.validated`와 `assertion.dataHash.match`가 있어도 `signingCredential.untrusted`가 남으면 신뢰된 발행자까지 검증됐다고 쓰지 않는다. 실패·변조·미신뢰 결과에서는 모델명을 검증된 사실로 승격하지 않는다.

표시는 `C2PA 기록: gpt-image / 2.0 · Trusted`처럼 **기록된 주장과 검증 수준**을 함께 적는다. 이는 서명된 출처 기록을 검증한 것이지 모델 내부 구현을 독립적으로 감정한 것은 아니다. 이후 편집·합성이 기록되어 있다면 생성 동작 하나만으로 전체 결과의 유일한 생성 모델을 단정하지 않는다.

모델 버전이 없으면 `Google 생성 출처 검증 · 세부 모델 미기재`처럼 표시한다. SynthID 적용 기록, Google 대화 모델명, 파일명만으로 Nano Banana 2라고 결론 내리지 않는다. C2PA가 없다는 사실 역시 비AI 또는 특정 모델 사용의 증거가 아니다.

## 비교에 반영

원본 이미지와 JSON 보고서를 함께 보존한다. 비교 데이터의 `image_model`에 기록된 이름/버전, `notes`에 C2PA 검증 수준과 한계를 넣는다. `image_model_verified`는 해당 모델 기록과 서명·파일 결합·발행자 신뢰까지 확인했을 때만 true로 둔다. 정보가 없으면 false로 둔다.

출처: [c2patool 사용법과 trust 옵션](https://github.com/contentauth/c2pa-rs/blob/main/cli/docs/usage.md), [공식 C2PA trust list](https://github.com/c2pa-org/conformance-public/blob/main/trust-list/C2PA-TRUST-LIST.pem).
