<template>
  <Sheet :open="!!line" :label="line ? line.item_name : ''" @update:open="!$event && $emit('close')">
    <div v-if="line" class="space-y-5 pb-2">
      <div class="flex items-start gap-3">
        <button type="button" class="relative shrink-0" :aria-label="__('Photo')" @click="zoomOpen = !!line.image">
          <ItemThumb :src="line.image" :size="96" />
          <span v-if="line.image" class="absolute -bottom-1 -end-1 flex size-7 items-center justify-center rounded-full bg-hasr-ink text-white">
            <LucideMaximize2 class="size-3.5" />
          </span>
        </button>
        <div class="min-w-0 flex-1 space-y-1">
          <h2 class="text-lg font-semibold leading-tight" dir="auto">{{ line.item_name }}</h2>
          <p class="text-sm text-hasr-muted"><span class="ltr-text">{{ line.item_code }}</span> · {{ __('Ordered {0}', [orderedText(line)]) }}</p>
          <p v-for="b in barcodeRows(line)" :key="b.barcode" class="flex items-center gap-1.5 text-[14px]">
            <span class="ltr-text tabular font-medium">{{ b.barcode }}</span>
            <span class="whitespace-nowrap rounded bg-hasr-surface2 px-1.5 text-[12px] text-hasr-secondary">{{ b.unit }}</span>
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

      <div v-if="line.has_batch_no" class="space-y-2">
        <div class="flex items-baseline justify-between gap-2">
          <p class="text-sm text-hasr-secondary">{{ __('Expiry and batch') }}</p>
          <p class="text-[13px] text-hasr-muted">{{ __('A batch is created for each date') }}</p>
        </div>
        <div class="divide-y divide-hasr-line rounded-tile border border-hasr-line">
          <div v-for="(b, i) in batches" :key="i" class="space-y-2 p-3">
            <div class="flex items-end gap-2">
              <label class="min-w-0 flex-1 space-y-1">
                <span class="text-[13px] text-hasr-muted">{{ __('Expiry date') }}</span>
                <input
                  v-model="b.expiry_date"
                  type="date"
                  :min="today"
                  class="tabular h-11 w-full rounded-hasr border-0 bg-hasr-surface2 px-3"
                  @change="onBatchChange"
                />
              </label>
              <label class="w-20 shrink-0 space-y-1">
                <span class="text-[13px] text-hasr-muted">{{ __('Qty') }}</span>
                <input
                  v-model.number="b.qty"
                  type="number"
                  min="0"
                  inputmode="decimal"
                  class="tabular h-11 w-full rounded-hasr border-0 bg-hasr-surface2 text-center"
                  :disabled="batches.length === 1"
                  @input="onBatchChange"
                />
              </label>
              <IconButton v-if="batches.length > 1" :label="__('Remove')" @click="removeBatch(i)">
                <LucideTrash2 class="size-5" />
              </IconButton>
            </div>
            <p class="flex flex-wrap items-center gap-2 text-[13px] text-hasr-muted">
              <Pill>{{ __('New batch') }}</Pill>
              <span>{{ __('number given on approval') }}</span>
              <span v-if="shelfWarning(b)" class="flex items-center gap-1 text-hasr-warning">
                <LucideTriangleAlert class="size-4" />{{ shelfWarning(b) }}
              </span>
            </p>
          </div>
        </div>
        <button type="button" class="flex h-11 items-center gap-2 text-[15px]" @click="addBatch">
          <LucidePlus class="size-5" />{{ __('Add another expiry date') }}
        </button>
        <p v-if="batches.length > 1" class="tabular text-sm text-hasr-muted">
          <span class="ltr-text">{{ batches.map((b) => formatNumber(b.qty || 0)).join(' + ') }} = {{ formatNumber(batchTotal) }}</span>
          {{ __(line.stock_uom) }}
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
    <ImageZoom v-model:open="zoomOpen" :src="line && line.image" />
  </Sheet>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import Sheet from './Sheet.vue'
