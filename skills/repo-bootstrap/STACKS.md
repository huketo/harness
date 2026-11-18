# 기본 스택

`repo-bootstrap`이 새 저장소에 고르는 스택의 정본이다. 저장소마다 스택을 다시 토론하지 않으려고 둔다. 여기에 없는 선택은 그 저장소의 ADR에 적는다.

## 선택 기준

에이전트가 틀렸을 때 기계가 얼마나 빨리, 얼마나 분명하게 알려 주는지를 본다.

1. 정적 타입이 강해서 잘못된 상태를 값으로 쓰기 어렵다.
2. 타입 검사, 린트, 테스트가 빠르고 결정적이다.
3. 린트에 저장소 전용 규칙과 전용 오류 메시지를 넣을 수 있다.
4. 디렉터리 관례가 있어서 코드가 놓일 자리가 하나로 정해진다.
5. 충분히 검증되어 문서와 사례가 많다.

## 상태

| 상태 | 뜻 |
| --- | --- |
| 채택 | 새 저장소의 기본값이다. 경계 규칙이 실패하는 것과 통과하는 것을 모두 확인한 템플릿이 있다. |
| 시험 | 실제 저장소 하나에서 써 보는 중이다. 템플릿은 없거나 확인이 끝나지 않았다. |
| 보류 | 새 저장소에 쓰지 않는다. 이유를 적는다. |

스택을 `채택`으로 올리려면 `templates/<스택>/`과 아래 "위반 사례"가 함께 있어야 하고, 사례마다 린트가 실패하는 것을 확인해야 한다.

## 채택

### TypeScript (`templates/typescript/`)

| 항목 | 선택 |
| --- | --- |
| 실행 | Node.js 24의 타입 제거 실행. 빌드 단계가 없다. |
| 도구 버전과 진입점 | `mise.toml`. `mise run check`가 타입 검사, 린트, 테스트를 모두 실행한다. |
| 타입 | `tsc --noEmit`, `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `erasableSyntaxOnly` |
| 린트 | ESLint의 `defineConfig`로 쓴 설정. typescript-eslint의 타입 인식 권장 규칙, `switch-exhaustiveness-check`, 경계용 `no-restricted-imports` |
| 테스트 | `node:test`와 `node:assert/strict`. 테스트는 대상 옆에 `*.test.ts`로 둔다. |
| CI | 원격에 맞는 파일 하나가 `mise run check`를 실행한다. |

설치 명령:

```bash
mise trust && mise install
npm install --save-dev typescript eslint typescript-eslint @types/node@24
mise run check
```

디렉터리 관례:

- `src/core/<기능>/`은 순수한 로직이다. 기능 하나가 평평한 디렉터리 하나이고, `index.ts`가 유일한 공개 진입점이다.
- `src/shell/`은 입출력과 진입점이다. core를 호출하고, core가 타입으로 선언한 의존성의 구현을 넘긴다.

위반 사례(`repo-bootstrap` 4단계에서 하나씩 실패를 확인한다):

| 위반 | 만드는 방법 | 실패하는 규칙 |
| --- | --- | --- |
| core의 입출력 | `src/core/<기능>/`의 파일에서 `node:fs`를 import한다 | `no-restricted-imports` |
| 접두사 없는 내장 모듈 | core의 파일에서 `fs`나 `fs/promises`를 import한다 | `no-restricted-imports` |
| core 테스트의 입출력 | `src/core/<기능>/*.test.ts`에서 `node:fs`를 import한다(`node:test`와 `node:assert`는 허용) | `no-restricted-imports` |
| core가 shell에 의존 | core의 파일에서 `../../shell/main.ts`를 import한다 | `no-restricted-imports` |
| shell의 깊은 import | `src/shell/`에서 `../core/<기능>/name.ts`를 import한다 | `no-restricted-imports` |
| 다른 기능의 깊은 import | 다른 기능에서 `../<기능>/name.ts`를 import한다 | `no-restricted-imports` |
| 빠진 분기 | `switch`에서 `case` 하나를 지운다 | `switch-exhaustiveness-check` |

확인한 범위: 2026-11-18에 Node.js 24, TypeScript 6.0, ESLint 10.15, typescript-eslint 8.73으로 위 일곱 사례의 실패와 올바른 코드(다른 기능을 `index.ts`로 import, shell의 `node:fs` 사용)의 통과를 확인했다. `.github/workflows/ci.yml`과 `.gitlab-ci.yml`은 파이프라인에서 실행해 보지 않았다.

## 시험

없음.

## 보류

없음.
