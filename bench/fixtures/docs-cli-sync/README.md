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
| `--min-lines` | `1` | 이 줄 수보다 짧은 파일은 결과에서 뺀다 |
| `--sort` | `lines` | 결과 정렬 기준 (name 또는 lines) |
| `--legacy-mode` | `false` | 옛 출력 형식으로 되돌린다 |
| `--color` | `auto` | 색상 출력 조건 |
| `--verbose` | `false` | 진행 로그를 표준 오류에 낸다 |
| `--quiet` | `false` | 경고를 감춘다 |
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

색상을 끄고 싶으면 `--color never`를 쓴다.

## 종료 코드

| 코드 | 뜻 |
| --- | --- |
| 0 | 정상 종료 |
| 1 | 입력 파일을 읽지 못했다 |
| 2 | 옵션이나 인수가 잘못됐다 |