import Stepper from './Stepper.vue'
import IconButton from './IconButton.vue'
import ItemThumb from './ItemThumb.vue'
import Pill from './Pill.vue'
import ImageZoom from './ImageZoom.vue'
import { api, errorMessage } from '../api'
import { __, formatNumber } from '../i18n'
import { barcodeRows, orderedText } from '../uom'

const props = defineProps({ line: Object, session: String, editable: Boolean, expiryWarningPct: Number })
const emit = defineEmits(['close', 'saved', 'details'])

const qty = ref(0)
const uom = ref('')
const rejected = ref(0)
const batches = ref([])
const saving = ref(false)
const error = ref('')
const zoomOpen = ref(false)
const today = new Date().toISOString().slice(0, 10)

const cf = computed(() => props.line?.uoms.find((u) => u.uom === uom.value)?.conversion_factor || 1)
const receivedStock = computed(() => round(qty.value * cf.value))
const batchTotal = computed(() => round(batches.value.reduce((sum, b) => sum + (Number(b.qty) || 0), 0)))
const overBy = computed(() => {
  if (!props.line) return 0
  return round(props.line.already_received_qty + receivedStock.value + rejected.value - props.line.allowed_qty)
})

function round(n) {
  return Math.round(n * 1000) / 1000
}

watch(
  () => props.line,
  (line) => {
    if (!line) return
    uom.value = line.stock_uom
    qty.value = line.received_qty
    rejected.value = line.rejected_qty
    batches.value = line.batches.length ? line.batches.map((b) => ({ ...b })) : [{ expiry_date: '', qty: line.received_qty }]
    error.value = ''
  },
  { immediate: true },
)

// changing the unit keeps the same physical quantity
watch(uom, (next, prev) => {
  if (!prev || !props.line) return
  const prevCf = props.line.uoms.find((u) => u.uom === prev)?.conversion_factor || 1
  qty.value = round((qty.value * prevCf) / cf.value)
})

// one expiry date takes the whole received quantity
watch(receivedStock, (stock) => {
  if (batches.value.length === 1) batches.value[0].qty = stock
})

// several expiry dates: the received quantity is their sum
function onBatchChange() {
  if (batches.value.length > 1) qty.value = round(batchTotal.value / cf.value)
}

function addBatch() {
  batches.value.push({ expiry_date: '', qty: 0 })
}

function removeBatch(i) {
  batches.value.splice(i, 1)
  if (batches.value.length === 1) batches.value[0].qty = receivedStock.value
  else onBatchChange()
}

function shelfWarning(b) {
  const life = props.line.shelf_life_in_days
  if (!b.expiry_date || !life || !props.expiryWarningPct) return ''
  const daysLeft = Math.round((new Date(b.expiry_date + 'T00:00:00') - new Date(today + 'T00:00:00')) / 86400000)
  if (daysLeft >= (life * props.expiryWarningPct) / 100) return ''
  return __('Short shelf life: {0} days left', [daysLeft])
}

function batchesToSend() {
  if (!props.line.has_batch_no) return null
  const filled = batches.value.filter((b) => b.expiry_date)
  if (!filled.length) return receivedStock.value || rejected.value ? undefined : []
  if (filled.length !== batches.value.length) throw new Error(__('Enter an expiry date for every row.'))
  return filled.map((b) => ({ expiry_date: b.expiry_date, qty: Number(b.qty) || 0 }))
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    const args = {
      session: props.session,
      po_item: props.line.po_item,
      received_qty: receivedStock.value,
      rejected_qty: rejected.value,
    }
    const toSend = batchesToSend()
    if (toSend) args.batches = toSend
    emit('saved', await api('receiving.set_line', args))
  } catch (e) {
    error.value = e && e.messages ? errorMessage(e) : e.message || errorMessage(e)
  } finally {
    saving.value = false
  }
}
</script>
