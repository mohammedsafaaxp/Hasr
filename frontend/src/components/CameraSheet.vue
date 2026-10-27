<template>
  <Sheet :open="open" :label="__('Scan with camera')" @update:open="$emit('update:open', $event)">
    <div class="space-y-3 pb-2">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold">{{ __('Scan with camera') }}</h2>
        <IconButton :label="__('Close')" @click="$emit('update:open', false)">
          <LucideX class="size-5" />
        </IconButton>
      </div>
      <div class="relative aspect-[3/4] w-full overflow-hidden rounded-tile bg-black">
        <video ref="video" class="h-full w-full object-cover" muted playsinline />
        <div class="pointer-events-none absolute inset-x-8 top-1/2 h-0.5 -translate-y-1/2 bg-hasr-yellow/80" />
        <div v-if="error" class="absolute inset-0 flex items-center justify-center p-6 text-center text-sm text-white">
          {{ error }}
        </div>
      </div>
      <p class="text-center text-sm text-hasr-muted">{{ last ? __('Scanned {0}', [last]) : __('Point the camera at a barcode') }}</p>
      <button type="button" class="h-11 w-full rounded-hasr bg-hasr-surface2 text-[15px] font-medium" @click="$emit('update:open', false)">
        {{ __('Close') }}
      </button>
    </div>
  </Sheet>
</template>

<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import Sheet from './Sheet.vue'
import IconButton from './IconButton.vue'
import { __ } from '../i18n'

const props = defineProps({ open: Boolean })
const emit = defineEmits(['update:open', 'scan'])
const video = ref(null)
const error = ref('')
const last = ref('')
let controls = null
let lastCode = ''
let lastAt = 0

async function start() {
  error.value = ''
  last.value = ''
  if (!window.isSecureContext || !navigator.mediaDevices) {
    error.value = __('The camera needs a secure (HTTPS) connection. Use a hardware scanner or type the barcode.')
    return
  }
  await nextTick()
  try {
    const { BrowserMultiFormatReader } = await import('@zxing/browser')
    const reader = new BrowserMultiFormatReader()
    controls = await reader.decodeFromConstraints(
      { video: { facingMode: { ideal: 'environment' } } },
      video.value,
      (result) => {
        if (!result) return
        const code = result.getText()
        const now = Date.now()
        // the camera sees the same code many times a second; count it once per 1.5 s
        if (code === lastCode && now - lastAt < 1500) return
        lastCode = code
        lastAt = now
        last.value = code
        emit('scan', code)
      },
    )
  } catch (e) {
    error.value = __('Could not open the camera. Check the browser permission.')
  }
}

function stop() {
  if (controls) controls.stop()
  controls = null
}

watch(() => props.open, (open) => (open ? start() : stop()))
onBeforeUnmount(stop)
</script>
