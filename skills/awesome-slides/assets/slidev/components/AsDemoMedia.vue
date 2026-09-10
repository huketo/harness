<!-- 정적 출력(PDF·인쇄) 및 미디어 미재생 환경을 위해 fallback 설명문은 영상 아래에 항상 텍스트로 함께 표시됩니다. -->
<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  src: string
  poster: string
  caption: string
  fallback: string
}

const props = defineProps<Props>()

const hasFallback = computed(() => Boolean(props.fallback && props.fallback.trim().length > 0))
</script>

<template>
  <div v-if="!hasFallback" class="as-demo-warning" role="alert">
    <strong>경고:</strong> AsDemoMedia에 필수 속성인 fallback 설명문이 비어 있습니다. 정적 출력 및 접근성을 위한 대체 텍스트를 반드시 제공해야 합니다.
  </div>
  <figure v-else class="as-demo-media">
    <div class="as-demo-frame">
      <SlidevVideo
        v-click
        autoplay
        controls
        :poster="poster"
        autoreset="click"
      >
        <source :src="src" type="video/mp4" />
      </SlidevVideo>
    </div>
    <figcaption class="as-demo-caption">{{ caption }}</figcaption>
    <p class="as-demo-fallback">{{ fallback }}</p>
  </figure>
</template>

<style scoped>
.as-demo-warning {
  padding: 18px 24px;
  border: 2px solid var(--as-accent);
  background: var(--as-bg);
  color: var(--as-accent);
  font-size: 18px;
  font-weight: 600;
  margin: 16px 0;
  border-radius: var(--as-radius, 4px);
  text-align: left;
}
.as-demo-media {
  margin: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}
.as-demo-frame {
  width: 100%;
  max-width: 600px;
  background: var(--as-bg);
  border: 1px solid var(--as-line);
  border-radius: var(--as-radius, 4px);
  overflow: hidden;
  display: flex;
  justify-content: center;
}
.as-demo-frame :deep(video) {
  width: 100%;
  height: auto;
  max-height: 250px;
  display: block;
  object-fit: contain;
  aspect-ratio: 16 / 9;
}
.as-demo-caption {
  color: var(--as-muted);
  font-size: 15px;
  margin-top: 10px;
}
.as-demo-fallback {
  margin: 10px 0 0;
  font-size: 18px;
  line-height: 1.5;
  color: var(--as-fg);
  max-width: 38em;
}
</style>
