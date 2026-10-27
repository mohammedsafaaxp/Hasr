<template>
  <span
    class="inline-flex h-7 shrink-0 items-center gap-1 whitespace-nowrap rounded-full px-2.5 text-[13px] font-medium"
    :class="themes[theme]"
  >
    <slot />
  </span>
</template>

<script setup>
defineProps({ theme: { type: String, default: 'gray' } })
const themes = {
  gray: 'bg-hasr-surface2 text-hasr-secondary',
  green: 'bg-hasr-success-bg text-hasr-success',
  orange: 'bg-hasr-warning-bg text-hasr-warning',
  red: 'bg-hasr-danger-bg text-hasr-danger',
  blue: 'bg-hasr-info-bg text-hasr-info',
}
</script>
