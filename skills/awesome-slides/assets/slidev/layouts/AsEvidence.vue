<template>
  <div class="slidev-layout as-evidence" lang="ko">
    <header><slot name="header" /></header>
    <main><slot /></main>
    <footer><slot name="footer" /></footer>
  </div>
</template>

<style scoped>
.as-evidence { display: grid; grid-template-rows: auto 1fr auto; gap: 24px; }
main { min-width: 0; align-self: center; }
footer { color: var(--as-muted); font-size: 15px; line-height: 1.5; }
footer :deep(p) { margin: 0; }
header :deep(h1) { margin: 0; }
</style>
