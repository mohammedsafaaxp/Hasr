<template>
  <!-- the tally mark; the yellow stroke is used for the logo only -->
  <svg :width="size" :height="size" viewBox="0 0 64 64" role="img" :aria-label="__('hasr')">
    <rect width="64" height="64" rx="15" fill="#171717" />
    <g stroke="#FFFFFF" :stroke-width="size < 32 ? 6 : 4.5" stroke-linecap="round">
      <path v-if="size < 32" d="M22 18v28M32 18v28M42 18v28" />
      <path v-else d="M21 19v26M28.5 19v26M36 19v26M43.5 19v26" />
    </g>
    <path d="M15 43 49 21" stroke="#F5B800" :stroke-width="size < 32 ? 7 : 5.5" stroke-linecap="round" />
  </svg>
</template>

<script setup>
defineProps({ size: { type: Number, default: 40 } })
</script>
