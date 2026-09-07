# 변이 목록

`verify.py`가 채점할 때 이 디렉터리의 파일을 하나씩 `src/money.ts` 자리에 놓은 임시 사본에서 테스트를 다시 돌린다. 각 파일은 원본 모듈과 주석·구성이 같고 아래 한 가지 동작만 다르다.

- `convert-unrounded.ts` — 변환 결과 반올림: 변환한 금액을 목표 통화 자리수로 반올림하지 않고 그대로 돌려준다.
- `currency-decimals.ts` — 통화 소수 자리수: KRW를 0자리에서 2자리로, BHD를 3자리에서 2자리로 바꾼다.
- `negative-sign.ts` — 부호 처리: 절댓값이 아니라 부호가 붙은 값으로 반올림해 음수의 대칭성을 깬다.
- `rate-inverse.ts` — 환율 방향: 표에 실린 방향과 실리지 않은 방향의 역수 적용을 서로 바꾼다.
- `rounding-mode.ts` — 반올림 모드: `half-even`과 `half-up`의 동률 처리 규칙을 서로 바꾼다.
- `sum-mixed-currency.ts` — 합산의 통화 검사: 지정한 통화와 다른 통화의 항목을 거절하지 않고 그대로 더한다.
- `unknown-currency-default.ts` — 알 수 없는 통화: `RangeError` 대신 2자리라는 기본값을 조용히 돌려준다.
