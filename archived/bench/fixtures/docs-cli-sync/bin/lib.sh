# tool의 플래그 정의와 공용 함수. bin/tool이 source 한다.
# FLAG_SPEC의 각 항목은 "<플래그>|<기본값>|<설명>" 이고 --help 출력과 기본값의 유일한 출처다.
# EXIT_CODE_SPEC의 각 항목은 "<종료 코드>|<뜻>" 이다.

USAGE_LINE='사용법: tool [옵션] <입력 파일>...'

FLAG_SPEC=(
  "--format|text|출력 형식을 고른다 (text 또는 json)"
  "--output|-|결과를 쓸 경로, -는 표준 출력"
  "--include|*|처리할 파일 이름 glob"
  "--exclude|-|건너뛸 파일 이름 glob, -는 없음"
  "--min-lines|0|이 줄 수보다 짧은 파일은 결과에서 뺀다"
  "--sort|name|결과 정렬 기준 (name 또는 lines)"
  "--retries|2|파일 읽기 실패 시 다시 시도할 횟수"
  "--cache-dir|.cache|줄 수 캐시를 둘 디렉터리, 없으면 캐시하지 않는다"
  "--verbose|false|진행 로그를 표준 오류에 낸다"
  "--quiet|false|경고를 감춘다"
  "--fail-fast|false|첫 실패에서 즉시 중단한다"
  "--help|false|이 도움말을 낸다"
)

EXIT_CODE_SPEC=(
  "0|정상 종료"
  "1|--fail-fast 를 켠 상태에서 입력 파일을 읽지 못했다"
  "2|옵션이나 인수가 잘못됐다"
)

# flag_default <플래그> — 정의된 기본값을 낸다.
flag_default() {
  local entry name default description
  for entry in "${FLAG_SPEC[@]}"; do
    IFS='|' read -r name default description <<< "$entry"
    if [[ $name == "$1" ]]; then
      printf '%s\n' "$default"
      return 0
    fi
  done
  return 1
}

# print_help — 사용법, 플래그 표, 종료 코드 목록을 표준 출력에 낸다.
print_help() {
  local entry name default description code meaning
  printf '%s\n' "$USAGE_LINE"
  printf '\n'
  printf '텍스트 파일의 줄 수와 단어 수를 센다.\n'
  printf '\n'
  printf '옵션:\n'
  for entry in "${FLAG_SPEC[@]}"; do
    IFS='|' read -r name default description <<< "$entry"
    printf '  %-14s %-10s %s\n' "$name" "$default" "$description"
  done
  printf '\n'
  printf '종료 코드:\n'
  for entry in "${EXIT_CODE_SPEC[@]}"; do
    IFS='|' read -r code meaning <<< "$entry"
    printf '  %-3s %s\n' "$code" "$meaning"
  done
}

# count_file <경로> — "<줄 수> <단어 수>" 를 낸다.
count_file() {
  local line lines=0 words=0
  local -a fields=()
  while IFS= read -r line || [[ -n $line ]]; do
    lines=$(( lines + 1 ))
    # read -r -a 는 단어 분리만 하고 파일명 확장을 하지 않는다.
    read -r -a fields <<< "$line"
    words=$(( words + ${#fields[@]} ))
  done < "$1"
  printf '%s %s\n' "$lines" "$words"
}

# json_escape <문자열> — JSON 문자열 본문으로 쓸 수 있게 치환한다.
# 역슬래시·따옴표와 U+0000–U+001F 제어 문자를 모두 처리한다.
json_escape() {
  local text=$1 out="" index char escaped
  for (( index = 0; index < ${#text}; index++ )); do
    char=${text:index:1}
    case $char in
      '\') out+='\\' ;;
      '"') out+='\"' ;;
      $'\n') out+='\n' ;;
      $'\r') out+='\r' ;;
      $'\t') out+='\t' ;;
      $'\b') out+='\b' ;;
      $'\f') out+='\f' ;;
      *)
        if [[ $char == [[:cntrl:]] ]]; then
          printf -v escaped '\\u%04x' "'$char"
          out+=$escaped
        else
          out+=$char
        fi
        ;;
    esac
  done
  printf '%s\n' "$out"
}
