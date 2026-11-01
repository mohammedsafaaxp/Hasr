<template>
  <Sheet :open="!!line" :label="line ? line.item_name : ''" @update:open="!$event && $emit('close')">
    <div v-if="line" class="space-y-4 pb-2">
      <div class="flex items-center gap-3">
        <button type="button" class="shrink-0" :aria-label="__('Photo')" @click="zoomOpen = !!line.image">
          <ItemThumb :src="line.image" :size="64" />
        </button>
        <div class="min-w-0 flex-1">
          <h2 class="text-[17px] font-semibold leading-tight" dir="auto">{{ line.item_name }}</h2>
          <p class="text-sm text-hasr-muted">{{ __('Ordered {0}', [orderedText(line)]) }}</p>
          <button type="button" class="text-[13px] text-hasr-info" @click="$emit('details', line.item_code)">{{ __('Item details') }}</button>
        </div>
        <IconButton :label="__('Close')" @click="$emit('close')"><LucideX class="size-5" /></IconButton>
      </div>

      <!-- read only once sent for review -->
      <div v-if="!editable" class="space-y-1 rounded-tile border border-hasr-line p-3 text-[15px]">
        <p>{{ __('Received quantity') }}: <span class="tabular font-semibold">{{ formatNumber(line.received_qty) }} {{ __(line.stock_uom) }}</span></p>
        <p v-for="b in line.batches" :key="b.expiry_date" class="text-sm text-hasr-muted">
          <span class="ltr-text tabular">{{ displayDate(b.expiry_date) }}</span> · {{ formatNumber(b.qty) }}
        </p>
      </div>

      <template v-else>
        <div class="flex items-center gap-3">
          <button v-if="stepIndex > 0" type="button" class="text-sm text-hasr-secondary" @click="back">{{ __('Back') }}</button>
          <div class="flex flex-1 gap-1.5" aria-hidden="true">
            <span v-for="(s, i) in steps" :key="s" class="h-1 flex-1 rounded-full" :class="i <= stepIndex ? 'bg-hasr-ink' : 'bg-hasr-line'" />
          </div>
        </div>

        <!-- 1. check the item -->
        <div v-if="step === 'check'" class="space-y-3">
          <template v-if="!check">
            <p class="text-center text-[15px] text-hasr-secondary">{{ __('Scan the carton or the item to check it') }}</p>
            <button
              type="button"
              class="flex h-32 w-full flex-col items-center justify-center gap-2 rounded-tile border-2 border-dashed border-hasr-line bg-hasr-surface2 text-[16px] font-semibold"
              @click="cameraOpen = true"
            >
              <LucideScanBarcode class="size-9" />{{ __('Tap to scan') }}
            </button>
            <form class="space-y-1.5" @submit.prevent="checkBarcode(typed)">
              <label for="hasr-check-code" class="text-[13px] text-hasr-muted">{{ __('Or enter the barcode or item code') }}</label>
              <div class="flex gap-2">
                <!-- inputmode none until tapped: a hardware scanner types here without opening the phone keyboard -->
                <input
                  id="hasr-check-code"
                  ref="scanField"
                  v-model="typed"
                  type="text"
                  :inputmode="typing ? 'text' : 'none'"
                  autocomplete="off"
                  autocapitalize="off"
                  spellcheck="false"
                  enterkeyhint="go"
                  class="ltr-text h-12 min-w-0 flex-1 rounded-hasr border-0 bg-hasr-surface2 px-3 text-[16px]"
                  @pointerdown="startTyping"
                />
                <button type="submit" class="h-12 shrink-0 rounded-hasr bg-hasr-surface2 px-4 text-[15px] font-medium">{{ __('Check') }}</button>
              </div>
            </form>
          </template>
          <div v-else-if="check.ok" class="py-6 text-center text-hasr-success" role="status">
            <LucideCircleCheck class="mx-auto size-10" />
            <p class="mt-2 text-lg font-semibold">{{ __('Matches this item') }}</p>
            <p class="text-sm"><span class="ltr-text tabular">{{ check.barcode }}</span><template v-if="check.unit"> · {{ check.unit }}</template></p>
          </div>
          <div v-else class="space-y-3 rounded-tile bg-hasr-danger-bg p-4 text-hasr-danger" role="alert">
            <div class="flex items-start gap-2">
              <LucideCircleX class="mt-0.5 size-5 shrink-0" />
              <div>
                <p class="font-semibold">{{ __('This barcode is not for this item') }}</p>
                <p class="ltr-text tabular text-sm">{{ check.barcode }}</p>
              </div>
            </div>
            <div class="flex gap-2">
              <button type="button" class="h-11 flex-1 rounded-hasr bg-hasr-danger text-[15px] font-medium text-white" @click="$emit('mismatch', line, check.barcode)">
                {{ __('Report to the supervisor') }}
              </button>
              <button type="button" class="h-11 rounded-hasr bg-white px-4 text-[15px] font-medium text-hasr-ink" @click="resetCheck">{{ __('Scan again') }}</button>
            </div>
          </div>
        </div>

        <!-- 2. quantity -->
        <div v-else-if="step === 'qty'" class="space-y-3">
          <p class="text-center text-[15px] text-hasr-secondary">{{ __('How many did you receive?') }}</p>
          <p class="tabular text-center text-[44px] font-semibold leading-tight" dir="ltr">{{ qtyText || '0' }}</p>
          <div v-if="line.uoms.length > 1" class="flex justify-center">
            <div class="inline-flex gap-0.5 rounded-hasr bg-hasr-surface2 p-1" role="radiogroup" :aria-label="__('Unit')">
              <button
                v-for="u in line.uoms"
                :key="u.uom"
                type="button"
                role="radio"
                :aria-checked="u.uom === uom"
                class="rounded-[8px] px-3 py-1.5 text-[15px]"
                :class="u.uom === uom ? 'bg-white font-semibold shadow-sm' : ''"
                @click="setUom(u.uom)"
              >
                {{ __(u.uom) }}
              </button>
            </div>
          </div>
          <p class="min-h-5 text-center text-sm text-hasr-muted">
            <template v-if="cf !== 1">= {{ formatNumber(receivedStock) }} {{ __(line.stock_uom) }}</template>
          </p>
          <div v-if="wholeWarning" class="flex gap-2 rounded-hasr bg-hasr-warning-bg p-3 text-sm text-hasr-warning" role="alert">
            <LucideTriangleAlert class="mt-0.5 size-4 shrink-0" />
            <span>{{ wholeWarning }}</span>
          </div>
          <p v-if="overBy > 0" class="flex items-center justify-center gap-1.5 text-sm text-hasr-warning">
            <LucideTriangleAlert class="size-4" />
            {{ __('{0} over the limit. The supervisor will decide.', [formatNumber(overBy)]) }}
          </p>
          <Keypad decimal @key="onQtyKey" />
          <button
            v-if="line.has_batch_no && receivedStock > 0"
            type="button"
            class="h-12 w-full rounded-hasr bg-hasr-ink text-[16px] font-medium text-white"
            @click="go('expiry')"
          >
            {{ __('Next') }}
          </button>
          <button v-else type="button" class="h-12 w-full rounded-hasr bg-hasr-ink text-[16px] font-medium text-white disabled:opacity-50" :disabled="saving" @click="save">
            {{ saving ? __('Saving…') : __('Save line') }}
          </button>
        </div>

        <!-- 3. expiry date -->
        <div v-else-if="step === 'expiry'" class="space-y-3">
          <p class="text-center text-[15px] text-hasr-secondary">{{ __('Expiry date') }}</p>
          <div class="mx-auto w-fit" dir="ltr">
            <p class="tabular flex items-center justify-center gap-2 text-[36px] font-semibold leading-tight">
              <template v-for="(p, i) in slots" :key="i">
                <span v-if="i" class="text-hasr-muted">/</span>
                <span class="inline-block w-[2ch] text-center" :class="p.includes('_') ? 'text-hasr-line' : ''">{{ p }}</span>
              </template>
            </p>
            <p class="flex justify-around text-[12px] text-hasr-muted">
              <span v-if="!monthOnly">{{ __('Day') }}</span><span>{{ __('Month') }}</span><span>{{ __('Year') }}</span>
            </p>
          </div>
          <p class="min-h-5 text-center text-sm" :class="dateStatus.cls" aria-live="polite">
            <template v-if="dateStatus.text">{{ dateStatus.text }}</template>
            <template v-else>
              {{ __('Type the digits on the pack, for example') }}
              <span class="ltr-text tabular font-semibold">{{ monthOnly ? '0327' : '150327' }}</span>
              = <span class="ltr-text tabular">{{ monthOnly ? '03/2027' : '15/03/2027' }}</span>
            </template>
          </p>
          <div class="flex flex-wrap justify-center gap-2">
            <button v-if="lastExpiry" type="button" class="h-9 rounded-full border border-hasr-line px-3 text-sm" @click="useLastExpiry">
              <span class="ltr-text tabular">{{ displayDate(lastExpiry) }}</span> {{ __('last date') }}
            </button>
            <button
              type="button"
              class="h-9 rounded-full border px-3 text-sm"
              :class="monthOnly ? 'border-hasr-ink bg-hasr-ink text-white' : 'border-hasr-line'"
              :aria-pressed="monthOnly"
              @click="toggleMonthOnly"
            >
              {{ __('Month and year only') }}
            </button>
          </div>

          <div v-if="dates.length" class="space-y-1.5">
            <div v-for="(b, i) in dates" :key="i" class="flex items-center gap-2 rounded-hasr bg-hasr-surface2 px-3 py-1.5 text-sm">
              <span class="ltr-text tabular flex-1">{{ displayDate(b.expiry_date) }}</span>
              <input
                v-model.number="b.qty"
                type="number"
                min="0"
                inputmode="decimal"
                class="tabular h-9 w-20 rounded-hasr border-0 bg-white text-center"
                :aria-label="__('Qty')"
              />
              <span class="text-hasr-muted">{{ __(line.stock_uom) }}</span>
              <IconButton :label="__('Remove')" @click="dates.splice(i, 1)"><LucideTrash2 class="size-4" /></IconButton>
            </div>
            <p class="text-sm text-hasr-muted">
              {{ __('The date above takes the rest: {0} {1}', [formatNumber(rest), __(line.stock_uom)]) }}
            </p>
          </div>

          <Keypad @key="onDateKey" />
          <p v-if="error" class="rounded-hasr bg-hasr-danger-bg p-3 text-sm text-hasr-danger">{{ error }}</p>
          <div class="flex gap-2">
            <button type="button" class="h-12 rounded-hasr bg-hasr-surface2 px-3 text-[14px] font-medium disabled:opacity-50" :disabled="!entryIso" @click="addDate">
              {{ __('+ Another date') }}
            </button>
            <button
              type="button"
              class="h-12 flex-1 rounded-hasr bg-hasr-ink text-[16px] font-medium text-white disabled:opacity-50"
              :disabled="saving || !canSaveDates"
              @click="save"
            >
              {{ saving ? __('Saving…') : __('Save line') }}
            </button>
          </div>
        </div>

        <p v-if="error && step !== 'expiry'" class="rounded-hasr bg-hasr-danger-bg p-3 text-sm text-hasr-danger">{{ error }}</p>
      </template>
    </div>
    <ImageZoom v-model:open="zoomOpen" :src="line && line.image" />
    <CameraSheet v-model:open="cameraOpen" single @scan="checkBarcode" />
  </Sheet>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Sheet from './Sheet.vue'
