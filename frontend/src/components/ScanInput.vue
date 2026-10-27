<template>
  <form class="flex items-center gap-3" @submit.prevent="submit">
    <label
      class="flex h-11 flex-1 items-center gap-2 rounded-hasr bg-hasr-surface2 px-3 ring-hasr-ink focus-within:ring-[1.5px]"
      :class="disabled ? 'opacity-50' : ''"
    >
      <LucideScanBarcode class="size-5 shrink-0 text-hasr-secondary" />
      <input
        ref="input"
        v-model="code"
        type="text"
        autocomplete="off"
        autocapitalize="off"
        spellcheck="false"
        enterkeyhint="go"
        :disabled="disabled"
        :placeholder="__('Scan or type a barcode')"
        :aria-label="__('Scan or type a barcode')"
        class="h-full w-full min-w-0 border-0 bg-transparent p-0 text-[15px] placeholder:text-hasr-muted focus:ring-0"
        @blur="refocusSoon"
      />
    </label>
    <IconButton dark :label="__('Scan with camera')" :disabled="disabled" @click="$emit('camera')">
      <LucideCamera class="size-5" />
    </IconButton>
  </form>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import IconButton from './IconButton.vue'

// Always holds focus while `active`, so keyboard-wedge scanners (which type the code and press Enter) just work.
const props = defineProps({ active: { type: Boolean, default: true }, disabled: Boolean })
const emit = defineEmits(['scan', 'camera'])
const input = ref(null)
const code = ref('')

function submit() {
  const value = code.value.trim()
  code.value = ''
  if (value) emit('scan', value)
  focus()
}

function focus() {
  if (props.active && !props.disabled) input.value?.focus({ preventScroll: true })
}

function refocusSoon() {
  setTimeout(() => {
    const el = document.activeElement
    const typingElsewhere = el && el !== document.body && ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName)
    if (!typingElsewhere) focus()
  }, 250)
}

watch(() => props.active, (active) => active && setTimeout(focus, 50))
onMounted(focus)
defineExpose({ focus })
</script>
