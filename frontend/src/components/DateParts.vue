<template>
  <div>
    <div class="flex items-end gap-2" role="group" :aria-label="label">
      <label v-for="p in parts" :key="p.key" class="space-y-0.5" :class="p.key === 'year' ? 'w-[4.75rem]' : 'w-14'">
        <span class="block text-center text-[12px] text-hasr-muted">{{ p.label }}</span>
        <input
          :ref="(el) => (inputs[p.key] = el)"
          :value="values[p.key]"
          type="text"
          inputmode="numeric"
          pattern="[0-9]*"
          :maxlength="p.max"
          :placeholder="p.placeholder"
          :aria-label="`${label} ${p.label}`"
          class="tabular h-11 w-full rounded-hasr border-0 bg-hasr-surface2 px-1 text-center text-[17px]"
          @input="onInput(p, $event)"
          @keydown.backspace="onBackspace(p, $event)"
        />
      </label>
    </div>
    <p v-if="error" class="mt-1 text-[13px] text-hasr-danger">{{ error }}</p>
  </div>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'
import { __ } from '../i18n'

// Day / month / year typed as numbers: faster with gloves than a calendar picker, and no locale surprises.
const props = defineProps({ modelValue: String, label: { type: String, default: '' } })
const emit = defineEmits(['update:modelValue'])
const values = reactive({ day: '', month: '', year: '' })
const inputs = {}
const parts = computed(() => [
  { key: 'day', label: __('Day'), max: 2, placeholder: 'DD', next: 'month', prev: null },
  { key: 'month', label: __('Month'), max: 2, placeholder: 'MM', next: 'year', prev: 'day' },
  { key: 'year', label: __('Year'), max: 4, placeholder: 'YYYY', next: null, prev: 'month' },
])

function fromIso(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || '')
  return m ? { day: m[3], month: m[2], year: m[1] } : null
}

watch(
  () => props.modelValue,
  (iso) => {
    const p = fromIso(iso)
    if (p && toIso() !== iso) Object.assign(values, p)
    if (!iso && toIso()) Object.assign(values, { day: '', month: '', year: '' })
  },
  { immediate: true },
)

function fullYear() {
  const y = values.year
  if (y.length === 2) return 2000 + Number(y)
  return y.length === 4 ? Number(y) : null
}

function toIso() {
  const d = Number(values.day)
  const m = Number(values.month)
  const y = fullYear()
  if (!d || !m || !y) return ''
  const date = new Date(Date.UTC(y, m - 1, d))
  if (date.getUTCFullYear() !== y || date.getUTCMonth() !== m - 1 || date.getUTCDate() !== d) return ''
  return `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

const complete = computed(() => values.day && values.month && values.year.length >= 2)
const error = computed(() => (complete.value && !toIso() ? __('This date does not exist.') : ''))

function onInput(p, event) {
  const digits = event.target.value.replace(/\D/g, '').slice(0, p.max)
  values[p.key] = digits
  event.target.value = digits
  emit('update:modelValue', toIso())
  // move on when the part is complete: two digits, or a digit that cannot start a longer day (4-9) or month (2-9)
  const full = digits.length === p.max || (p.key === 'day' && Number(digits) > 3) || (p.key === 'month' && Number(digits) > 1)
  if (full && p.next) inputs[p.next]?.focus()
}

function onBackspace(p, event) {
  if (!event.target.value && p.prev) inputs[p.prev]?.focus()
}
</script>