import IconButton from './IconButton.vue'
import ItemThumb from './ItemThumb.vue'
import ImageZoom from './ImageZoom.vue'
import CameraSheet from './CameraSheet.vue'
import Keypad from './Keypad.vue'
import { api, errorMessage } from '../api'
import { __, formatNumber, lang as langRef } from '../i18n'
import { barcodeRows, orderedText } from '../uom'
import { feedbackError, feedbackSuccess } from '../sound'
import { daysUntil, digitsToIso, displayDate, isoToDigits, slotParts } from '../expiry'

const props = defineProps({ line: Object, session: String, editable: Boolean, expiryWarningPct: Number })
const emit = defineEmits(['close', 'saved', 'details', 'mismatch'])

const step = ref('check')
const qtyText = ref('')
const freshQty = ref(true)
const uom = ref('')
const dates = ref([])
const entry = ref('')
const freshEntry = ref(false)
const monthOnly = ref(false)
const saving = ref(false)
const error = ref('')
const zoomOpen = ref(false)
const cameraOpen = ref(false)
const check = ref(null)
const typed = ref('')
const typing = ref(false)
const scanField = ref(null)
const lastExpiry = ref('')

const steps = computed(() => (props.line?.has_batch_no ? ['check', 'qty', 'expiry'] : ['check', 'qty']))
const stepIndex = computed(() => steps.value.indexOf(step.value))
const cf = computed(() => props.line?.uoms.find((u) => u.uom === uom.value)?.conversion_factor || 1)
const qty = computed(() => Number(qtyText.value) || 0)
const receivedStock = computed(() => round(qty.value * cf.value))
const overBy = computed(() => {
  if (!props.line) return 0
  return round(props.line.already_received_qty + receivedStock.value + props.line.rejected_qty - props.line.allowed_qty)
})

