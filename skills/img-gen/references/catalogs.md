# 참고 카탈로그와 결과 비교

카탈로그는 참고 자료를 고르는 도구이고, 비교 화면은 새로운 요청에 기법을 적용한 결과를 보는 도구다. 선택한 모든 항목의 재현을 약속하지 않는다. 원본 이미지는 생성 입력에 자동 첨부하지 않는다.

## 원본 카탈로그

[GPT-Image2-Skill](https://github.com/wuyoscar/GPT-Image2-Skill)을 별도 작업 디렉터리에 클론한다. upstream 코드나 설치 스크립트를 실행할 필요는 없다.

```bash
git clone --depth 1 https://github.com/wuyoscar/GPT-Image2-Skill.git /absolute/upstream
python3 /absolute/img-gen/scripts/build_catalog.py \
  --upstream /absolute/upstream --output /absolute/catalog
```

새 산출물 전용 디렉터리를 지정한다. 빌더는 그곳의 assets를 재생성하므로 사용자 파일이 들어 있는 디렉터리를 출력으로 사용하지 않는다. 결과는 `index.html`, `catalog.json`, `assets/`다. 전체 디렉터리를 함께 열거나 로컬 정적 서버로 제공한다. 프롬프트·출처·이미지 연결과 누락 표시를 확인한다.

Pillow가 있으면 썸네일을 만들고, 없으면 원본 파일을 미리보기로 사용한다. 후자는 로딩량이 커질 수 있다. 원본 이미지와 프롬프트의 권리·개별 출처는 upstream MIT 표시와 별도로 확인한다. 로컬 검토가 원격 재배포 승인이나 모든 외부 소재의 이용허락을 뜻하지 않는다.

선택 JSON은 `schema_version`, `upstream_commit`, `selected_ids`, `notes`를 가진다. 사용자의 선택을 기법별로 묶고 필요한 대표 예제만 사용한다. 취향 참고인지, 직접 재현 요청인지 구별한다.

## 결과 비교

```bash
python3 /absolute/img-gen/scripts/build_comparison.py \
  --catalog /absolute/catalog/catalog.json \
  --results /absolute/results.json --output /absolute/comparison
```
출력은 catalog.json과 results.json이 있는 디렉터리와 다른 전용 디렉터리를 지정한다. 사례별 `reference_ids`는 참고 원본 1~3개다.


`results.json`의 구조:

```json
{
  "schema_version": 1,
  "title": "참고 기법의 새 요청 적용",
  "description": "원본 재현이나 통제된 모델 벤치마크가 아닌 결과 비교",
  "cases": [
    {
      "id": "new-subject",
      "title": "새 주제에 적용한 예제",
      "pattern_id": "product-brand",
      "short_prompt": "사용자의 짧은 요청",
      "expanded_prompt": "실제 생성에 전달한 확장 프롬프트",
      "checks": ["관찰 가능한 요청 조건"],
      "reference_ids": ["product-chocolate-wafer"],
      "runs": [
        {
          "id": "omp-result",
          "label": "OMP 네이티브",
          "runtime": "omp",
          "agent_model": "실제 대화 모델과 effort",
          "image_model": "미확인",
          "image_model_verified": false,
          "status": "pending",
          "image_path": null,
          "elapsed_seconds": null,
          "notes": ["아직 생성하지 않음"]
        }
      ]
    }
  ]
}
```

성공 상태에는 실제 결과 파일 경로를 넣는다. 이미지 경로는 results.json 기준 상대 경로나 절대 로컬 경로다. 실패는 `error`, 미실행은 `pending`으로 남기고 다른 이미지로 메우지 않는다. 각 run의 입력이 확장 프롬프트와 달라졌다면 notes에 차이를 명시한다. 반복 수정 결과와 최초 결과를 구별한다.

`image_model_verified`는 대화 모델명을 아는지만으로 true가 되지 않는다. [출처 검사](provenance.md) 결과에 맞춰 이미지 모델 기록, 신뢰 검증 수준, 미기재 항목을 notes에 넣는다. C2PA의 모델 기록과 실제 런타임 설정을 함께 보존한다.

산출물을 직접 브라우저로 열어 실제 이미지·출처 링크·프롬프트·실패 표시와 좁은 화면을 확인한다. 생성 파일과 전체 C2PA JSON은 원본 상태로 별도 보존한다. 비교 HTML은 해당 파일을 재인코딩하지 않는다.
