<template>
  <Sheet :open="!!item" :label="item ? item.item_name : ''" @update:open="!$event && $emit('close')">
    <div v-if="item" class="space-y-4 pb-2">
      <div class="flex items-start gap-3">
        <button type="button" class="shrink-0" :aria-label="__('Photo')" @click="item.image && (zoomOpen = true)">
          <ItemThumb :src="item.image" :size="72" />
        </button>
        <div class="min-w-0 flex-1 space-y-0.5">
          <h2 class="text-lg font-semibold leading-snug" dir="auto">{{ item.item_name }}</h2>
          <p class="ltr-text text-[14px] text-hasr-muted">{{ item.item_code }}</p>
          <button type="button" class="text-[13px] text-hasr-info" @click="$emit('details', item.item_code)">{{ __('Item details') }}</button>
        </div>
        <IconButton :label="__('Close')" @click="$emit('close')"><LucideX class="size-5" /></IconButton>
      </div>

      <!-- batch items are counted batch by batch -->
      <div v-if="item.has_batch_no && step === 'batch'" class="space-y-3">
        <p class="text-center text-[15px] text-hasr-secondary">{{ __('Which batch are you counting?') }}</p>
        <ul class="divide-y divide-hasr-line rounded-tile border border-hasr-line">
          <li v-for="b in batches" :key="b.batch_no">
            <button type="button" class="flex w-full items-center gap-3 px-3 py-3 text-start active:bg-hasr-surface2" @click="pickBatch(b.batch_no)">
              <span class="min-w-0 flex-1">
                <span class="ltr-text block text-[16px] font-medium">{{ b.batch_no }}</span>
                <span v-if="b.expiry_date" class="block text-[13px] text-hasr-muted">{{ __('Expires {0}', [displayDate(b.expiry_date)]) }}</span>
              </span>
              <span v-if="countedOf(b.batch_no) !== null" class="tabular text-[15px] font-semibold text-hasr-success">
                {{ formatNumber(countedOf(b.batch_no)) }}
              </span>
              <LucideChevronRight class="size-5 text-hasr-muted rtl:-scale-x-100" />
            </button>
          </li>
          <li v-if="!batches.length" class="px-3 py-3 text-[15px] text-hasr-muted">{{ __('This item has no batches in ERPNext.') }}</li>
        </ul>
        <p class="text-center text-[13px] text-hasr-muted">{{ __('Batch not in the list? Scan its GS1 code, or tell your supervisor.') }}</p>
      </div>

      <div v-else class="space-y-3">
        <button v-if="item.has_batch_no" type="button" class="flex w-full items-center justify-between rounded-hasr bg-hasr-surface2 px-3 py-2 text-[15px]" @click="step = 'batch'">
          <span>{{ __('Batch') }} <b class="ltr-text">{{ batchNo }}</b></span>
          <span class="text-hasr-info">{{ __('Change') }}</span>
        </button>
        <p class="text-center text-[15px] text-hasr-secondary">{{ __('How many are on the shelf?') }}</p>
        <p v-if="previous !== null" class="-mt-2 text-center text-[13px] text-hasr-muted">
          {{ __('You counted {0} {1}. Type the total again to change it.', [formatNumber(previous), __(item.stock_uom)]) }}
        </p>
        <p class="tabular text-center text-[44px] font-semibold leading-tight" dir="ltr">{{ qtyText || '0' }}</p>
        <div v-if="item.uoms.length > 1" class="flex justify-center">
          <div class="inline-flex gap-0.5 rounded-hasr bg-hasr-surface2 p-1" role="radiogroup" :aria-label="__('Unit')">
            <button
              v-for="u in item.uoms"
              :key="u.uom"
              type="button"
              role="radio"
              :aria-checked="u.uom === uom"
              class="rounded-[8px] px-3 py-1.5 text-[15px]"
              :class="u.uom === uom ? 'bg-white font-semibold shadow-sm' : ''"
              @click="uom = u.uom"
            >
              {{ __(u.uom) }}
            </button>
          </div>
        </div>
        <p class="min-h-5 text-center text-sm text-hasr-muted">
          <template v-if="cf !== 1">= {{ formatNumber(stockQty) }} {{ __(item.stock_uom) }}</template>
        </p>
        <p v-if="notWhole" class="text-center text-sm text-hasr-danger" role="alert">
          {{ __('{0} is counted in whole {1}. Type a whole number.', [item.item_name, __(item.stock_uom)]) }}
        </p>
        <Keypad :decimal="!item.whole_units || cf !== 1" @key="onKey" />
        <button
          type="button"
          class="h-12 w-full rounded-hasr bg-hasr-ink text-[16px] font-medium text-white disabled:opacity-50"
          :disabled="!editable || qtyText === '' || notWhole || (item.has_batch_no && !batchNo)"
          @click="save"
        >
          {{ __('Save count') }}
        </button>
      </div>
    </div>
    <ImageZoom v-model:open="zoomOpen" :src="item && item.image" />
  </Sheet>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import Sheet from './Sheet.vue'
