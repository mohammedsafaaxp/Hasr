<template>
  <Sheet :open="!!line" :label="line ? line.item_name : ''" @update:open="!$event && $emit('close')">
    <div v-if="line" class="space-y-5 pb-2">
      <div class="flex items-start gap-3">
        <button type="button" class="relative" :aria-label="__('Item details')" @click="$emit('details', line.item_code)">
          <ItemThumb :src="line.image" :size="56" />
          <span class="absolute -bottom-1 -end-1 flex size-6 items-center justify-center rounded-full bg-hasr-ink text-white">
            <LucideMaximize2 class="size-3" />
          </span>
        </button>
        <div class="min-w-0 flex-1">
          <h2 class="text-lg font-semibold leading-tight" dir="auto">{{ line.item_name }}</h2>
          <p class="text-sm text-hasr-muted">
            <span class="ltr-text">{{ line.item_code }}</span> ·
            {{ __('ordered {0} {1}', [formatNumber(line.pending_qty), __(line.stock_uom)]) }}
          </p>
          <button type="button" class="text-sm text-hasr-info" @click="$emit('details', line.item_code)">{{ __('Item details') }}</button>
        </div>
        <IconButton :label="__('Close')" @click="$emit('close')"><LucideX class="size-5" /></IconButton>
      </div>

      <div class="space-y-2">
        <p class="text-sm text-hasr-secondary">{{ __('Received quantity') }}</p>
        <div class="flex items-center gap-2">
          <Stepper v-model="qty" big class="min-w-0 flex-1" :label="__('Received quantity')" />
          <select
            v-model="uom"
            class="h-14 w-24 shrink-0 rounded-hasr border-0 bg-hasr-surface2 pe-8 ps-3 text-[15px]"
            :aria-label="__('Unit')"
            :disabled="!editable"
          >
            <option v-for="u in line.uoms" :key="u.uom" :value="u.uom">{{ __(u.uom) }}</option>
          </select>
        </div>
        <p v-if="cf !== 1" class="text-sm text-hasr-muted">
          {{ __('{0} {1} = {2} {3}', [formatNumber(qty), __(uom), formatNumber(receivedStock), __(line.stock_uom)]) }}
        </p>
        <p v-if="overBy > 0" class="flex items-center gap-1.5 text-sm text-hasr-warning">
          <LucideTriangleAlert class="size-4" />
          {{ __('{0} over the limit. The supervisor will decide.', [formatNumber(overBy)]) }}
        </p>
      </div>

      <div class="flex items-center gap-3 rounded-tile border border-hasr-line p-3">
        <div class="min-w-0 flex-1">
          <p class="text-[15px] font-medium">{{ __('Rejected quantity') }}</p>
          <p class="text-[13px] text-hasr-muted">{{ __('Damaged or expired, goes to the rejected warehouse') }}</p>
        </div>
        <Stepper v-model="rejected" :label="__('Rejected quantity')" />
      </div>

      <p v-if="error" class="rounded-hasr bg-hasr-danger-bg p-3 text-sm text-hasr-danger">{{ error }}</p>

      <div class="flex gap-3">
        <button
          type="button"
          class="h-11 flex-1 rounded-hasr bg-hasr-ink text-[15px] font-medium text-white disabled:opacity-50"
          :disabled="saving || !editable"
          @click="save"
        >
          {{ saving ? __('Saving…') : __('Save line') }}
        </button>
        <button type="button" class="h-11 rounded-hasr bg-hasr-surface2 px-5 text-[15px] font-medium" @click="$emit('close')">
          {{ __('Cancel') }}
        </button>
      </div>
    </div>
  </Sheet>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import Sheet from './Sheet.vue'
import Stepper from './Stepper.vue'
import IconButton from './IconButton.vue'
import ItemThumb from './ItemThumb.vue'
import { api, errorMessage } from '../api'
import { formatNumber } from '../i18n'

const props = defineProps({ line: Object, session: String, editable: Boolean })
const emit = defineEmits(['close', 'saved', 'details'])

const qty = ref(0)
const uom = ref('')
const rejected = ref(0)
const saving = ref(false)
const error = ref('')

const cf = computed(() => props.line?.uoms.find((u) => u.uom === uom.value)?.conversion_factor || 1)
const receivedStock = computed(() => Math.round(qty.value * cf.value * 1000) / 1000)
const overBy = computed(() => {
  if (!props.line) return 0
  const total = props.line.already_received_qty + receivedStock.value + rejected.value
  return Math.round((total - props.line.allowed_qty) * 1000) / 1000
})

watch(
  () => props.line,
  (line) => {
    if (!line) return
    uom.value = line.stock_uom
    qty.value = line.received_qty
    rejected.value = line.rejected_qty
    error.value = ''
  },
  { immediate: true },
)

// changing the unit keeps the same physical quantity
watch(uom, (next, prev) => {
  if (!prev || !props.line) return
  const prevCf = props.line.uoms.find((u) => u.uom === prev)?.conversion_factor || 1
  qty.value = Math.round(((qty.value * prevCf) / cf.value) * 1000) / 1000
})

async function save() {
  saving.value = true
  error.value = ''
  try {
    const session = await api('receiving.set_line', {
      session: props.session,
      po_item: props.line.po_item,
      received_qty: receivedStock.value,
      rejected_qty: rejected.value,
    })
    emit('saved', session)
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}
</script>