// The Purchase Receipt stays in the order's unit, so a box line takes whole boxes only.
const wholeWarning = computed(() => {
  const l = props.line
  if (!l || !l.uom_must_be_whole) return ''
  const poCf = l.conversion_factor || 1
  if (Math.abs(receivedStock.value / poCf - Math.round(receivedStock.value / poCf)) < 1e-6) return ''
  const examples = [1, 2, 3].map((n) => formatNumber(n * poCf)).join(langRef.value === 'ar' ? '، ' : ', ')
  return __('This order is in {0} (1 {0} = {1} {2}). Enter whole {0} only: {3}… You cannot finish the shipment until this is fixed.', [
    __(l.uom),
    formatNumber(poCf),
    __(l.stock_uom),
    examples,
  ])
})

const slots = computed(() => slotParts(entry.value, monthOnly.value))
const entryIso = computed(() => digitsToIso(entry.value, monthOnly.value) || '')
const committed = computed(() => round(dates.value.reduce((sum, b) => sum + (Number(b.qty) || 0), 0)))
const rest = computed(() => round(receivedStock.value - committed.value))
const dateStatus = computed(() => {
  const iso = digitsToIso(entry.value, monthOnly.value)
  if (iso === null) return { cls: 'text-hasr-danger', text: __('This date does not exist.') }
  if (!iso) return { cls: '', text: '' }
  const left = daysUntil(iso)
  if (left < 0) return { cls: 'text-hasr-danger', text: __('Expired. Do not receive it.') }
  const life = props.line.shelf_life_in_days
  if (life && props.expiryWarningPct && left < (life * props.expiryWarningPct) / 100) {
    return { cls: 'text-hasr-warning', text: __('Short shelf life: {0} days left', [left]) }
  }
  return { cls: 'text-hasr-success', text: __('{0} days left', [left]) }
})
const entryUsable = computed(() => entryIso.value && daysUntil(entryIso.value) >= 0)
const canSaveDates = computed(() => {
  if (entry.value) return entryUsable.value && (!dates.value.length || rest.value > 0)
  return dates.value.length > 0 && Math.abs(rest.value) < 1e-6
})

