<template>
  <Transition name="hasr-fade">
    <div
      v-if="toast"
      role="status"
      aria-live="polite"
      class="flex items-center gap-3 rounded-tile border border-hasr-line bg-white p-3 shadow-[0_4px_16px_rgba(0,0,0,0.08)]"
    >
      <div
        class="flex size-9 shrink-0 items-center justify-center rounded-full"
        :class="toast.error ? 'bg-hasr-danger-bg text-hasr-danger' : 'bg-hasr-success-bg text-hasr-success'"
      >
        <LucideX v-if="toast.error" class="size-5" />
        <LucideCheck v-else class="size-5" />
      </div>
      <div class="min-w-0 flex-1">
        <p class="text-[15px] font-medium">{{ toast.title }}</p>
        <p v-if="toast.subtitle" class="truncate text-[13px] text-hasr-muted">{{ toast.subtitle }}</p>
      </div>
      <button
        v-if="toast.undo"
        type="button"
        class="inline-flex h-11 shrink-0 items-center gap-1.5 rounded-hasr bg-hasr-surface2 px-3 text-[15px] font-medium"
        @click="$emit('undo', toast)"
      >
        <LucideUndo2 class="size-4 rtl:-scale-x-100" />
        {{ __('Undo') }}
      </button>
    </div>
  </Transition>
</template>

<script setup>
defineProps({ toast: Object })
defineEmits(['undo'])
</script>
