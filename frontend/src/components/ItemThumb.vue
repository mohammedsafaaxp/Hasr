<template>
  <div
    class="relative flex shrink-0 items-center justify-center overflow-hidden rounded-tile bg-hasr-surface2 text-hasr-muted"
    :style="{ width: size + 'px', height: size + 'px' }"
  >
    <img v-if="src && !failed" :src="src" alt="" class="h-full w-full object-cover" loading="lazy" @error="failed = true" />
    <LucidePackage v-else class="size-6" />
    <slot />
  </div>
</template>

<script setup>
import { ref } from 'vue'
defineProps({ src: String, size: { type: Number, default: 48 } })
const failed = ref(false)
</script>