function round(n) {
  return Math.round(n * 1000) / 1000
}

function checkedKey() {
  return `hasr_checked_${props.session}_${props.line.po_item}`
}

function remember(key, value) {
  try {
    localStorage.setItem(key, value)
  } catch (e) {
    /* not remembered */
  }
}

function recall(key) {
  try {
    return localStorage.getItem(key) || ''
  } catch (e) {
    return ''
  }
}

watch(
  () => props.line,
  (line, prev) => {
    if (!line) return
    if (prev && prev.po_item === line.po_item) return
    // open in the order's unit when the quantity fits it (boxes), otherwise in the stock unit
    const poCf = line.conversion_factor || 1
    const inPoUnit = line.uom && line.uom !== line.stock_uom && Math.abs(line.received_qty / poCf - Math.round(line.received_qty / poCf)) < 1e-6
    uom.value = inPoUnit && line.uoms.some((u) => u.uom === line.uom) ? line.uom : line.stock_uom
    qtyText.value = line.received_qty ? String(round(line.received_qty / cf.value)) : ''
    freshQty.value = true
    const saved = line.batches || []
    dates.value = saved.slice(0, -1).map((b) => ({ ...b }))
    entry.value = saved.length ? isoToDigits(saved[saved.length - 1].expiry_date) : ''
    freshEntry.value = !!entry.value
    monthOnly.value = false
    lastExpiry.value = recall(`hasr_last_expiry_${line.item_code}`)
    if (lastExpiry.value && daysUntil(lastExpiry.value) < 0) lastExpiry.value = ''
    error.value = ''
    check.value = null
    step.value = recall(checkedKey()) ? 'qty' : 'check'
    if (step.value === 'check') focusScanField()
  },
  { immediate: true },
)

