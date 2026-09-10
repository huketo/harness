# 기술 발표 입력: 사내 작업 러너 TaskForge v2 릴리스와 마이그레이션

이 자료와 수치는 사내 교육 및 평가를 위해 작성한 가상 사례이다. 실존하는 회사, 제품, 인물 또는 실제 프로덕션 측정치가 아니다. 슬라이드 본문에서 합성 데이터임을 명시하고, 이를 실제 운영 환경의 성능 개선 성과로 단정하지 않는다.

## 청중과 목적

- 청중: TypeScript 기반 마이크로서비스를 개발·운영하는 사내 소프트웨어 엔지니어.
- 분량: 10분 발표 (발표 8분, 질의응답 2분, 슬라이드 7~10장 내외).
- 목적: TaskForge v2 신규 릴리스의 주요 변경점을 공유하고, 기존 v1 클라이언트 코드를 v2 러너 API로 마이그레이션하는 방법과 로컬 개발 환경 동작을 안내한다.
- 언어: 한국어. 코드 식별자, 패키지 이름, CLI 명령어는 영문 원문을 유지한다.
- 발표 형식: 발표자 주도(Speaker-driven) 발표. 발표자 노트에 각 슬라이드의 클릭 시점, 전환 타이밍, 예상 소요 시간을 명확히 배분한다.
- 디자인: 짙은 슬레이트 배경(#0f172a), 흰색 본문(#f8fafc), 민트 강조(#10b981), 주황 경고(#f97316). 간결하고 가독성 높은 엔지니어링 테마를 사용하며, 추가 디자인 승인 없이 제작한다.
- 산출물: Slidev 원본(마크다운), 오프라인 웹 빌드, 배포용 PDF, 발표자 노트.

## 발표장 환경과 제약

- 발표장 환경: 행사장 내부 네트워크 연결이 지원되지 않는다(오프라인 환경). 외부 CDN, 원격 웹 폰트, 외부 동영상 스트리밍 의존성 없이 로컬 자산만으로 웹 빌드가 완결되어야 한다.
- 배포본 요구사항: 발표 직후 청중에게 전달할 PDF 배포본을 함께 제작한다. 클릭 및 단계별 트랜지션이 적용된 슬라이드라도, PDF 변환 결과물에서 코드의 최종 형태나 설명 요약이 누락되거나 가려지지 않아야 한다.

## 마이그레이션 대상 코드 (TypeScript)

작업 큐 등록 및 처리 API가 v1의 콜백 기반 인스턴스 방식에서 v2의 선언적 러너 방식으로 변경되었다. 슬라이드에서는 정적 2열 비교 대신, v1 코드가 v2 코드로 점진적으로 변환되는 단계적 전환으로 제시한다.

### v1 코드 (변경 전)

```typescript
import { createWorker, TaskConfig } from '@internal/taskforge';

const config: TaskConfig = { queue: 'thumbnail-jobs', concurrency: 2 };
const worker = createWorker(config);

worker.register('resize', async (task) => {
  const result = await processImage(task.data.imageUrl, task.data.options);
  return { status: 'completed', result };
});

await worker.start();
```

### v2 코드 (변경 후)

```typescript
import { defineTaskRunner } from '@internal/taskforge';

const runner = defineTaskRunner('thumbnail-jobs', {
  concurrency: 4,
  retryLimit: 3,
});

runner.handle('resize', async ({ payload, signal }) => {
  const result = await processImage(payload.imageUrl, payload.options, { signal });
  return { status: 'success', result };
});

await runner.listen();
```

## 데모 영상 클립 요구사항

사내 CLI 도구의 로컬 실행 과정을 시연하는 15초 화면 녹화 클립이 준비되어 있다. **실제 비디오 파일은 첨부하지 않는다.** 클립은 발표 당일 교체 예정이며 지금은 플레이스홀더를 쓴다.

- 슬라이드 구성: 슬라이드에 로컬 비디오 자산을 배치하고, 영상이 재생되지 않거나 로딩 중일 때를 위한 포스터 이미지 또는 정지 상태 요약 설명을 함께 둔다.
- 플레이스홀더 명시: 슬라이드 화면 또는 발표자 노트에 해당 미디어가 발표 당일 교체 예정인 데모 플레이스홀더임을 명확히 적는다.
- 클립 타임라인 내용 (15초 요약):
  - 0~4초: 터미널에서 `taskforge dev --watch` 명령 실행 및 워커 초기화 확인.
  - 5~10초: `thumbnail-jobs` 큐에 들어온 3개 작업이 병렬 수신되어 200ms 내 순차 완료.
  - 11~15초: 일시적 실패 작업의 자동 재시도 1회 성공 및 요약 통계 출력 후 대기 모드 진입.

## 성능 비교 지표 (합성 벤치마크)

v1과 v2의 로컬 벤치마크 비교 수치이다. 아래 수치는 모의 테스트 환경에서 측정한 합성 수치이며, 프로덕션 서비스 전반의 실제 성능 향상 보증이나 실측 ROI가 아니다.

| 지표 | TaskForge v1 | TaskForge v2 | 비고 |
| :--- | :--- | :--- | :--- |
| 초당 작업 처리량 (Throughput) | 320 jobs/sec | 1,150 jobs/sec | 로컬 모의 부하 100 워커 기준 |
| 작업 등록 지연시간 (p95 latency) | 42 ms | 9 ms | 단일 노드 인메모리 큐 측정 |
| 유휴 상태 메모리 점유 (Idle RSS) | 148 MB | 52 MB | 런타임 최적화 후 측정 |

슬라이드에서 이 수치를 시각화하거나 비교할 때 합성 벤치마크 결과이며 실제 서비스 환경에 따라 다를 수 있음을 주석 또는 캡션으로 반드시 표기한다.
