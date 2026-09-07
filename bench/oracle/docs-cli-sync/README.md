# tool

텍스트 파일의 줄 수와 단어 수를 세는 작은 CLI다. 의존성은 bash뿐이고 `bin/tool` 하나로 돈다.

## 사용법

`bin/tool --help`가 내는 사용법 줄은 다음과 같다.

사용법: tool [옵션] <입력 파일>...

실행은 bash로 한다.

```bash
bash bin/tool notes.txt draft.txt
```

입력 파일마다 `<이름> <줄 수> <단어 수>` 한 줄을 낸다. 입력을 하나도 주지 않으면 종료 코드 2로
끝난다.

## 옵션

| 플래그 | 기본값 | 설명 |
| --- | --- | --- |
| `--format` | `text` | 출력 형식을 고른다 (text 또는 json) |
| `--output` | `-` | 결과를 쓸 경로, -는 표준 출력 |
| `--include` | `*` | 처리할 파일 이름 glob |
| `--exclude` | `-` | 건너뛸 파일 이름 glob, -는 없음 |
| `--min-lines` | `0` | 이 줄 수보다 짧은 파일은 결과에서 뺀다 |
| `--sort` | `name` | 결과 정렬 기준 (name 또는 lines) |
| `--retries` | `2` | 파일 읽기 실패 시 다시 시도할 횟수 |
| `--cache-dir` | `.cache` | 줄 수 캐시를 둘 디렉터리, 없으면 캐시하지 않는다 |
| `--verbose` | `false` | 진행 로그를 표준 오류에 낸다 |
| `--quiet` | `false` | 경고를 감춘다 |
| `--fail-fast` | `false` | 첫 실패에서 즉시 중단한다 |
| `--help` | `false` | 이 도움말을 낸다 |

## 예시

기본 출력:

```bash
bash bin/tool notes.txt draft.txt
```

```
draft.txt 12 87
notes.txt 4 19
```

JSON 출력:

```bash
bash bin/tool --format json notes.txt
```

```
[{"name":"notes.txt","lines":4,"words":19}]
```

## 종료 코드

읽을 수 없는 입력 파일은 기본적으로 경고만 내고 나머지 입력을 계속 처리한다. 그래서 읽기 실패
자체는 종료 코드를 바꾸지 않는다.

| 코드 | 뜻 |
| --- | --- |
| 0 | 정상 종료 |
| 1 | --fail-fast 를 켠 상태에서 입력 파일을 읽지 못했다 |
| 2 | 옵션이나 인수가 잘못됐다 |