function go(next) {
  error.value = ''
  step.value = next
}

function back() {
  go(steps.value[stepIndex.value - 1])
  if (step.value === 'check') resetCheck()
}

// 1. check: the carton or the item must be this line's product
function checkBarcode(code) {
  code = (code || '').trim()
  typed.value = ''
  if (!code || !props.line) return
  const row = barcodeRows(props.line).find((b) => b.barcode === code)
  const ok = !!row || code.toUpperCase() === props.line.item_code.toUpperCase()
  check.value = { ok, barcode: code, unit: row ? row.unit : '' }
  if (!ok) return feedbackError()
  feedbackSuccess()
  remember(checkedKey(), '1')
  setTimeout(() => step.value === 'check' && check.value?.ok && go('qty'), 700)
}

function resetCheck() {
  check.value = null
  typed.value = ''
  typing.value = false
  focusScanField()
}

function focusScanField() {
  // after the sheet has taken focus itself, so a hardware scanner types into the field
  setTimeout(() => scanField.value?.focus({ preventScroll: true }), 100)
}

function startTyping() {
  if (typing.value) return
  typing.value = true
  scanField.value?.blur()
  setTimeout(() => scanField.value?.focus(), 0)
}

// 2. quantity
function onQtyKey(k) {
  let text = freshQty.value ? '' : qtyText.value
  freshQty.value = false
  if (k === 'del') text = text.slice(0, -1)
  else if (k === '.') text = text.includes('.') ? text : (text || '0') + '.'
  else text = (text === '0' ? '' : text) + k
  qtyText.value = text.slice(0, 7)
}

function setUom(next) {
  if (next === uom.value) return
  const stock = receivedStock.value
  uom.value = next
  qtyText.value = stock ? String(round(stock / cf.value)) : ''
  freshQty.value = true
}

// 3. expiry
function onDateKey(k) {
  if (k === '.') return
  // a date shown from before is replaced by the first digit typed, like the quantity
  const start = freshEntry.value && k !== 'del' ? '' : entry.value
  freshEntry.value = false
  entry.value = k === 'del' ? start.slice(0, -1) : (start + k).slice(0, monthOnly.value ? 4 : 6)
}

function toggleMonthOnly() {
  monthOnly.value = !monthOnly.value
  entry.value = ''
}

function useLastExpiry() {
  monthOnly.value = false
  entry.value = isoToDigits(lastExpiry.value)
  freshEntry.value = true
}

function addDate() {
  if (!entryUsable.value) return
  dates.value.push({ expiry_date: entryIso.value, qty: Math.max(rest.value, 0) })
  entry.value = ''
  monthOnly.value = false
}

function batchesToSend() {
  if (!props.line.has_batch_no || !receivedStock.value) return props.line.has_batch_no ? [] : null
  const list = dates.value.map((b) => ({ expiry_date: b.expiry_date, qty: Number(b.qty) || 0 }))
  if (entry.value) list.push({ expiry_date: entryIso.value, qty: dates.value.length ? rest.value : receivedStock.value })
  return list.filter((b) => b.qty > 0)
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    const args = {
      session: props.session,
      po_item: props.line.po_item,
      received_qty: receivedStock.value,
      rejected_qty: props.line.rejected_qty,
    }
    const batches = batchesToSend()
    if (batches) args.batches = batches
    const session = await api('receiving.set_line', args)
    if (batches && batches.length) remember(`hasr_last_expiry_${props.line.item_code}`, batches[batches.length - 1].expiry_date)
    emit('saved', session)
  } catch (e) {
    error.value = e && e.messages ? errorMessage(e) : e.message || errorMessage(e)
  } finally {
    saving.value = false
  }
}

// a hardware keyboard works on the keypad steps too
function onKeydown(event) {
  if (!props.line || !props.editable || cameraOpen.value || zoomOpen.value) return
  if (['INPUT', 'TEXTAREA', 'SELECT'].includes(event.target.tagName)) return
  const key = event.key === 'Backspace' ? 'del' : event.key
  if (!/^[0-9.]$/.test(key) && key !== 'del') return
  if (step.value === 'qty') onQtyKey(key)
  else if (step.value === 'expiry') onDateKey(key)
  else return
  event.preventDefault()
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>
