<template>
  <div class="slidev-layout as-cover" lang="ko">
    <div class="as-cover-copy"><slot /></div>
    <div class="as-cover-aside"><slot name="aside" /></div>
  </div>
</template>

<style scoped>
.as-cover { display: grid; grid-template-columns: 1.7fr 1fr; gap: 48px; align-items: center; }
.as-cover-copy { min-width: 0; }
.as-cover-aside { border-inline-start: 2px solid var(--as-accent); padding-inline-start: 32px; }
.as-cover-copy :deep(h1) { font-size: 54px; line-height: 1.2; letter-spacing: -.035em; margin-block: 20px 28px; }
.as-cover-aside :deep(p) { margin-block: 12px; }
</style>
