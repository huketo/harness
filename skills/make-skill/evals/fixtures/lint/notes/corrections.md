# 리뷰 교정 기록

## 11월 2일, PR 412
`src/checkout.ts`에 디버깅용 `console.log`가 세 줄 남아 있었습니다. 지워 달라고 요청했습니다.

## 11월 14일, PR 431
같은 지적입니다. `src/cart.ts`에 `console.log("prices", prices)`가 남은 채로 올라왔습니다. 로그는 `src/log.ts`의 `log()`만 씁니다.
