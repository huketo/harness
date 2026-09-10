<!-- Adapted from BaizeAI/talks TtftBreakdown.vue; Apache-2.0. See NOTICE.txt.
     Modified: shared absolute scale, computed totals, text labels, token styling. -->
<script setup lang="ts">
import { computed } from 'vue'
interface Segment { name: string; value: number }
interface Scenario { title: string; segments: Segment[] }
const props = withDefaults(defineProps<{ scenarios: Scenario[]; unit?: string; caption: string }>(), { unit: 'ms' })
const rows = computed(() => props.scenarios.map(s => ({ ...s, total: s.segments.reduce((sum, seg) => sum + seg.value, 0) })))
const maximum = computed(() => Math.max(1, ...rows.value.map(s => s.total)))
</script>

<template>
  <figure class="as-breakdown">
    <figcaption>{{ caption }}</figcaption>
    <div v-for="row in rows" :key="row.title" class="as-breakdown-row">
      <div class="as-breakdown-heading"><span>{{ row.title }}</span><strong>{{ row.total }} {{ unit }}</strong></div>
      <div class="as-breakdown-track" aria-hidden="true">
        <div v-for="(seg, index) in row.segments" :key="seg.name" class="as-breakdown-segment"
          :class="{ 'as-breakdown-primary': index === 0 }" :style="{ width: (seg.value / maximum * 100) + '%' }" />
      </div>
      <dl class="as-breakdown-legend">
        <div v-for="(seg, index) in row.segments" :key="seg.name">
          <dt><span class="as-breakdown-key" :class="{ 'as-breakdown-primary': index === 0 }" />{{ seg.name }}</dt>
          <dd>{{ seg.value }} {{ unit }}</dd>
        </div>
      </dl>
    </div>
  </figure>
</template>

<style scoped>
.as-breakdown { margin: 0; }
figcaption { color: var(--as-muted); font-size: 16px; margin-bottom: 12px; }
.as-breakdown-row + .as-breakdown-row { margin-top: 20px; }
.as-breakdown-heading { display: flex; justify-content: space-between; align-items: baseline; font-size: 22px; margin-bottom: 6px; }
.as-breakdown-heading strong { font-size: 28px; font-variant-numeric: tabular-nums; }
.as-breakdown-track { display: flex; height: 24px; width: 100%; border-inline-start: 1px solid var(--as-line); }
.as-breakdown-segment, .as-breakdown-key { background: var(--as-muted); }
.as-breakdown-primary { background: var(--as-accent); }
.as-breakdown-segment + .as-breakdown-segment { border-inline-start: 2px solid var(--as-bg); }
.as-breakdown-legend { display: flex; gap: 28px; margin: 6px 0 0; font-size: 17px; }
.as-breakdown-legend > div, dt { display: flex; align-items: center; gap: 8px; }
dd { margin: 0; font-variant-numeric: tabular-nums; }
.as-breakdown-key { display: inline-block; width: 10px; height: 10px; }
</style>
