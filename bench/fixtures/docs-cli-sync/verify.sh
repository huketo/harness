#!/usr/bin/env bash
# README.md가 bin/tool --help 와 일치하는지 검사한다. bash 내장만 쓴다.
# 검사 항목: (1) --help의 사용법 한 줄이 문서에 정확히 한 번 있는지, (2) 옵션 표의
# 플래그·기본값·설명이 --help와 같은지, (3) 종료 코드 표가 --help의 종료 코드 목록과 같은지,
# (4) 문서 어디에도 --help에 없는 플래그가 남아 있지 않은지.
# 펜스 코드 블록과 HTML 주석 안의 내용은 판독하지 않는다.
set -u

fail() {
  printf 'verify: FAIL %s\n' "$1" >&2
  exit 1
}

trim() {
  local text=$1
  text=${text#"${text%%[![:space:]]*}"}
  text=${text%"${text##*[![:space:]]}"}
  printf '%s' "$text"
}

# split_row <표 행> — ROW_CELLS 에 칸을 넣는다. 백틱과 앞뒤 공백은 지운다.
ROW_CELLS=()
split_row() {
  local line=$1 body cell
  local -a parts=()
  ROW_CELLS=()
  [[ $line == \|*\| ]] || return 1
  body=${line#|}
  body=${body%|}
  IFS='|' read -r -a parts <<< "$body"
  for cell in "${parts[@]}"; do
    cell=${cell//\`/}
    ROW_CELLS+=("$(trim "$cell")")
  done
  return 0
}

[[ -f bin/tool ]] || fail 'bin/tool 이 없다'
[[ -f README.md ]] || fail 'README.md 가 없다'

# ------------------------------------------------------- bin/tool --help 파싱
declare -A HELP_DEFAULT=()
declare -A HELP_DESC=()
declare -A HELP_EXIT=()
HELP_FLAGS=()
HELP_CODES=()
HELP_USAGE=""
while IFS= read -r line; do
  if [[ -z $HELP_USAGE && $line == 사용법:* ]]; then
    HELP_USAGE=$(trim "$line")
    continue
  fi
  if [[ $line =~ ^[[:space:]][[:space:]](--[a-z][a-z0-9-]*)[[:space:]]+([^[:space:]]+)[[:space:]]+(.+)$ ]]; then
    flag=${BASH_REMATCH[1]}
    if [[ -n ${HELP_DEFAULT[$flag]+set} ]]; then
      fail "bin/tool --help 에 ${flag} 가 두 번 나온다"
    fi
    HELP_FLAGS+=("$flag")
    HELP_DEFAULT[$flag]=${BASH_REMATCH[2]}
    HELP_DESC[$flag]=$(trim "${BASH_REMATCH[3]}")
    continue
  fi
  if [[ $line =~ ^[[:space:]][[:space:]]([0-9]+)[[:space:]]+(.+)$ ]]; then
    code=${BASH_REMATCH[1]}
    if [[ -n ${HELP_EXIT[$code]+set} ]]; then
      fail "bin/tool --help 에 종료 코드 ${code} 가 두 번 나온다"
    fi
    HELP_CODES+=("$code")
    HELP_EXIT[$code]=$(trim "${BASH_REMATCH[2]}")
    continue
  fi
done < <(bash bin/tool --help 2> /dev/null)

[[ -n $HELP_USAGE ]] || fail 'bin/tool --help 이 사용법 줄을 내지 않는다. 도움말 출력이 깨졌다'
if (( ${#HELP_FLAGS[@]} < 8 )); then
  fail "bin/tool --help 에서 플래그를 ${#HELP_FLAGS[@]}개만 읽었다. 도움말 출력이 깨졌다"
fi
if (( ${#HELP_CODES[@]} < 2 )); then
  fail "bin/tool --help 에서 종료 코드를 ${#HELP_CODES[@]}개만 읽었다. 도움말 출력이 깨졌다"
fi

# ------------------------------------------------------------- README.md 파싱
declare -A README_DEFAULT=()
declare -A README_DESC=()
declare -A README_EXIT=()
declare -A DOC_FLAGS=()
README_FLAGS=()
README_CODES=()
usage_count=0
in_fence=0
in_comment=0
flag_header=0
exit_header=0
section=none

while IFS= read -r raw || [[ -n $raw ]]; do
  line=$(trim "$raw")

  # 펜스 코드 블록과 HTML 주석은 판독에서 뺀다. 예시 블록에 남은 옛 플래그나 주석으로
  # 감춘 표는 문서가 서술하는 사실이 아니다.
  if (( in_fence == 1 )); then
    [[ $line == '```'* || $line == '~~~'* ]] && in_fence=0
    continue
  fi
  if (( in_comment == 1 )); then
    [[ $line == *'-->'* ]] && in_comment=0
    continue
  fi
  if [[ $line == '```'* || $line == '~~~'* ]]; then
    in_fence=1
    continue
  fi
  if [[ $line == '<!--'* ]]; then
    [[ $line == *'-->'* ]] || in_comment=1
    continue
  fi

  # 문서 전체에서 플래그 모양의 토큰을 모은다.
  rest=$line
  while [[ $rest =~ (--[a-z][a-z0-9-]*) ]]; do
    token=${BASH_REMATCH[1]}
    DOC_FLAGS[$token]=1
    rest=${rest#*"$token"}
  done

  [[ $line == "$HELP_USAGE" ]] && usage_count=$(( usage_count + 1 ))

  if ! split_row "$line"; then
    section=none
    continue
  fi

  if (( ${#ROW_CELLS[@]} == 3 )) &&
    [[ ${ROW_CELLS[0]} == 플래그 && ${ROW_CELLS[1]} == 기본값 && ${ROW_CELLS[2]} == 설명 ]]; then
    section=flags
    flag_header=1
    continue
  fi
  if (( ${#ROW_CELLS[@]} == 2 )) && [[ ${ROW_CELLS[0]} == 코드 && ${ROW_CELLS[1]} == 뜻 ]]; then
    section=exits
    exit_header=1
    continue
  fi

  first=${ROW_CELLS[0]}
  [[ $first =~ ^:?-{3,}:?$ ]] && continue

  case $section in
    flags)
      (( ${#ROW_CELLS[@]} == 3 )) || fail "README 옵션 표의 칸 수가 3이 아닌 행이 있다: ${line}"
      [[ $first =~ ^--[a-z][a-z0-9-]*$ ]] || fail "README 옵션 표의 첫 칸이 플래그가 아니다: ${first}"
      if [[ -n ${README_DEFAULT[$first]+set} ]]; then
        fail "README 옵션 표에 ${first} 행이 두 번 있다"
      fi
      README_FLAGS+=("$first")
      README_DEFAULT[$first]=${ROW_CELLS[1]}
      README_DESC[$first]=${ROW_CELLS[2]}
      ;;
    exits)
      (( ${#ROW_CELLS[@]} == 2 )) || fail "README 종료 코드 표의 칸 수가 2가 아닌 행이 있다: ${line}"
      [[ $first =~ ^[0-9]+$ ]] || fail "README 종료 코드 표의 첫 칸이 숫자가 아니다: ${first}"
      if [[ -n ${README_EXIT[$first]+set} ]]; then
        fail "README 종료 코드 표에 ${first} 행이 두 번 있다"
      fi
      README_CODES+=("$first")
      README_EXIT[$first]=${ROW_CELLS[1]}
      ;;
  esac
done < README.md

(( flag_header == 1 )) || fail 'README.md 에 `| 플래그 | 기본값 | 설명 |` 헤더를 가진 옵션 표가 없다'
(( exit_header == 1 )) || fail 'README.md 에 `| 코드 | 뜻 |` 헤더를 가진 종료 코드 표가 없다'
if (( usage_count != 1 )); then
  fail "README.md 에 --help 의 사용법 줄이 정확히 한 번 있어야 한다. 지금 ${usage_count}번(코드 펜스와 HTML 주석 안은 세지 않는다): ${HELP_USAGE}"
fi

# --------------------------------------------------------------------- 대조
missing=()
extra=()
mismatch=()
descdiff=()
exitproblem=()
stale=()

for flag in "${HELP_FLAGS[@]}"; do
  if [[ -z ${README_DEFAULT[$flag]+set} ]]; then
    missing+=("$flag")
    continue
  fi
  if [[ "${README_DEFAULT[$flag]}" != "${HELP_DEFAULT[$flag]}" ]]; then
    mismatch+=("${flag} (README=${README_DEFAULT[$flag]}, --help=${HELP_DEFAULT[$flag]})")
  fi
  if [[ "${README_DESC[$flag]}" != "${HELP_DESC[$flag]}" ]]; then
    descdiff+=("${flag} (README=${README_DESC[$flag]:-<빈 칸>}, --help=${HELP_DESC[$flag]})")
  fi
done
for flag in "${README_FLAGS[@]}"; do
  if [[ -z ${HELP_DEFAULT[$flag]+set} ]]; then
    extra+=("$flag")
  fi
done
for token in "${!DOC_FLAGS[@]}"; do
  if [[ -z ${HELP_DEFAULT[$token]+set} ]]; then
    stale+=("$token")
  fi
done
for code in "${HELP_CODES[@]}"; do
  if [[ -z ${README_EXIT[$code]+set} ]]; then
    exitproblem+=("종료 코드 ${code} 행이 없다")
    continue
  fi
  if [[ "${README_EXIT[$code]}" != "${HELP_EXIT[$code]}" ]]; then
    exitproblem+=("종료 코드 ${code} 설명 (README=${README_EXIT[$code]}, --help=${HELP_EXIT[$code]})")
  fi
done
for code in "${README_CODES[@]}"; do
  if [[ -z ${HELP_EXIT[$code]+set} ]]; then
    exitproblem+=("--help 에 없는 종료 코드 ${code} 행이 있다")
  fi
done

problems=0
report() { # $1 = 제목, $2.. = 항목
  local title=$1 item
  shift
  (( $# == 0 )) && return 0
  problems=$(( problems + $# ))
  printf 'verify: %s (%d건)\n' "$title" "$#" >&2
  for item in "$@"; do
    printf 'verify:   - %s\n' "$item" >&2
  done
}

report 'README 옵션 표에 없는 플래그' ${missing[@]+"${missing[@]}"}
report 'bin/tool 에 없는데 README 옵션 표에 남은 플래그' ${extra[@]+"${extra[@]}"}
report '기본값 불일치' ${mismatch[@]+"${mismatch[@]}"}
report '설명이 --help 와 다른 플래그' ${descdiff[@]+"${descdiff[@]}"}
report '문서 어딘가에 남은 미지원 플래그' ${stale[@]+"${stale[@]}"}
report '종료 코드 표 불일치' ${exitproblem[@]+"${exitproblem[@]}"}

if (( problems > 0 )); then
  fail "README.md 와 bin/tool --help 가 ${problems}곳 어긋난다"
fi

printf 'verify: OK 사용법 줄 1개, 플래그 %d개의 이름·기본값·설명, 종료 코드 %d개의 뜻이 bin/tool --help 와 같고 코드 펜스·HTML 주석 밖 어디에도 미지원 플래그가 없다\n' \
  "${#HELP_FLAGS[@]}" "${#HELP_CODES[@]}"
exit 0
