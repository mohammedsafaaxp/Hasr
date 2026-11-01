<template>
  <!-- our own keypad: the phone keyboard never opens and covers the screen -->
  <div class="grid grid-cols-3 gap-1.5 rounded-tile bg-hasr-surface2 p-2" dir="ltr">
    <template v-for="(k, i) in keys" :key="i">
      <span v-if="!k" />
      <button
        v-else
        type="button"
        class="tabular h-12 rounded-hasr bg-white text-[22px] font-medium shadow-[0_1px_0_rgba(0,0,0,0.08)] active:bg-hasr-line"
        :aria-label="k === 'del' ? __('Delete digit') : k"
        @click="$emit('key', k)"
      >
        <LucideDelete v-if="k === 'del'" class="mx-auto size-6" />
        <template v-else>{{ k }}</template>
      </button>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ decimal: Boolean })
defineEmits(['key'])
const keys = computed(() => ['1', '2', '3', '4', '5', '6', '7', '8', '9', props.decimal ? '.' : '', '0', 'del'])
</script>
