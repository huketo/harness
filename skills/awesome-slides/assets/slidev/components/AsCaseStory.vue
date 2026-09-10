<!-- Adapted from BaizeAI/talks CaseStory.vue; Apache-2.0. See NOTICE.txt.
     Modified: Korean labels, plain-text props instead of v-html, open editorial rows. -->
<script setup lang="ts">
defineProps<{ saw: string; meant: string; changed: string; verified: string; rollback?: string }>()
</script>

<template>
  <dl class="as-case-story">
    <div><dt>관찰</dt><dd>{{ saw }}</dd></div>
    <div><dt>해석</dt><dd>{{ meant }}</dd></div>
    <div class="as-case-change"><dt>변경</dt><dd>{{ changed }}</dd></div>
    <div><dt>검증</dt><dd>{{ verified }}<p v-if="rollback" class="as-case-rollback">되돌릴 조건 · {{ rollback }}</p></dd></div>
  </dl>
</template>

<style scoped>
.as-case-story { margin: 0; }
.as-case-story > div { display: grid; grid-template-columns: 56px 1fr; gap: 24px; padding: 15px 0; border-bottom: 1px solid var(--as-line); }
dt { color: var(--as-muted); font-size: 16px; padding-top: 3px; }
dd { margin: 0; font-size: 21px; line-height: 1.5; }
.as-case-change dt { color: var(--as-accent); font-weight: 700; }
.as-case-change dd { font-weight: 600; }
.as-case-rollback { color: var(--as-muted); font-size: 15px; margin: 8px 0 0; }
</style>
