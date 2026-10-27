<template>
  <Teleport to="body">
    <Transition name="hasr-fade">
      <div v-if="open" class="fixed inset-0 z-40 bg-black/40" @click="dismiss" />
    </Transition>
    <Transition name="hasr-slide">
      <div
        v-if="open"
        ref="panel"
        role="dialog"
        aria-modal="true"
        :aria-label="label"
        class="fixed inset-x-0 bottom-0 z-50 mx-auto flex max-h-[92dvh] w-full max-w-xl flex-col rounded-t-sheet bg-white font-hasr text-hasr-ink"
        tabindex="-1"
        @keydown.esc="dismiss"
      >
        <div class="flex shrink-0 justify-center pb-1 pt-3">
          <div class="h-1 w-9 rounded-full bg-hasr-line" />
        </div>
        <div class="min-h-0 overflow-y-auto overscroll-contain px-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
          <slot />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'

const props = defineProps({
  open: Boolean,
  label: { type: String, default: '' },
  dismissible: { type: Boolean, default: true },
})
const emit = defineEmits(['update:open', 'close'])
const panel = ref(null)

function dismiss() {
  if (!props.dismissible) return
  emit('update:open', false)
  emit('close')
}

watch(
  () => props.open,
  async (open) => {
    if (open) {
      await nextTick()
      panel.value?.focus()
    }
  },
)
</script>

<style>
.hasr-fade-enter-active,
.hasr-fade-leave-active {
  transition: opacity 0.15s;
}
.hasr-fade-enter-from,
.hasr-fade-leave-to {
  opacity: 0;
}
.hasr-slide-enter-active,
.hasr-slide-leave-active {
  transition: transform 0.2s ease-out;
}
.hasr-slide-enter-from,
.hasr-slide-leave-to {
  transform: translateY(100%);
}
</style>
