<template>
  <div class="flex items-center gap-2" :class="big ? '' : 'shrink-0'">
    <IconButton :label="__('Decrease')" :disabled="modelValue <= 0" @click="set(modelValue - step)">
      <LucideMinus class="size-5" />
    </IconButton>
    <input
      :value="modelValue"
      type="number"
      inputmode="decimal"
      min="0"
      :aria-label="label"
      class="tabular min-w-0 rounded-hasr border bg-white text-center font-semibold focus:border-hasr-ink focus:ring-0"
      :class="big ? 'h-14 flex-1 border-hasr-line text-3xl' : 'h-11 w-14 border-transparent text-lg'"
      @input="set($event.target.value)"
      @focus="$event.target.select()"
    />
    <IconButton :label="__('Increase')" @click="set(modelValue + step)">
      <LucidePlus class="size-5" />
    </IconButton>
  </div>
</template>

<script setup>
import IconButton from './IconButton.vue'

defineProps({ modelValue: { type: Number, default: 0 }, step: { type: Number, default: 1 }, label: String, big: Boolean })
const emit = defineEmits(['update:modelValue'])

function set(value) {
  const n = Math.max(0, Number(value) || 0)
  emit('update:modelValue', Math.round(n * 1000) / 1000)
}
</script>
