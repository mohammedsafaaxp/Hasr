<template>
  <button
    type="button"
    class="inline-flex h-11 min-w-tap shrink-0 items-center justify-center rounded-hasr px-3 transition active:scale-95 disabled:opacity-40"
    :class="dark ? 'bg-hasr-ink text-white' : 'bg-hasr-surface2 text-hasr-ink'"
    :aria-label="label"
    :title="label"
  >
    <slot />
  </button>
</template>

<script setup>
defineProps({ label: { type: String, required: true }, dark: Boolean })
</script>