import Keypad from './Keypad.vue'
import ItemThumb from './ItemThumb.vue'
import IconButton from './IconButton.vue'
import ImageZoom from './ImageZoom.vue'
import { displayDate } from '../expiry'
import { formatNumber } from '../i18n'

// entry: what the scan told ({ uom, batch_no }); counts: what this person counted, { "item|batch": qty }
const props = defineProps({ item: Object, entry: Object, counts: Object, editable: Boolean })
const emit = defineEmits(['close', 'save', 'details'])

const step = ref('qty')
const batchNo = ref('')
const uom = ref('')
const qtyText = ref('')
const fresh = ref(true)
const zoomOpen = ref(false)

const batches = computed(() => {
  const all = props.item?.batches || []
  const only = props.item?.recount_batches
  return only ? all.filter((b) => only.includes(b.batch_no)) : all
})
const cf = computed(() => props.item?.uoms.find((u) => u.uom === uom.value)?.conversion_factor || 1)
const stockQty = computed(() => Math.round((Number(qtyText.value) || 0) * cf.value * 1e6) / 1e6)
const notWhole = computed(() => !!props.item?.whole_units && Math.abs(stockQty.value - Math.round(stockQty.value)) > 1e-6)
const countedOf = (batch) => {
  const v = props.counts?.[`${props.item.item_code}|${batch || ''}`]
  return v === undefined ? null : v
}
const previous = computed(() => (props.item && (!props.item.has_batch_no || batchNo.value) ? countedOf(batchNo.value) : null))

watch(
  () => props.item,
  (item) => {
    if (!item) return
    const scanned = props.entry || {}
    uom.value = scanned.uom && item.uoms.some((u) => u.uom === scanned.uom) ? scanned.uom : item.stock_uom
    batchNo.value = scanned.batch_no || (batches.value.length === 1 ? batches.value[0].batch_no : '')
    step.value = item.has_batch_no && !batchNo.value ? 'batch' : 'qty'
    resetQty()
  },
  { immediate: true },
)

function resetQty() {
  qtyText.value = ''
  fresh.value = true
}

function pickBatch(batch) {
  batchNo.value = batch
  step.value = 'qty'
  resetQty()
}

function onKey(k) {
  const start = fresh.value && k !== 'del' ? '' : qtyText.value
  fresh.value = false
  if (k === 'del') qtyText.value = start.slice(0, -1)
  else if (k === '.') qtyText.value = start.includes('.') ? start : (start || '0') + '.'
  else qtyText.value = (start === '0' ? '' : start) + k
  qtyText.value = qtyText.value.slice(0, 9)
}

function save() {
  emit('save', { item_code: props.item.item_code, batch_no: props.item.has_batch_no ? batchNo.value : null, qty: stockQty.value })
}
</script>
