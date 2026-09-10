<template>
  <div class="slidev-layout as-split" lang="ko">
    <header><slot name="header" /></header>
    <div class="as-split-body"><section><slot /></section><aside><slot name="right" /></aside></div>
    <footer><slot name="footer" /></footer>
  </div>
</template>

<style scoped>
.as-split { display: grid; grid-template-rows: auto 1fr auto; gap: 28px; }
.as-split-body { display: grid; grid-template-columns: 1.2fr 1fr; gap: 42px; align-items: center; }
section, aside { min-width: 0; }
aside { border-inline-start: 1px solid var(--as-line); padding-inline-start: 28px; }
header :deep(h1) { margin: 0; }
footer { font-size: 15px; color: var(--as-muted); }
footer :deep(p) { margin: 0; }
</style>
