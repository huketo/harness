<!-- Adapted from BaizeAI/talks StageFlow.vue; Apache-2.0. See NOTICE.txt.
     Modified: ordered-list semantics, local vector arrows, readable non-highlighted stages. -->
<script setup lang="ts">
interface Stage { id: string; name: string; detail: string; metric?: string }
defineProps<{ stages: Stage[]; highlight?: string[] }>()
</script>

<template>
  <ol class="as-stage-flow" aria-label="처리 순서">
    <li v-for="(stage, index) in stages" :key="stage.id" :class="{ 'as-stage-active': highlight?.includes(stage.id) }">
      <span class="as-stage-index">{{ String(index + 1).padStart(2, '0') }}</span>
      <h2>{{ stage.name }}</h2>
      <p>{{ stage.detail }}</p>
      <strong v-if="stage.metric">{{ stage.metric }}</strong>
      <svg v-if="index < stages.length - 1" class="as-stage-arrow" viewBox="0 0 32 16" aria-hidden="true"><path d="M1 8h28m-7-6 7 6-7 6" /></svg>
    </li>
  </ol>
</template>

<style scoped>
.as-stage-flow { display: flex; gap: 36px; padding: 0; margin: 0; list-style: none; }
li { position: relative; flex: 1; min-width: 0; border-top: 2px solid var(--as-line); padding-top: 20px; }
li.as-stage-active { border-color: var(--as-accent); }
.as-stage-index { font: 18px var(--as-mono); color: var(--as-muted); }
h2 { margin: 14px 0 8px; font-size: 25px; }
p { font-size: 20px; margin: 0 0 20px; }
strong { font-size: 18px; font-weight: 600; }
.as-stage-arrow { position: absolute; right: -32px; top: 27px; width: 28px; height: 16px; fill: none; stroke: var(--as-muted); stroke-width: 1.5; }
.as-stage-active .as-stage-index { color: var(--as-accent); }
</style>
