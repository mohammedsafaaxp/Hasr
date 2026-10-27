<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-50 flex touch-none select-none items-center justify-center bg-black"
      role="dialog"
      aria-modal="true"
      :aria-label="__('Photo')"
      @keydown.esc="close"
      @pointerdown="down"
      @pointermove="move"
      @pointerup="up"
      @pointercancel="up"
      @wheel.prevent="wheel"
      @dblclick="toggle"
    >
      <img
        :src="src"
        alt=""
        class="max-h-full max-w-full"
        draggable="false"
        :style="{ transform: `translate(${x}px, ${y}px) scale(${scale})`, transition: pointers.size ? 'none' : 'transform 0.15s' }"
      />
      <button
        type="button"
        class="absolute end-4 top-4 flex size-11 items-center justify-center rounded-hasr bg-white/15 text-white"
        :aria-label="__('Close')"
        @pointerdown.stop
        @click="close"
      >
        <LucideX class="size-5" />
      </button>
    </div>
  </Teleport>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'

const props = defineProps({ open: Boolean, src: String })
const emit = defineEmits(['update:open'])
const scale = ref(1)
const x = ref(0)
const y = ref(0)
const pointers = reactive(new Map())
let startDist = 0
let startScale = 1
let lastTap = 0

function reset() {
  scale.value = 1
  x.value = 0
  y.value = 0
}
watch(() => props.open, reset)

function close() {
  emit('update:open', false)
}

function toggle() {
  if (scale.value > 1) reset()
  else scale.value = 2.5
}

function distance() {
  const [a, b] = [...pointers.values()]
  return Math.hypot(a.x - b.x, a.y - b.y)
}

function down(e) {
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
  if (pointers.size === 2) {
    startDist = distance()
    startScale = scale.value
  } else if (e.pointerType === 'touch') {
    const now = Date.now()
    if (now - lastTap < 300) toggle()
    lastTap = now
  }
}

function move(e) {
  const prev = pointers.get(e.pointerId)
  if (!prev) return
  const cur = { x: e.clientX, y: e.clientY }
  pointers.set(e.pointerId, cur)
  if (pointers.size === 2 && startDist) {
    scale.value = Math.min(6, Math.max(1, (startScale * distance()) / startDist))
  } else if (pointers.size === 1 && scale.value > 1) {
    x.value += cur.x - prev.x
    y.value += cur.y - prev.y
  }
}

function up(e) {
  pointers.delete(e.pointerId)
  if (pointers.size < 2) startDist = 0
  if (scale.value <= 1) reset()
}

function wheel(e) {
  scale.value = Math.min(6, Math.max(1, scale.value - e.deltaY * 0.002))
  if (scale.value <= 1) reset()
}
</script>
