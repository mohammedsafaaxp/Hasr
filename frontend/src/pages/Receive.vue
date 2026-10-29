<template>
  <div class="flex min-h-full flex-col">
    <header class="space-y-4 px-4 pt-4">
      <div class="flex items-start gap-3">
        <IconButton :label="__('Back')" @click="router.push({ name: 'Home' })">
          <LucideChevronLeft class="size-5 rtl:-scale-x-100" />
        </IconButton>
        <div class="min-w-0 flex-1">
          <h1 class="ltr-text truncate text-lg font-semibold">{{ s ? s.purchase_order : '' }}</h1>
          <p v-if="s" class="text-[15px] text-hasr-muted">
            <bdi>{{ s.supplier_name }}</bdi> · {{ __('shipment {0}', [s.shipment_no]) }}
          </p>
        </div>
        <button
          v-if="s && (s.editable || s.invoices.length)"
          type="button"
          class="relative inline-flex h-11 shrink-0 items-center gap-1.5 rounded-hasr bg-hasr-surface2 px-3 text-[14px]"
          :aria-label="__('Supplier invoice')"
          @click="invoiceOpen = true"
        >
          <LucideReceiptText class="size-5" />
          <span>{{ __('Invoice') }}</span>
          <span v-if="s.invoices.length" class="tabular rounded-full bg-hasr-ink px-1.5 text-[12px] text-white">{{ s.invoices.length }}</span>
        </button>
        <Pill v-if="!online" theme="orange"><LucideCloudOff class="size-4" />{{ __('Offline') }}</Pill>
        <Pill v-else-if="s && s.status !== 'Open'" :theme="statusTheme">{{ __(s.status) }}</Pill>
      </div>

      <p v-if="loadError" class="rounded-hasr bg-hasr-danger-bg p-3 text-sm text-hasr-danger">{{ loadError }}</p>

      <template v-if="s">
        <div
          v-if="s.status === 'Sent Back'"
          class="rounded-hasr bg-hasr-warning-bg p-3 text-sm text-hasr-warning"
        >
          <b>{{ __('Sent back by the supervisor') }}</b>
          <span v-if="s.review_note">: {{ s.review_note }}</span>
        </div>
        <div v-else-if="!s.editable" class="rounded-hasr bg-hasr-info-bg p-3 text-sm text-hasr-info">
          {{ s.status === 'Pending Approval' ? __('Sent for review. The supervisor will approve it.') : __('This shipment can no longer be changed.') }}
        </div>

        <div class="space-y-2">
          <div class="flex justify-between text-[15px] text-hasr-secondary">
            <span>{{ __('{0} of {1} items complete', [counts.done, s.lines.length]) }}</span>
            <span class="tabular">{{ formatNumber(percent, 0) }}%</span>
          </div>
          <div class="h-1.5 overflow-hidden rounded-full bg-hasr-line">
            <div class="h-full rounded-full bg-hasr-ink transition-all" :style="{ width: percent + '%' }" />
          </div>
        </div>

        <ScanInput
          v-if="s.editable"
          ref="scanInput"
          :active="!sheetOpen"
          @scan="onScan"
          @camera="cameraOpen = true"
        />

        <LastScanCard v-if="lastLine" :line="lastLine" :scan="lastScan" @zoom="zoom" />

        <div class="flex gap-2 overflow-x-auto pb-1">
          <button
            v-for="f in filters"
            :key="f.value"
            type="button"
            class="tabular h-10 shrink-0 rounded-full px-4 text-[15px]"
            :class="filterClass(f)"
            @click="filter = f.value"
          >
            {{ f.label }} {{ f.count }}
          </button>
        </div>
      </template>
    </header>

    <ul v-if="s" class="mt-2 flex-1 border-t border-hasr-line">
      <li
        v-for="l in shownLines"
        :key="l.po_item"
        :ref="(el) => (rowEls[l.po_item] = el)"
        class="flex items-start gap-3 border-b border-hasr-line px-4 py-3"
        :class="[isIssue(l) ? 'bg-[#FFFAF0]' : '', lastScan && lastScan.po_item === l.po_item ? 'outline outline-2 -outline-offset-2 outline-hasr-ink' : '']"
      >
        <button type="button" class="shrink-0" :aria-label="__('Photo')" @click="zoom(l.image)">
          <ItemThumb :src="l.image" :size="72" />
        </button>
        <button type="button" class="min-w-0 flex-1 space-y-0.5 text-start" @click="openLine(l)">
          <p class="text-[17px] leading-snug" dir="auto">{{ l.item_name }}</p>
          <p v-for="b in barcodeRows(l).slice(0, 2)" :key="b.barcode" class="flex items-center gap-1.5 text-[15px]">
            <span class="ltr-text tabular font-medium">{{ b.barcode }}</span>
            <span class="rounded bg-hasr-surface2 px-1.5 text-[12px] text-hasr-secondary">{{ b.unit }}</span>
          </p>
          <p v-if="!l.barcodes.length" class="ltr-text text-[15px] text-hasr-muted">{{ l.item_code }}</p>
          <p class="text-[13px] text-hasr-muted">{{ __('Ordered {0}', [orderedText(l)]) }} · {{ lineHint(l) }}</p>
        </button>
        <button type="button" class="tabular flex shrink-0 items-center gap-1.5 self-center text-[17px] font-semibold" :class="qtyClass(l)" @click="openLine(l)">
          <LucideTriangleAlert v-if="isIssue(l)" class="size-5" />
          <LucideCheck v-else-if="isDone(l)" class="size-5" />
          <span class="ltr-text">{{ formatNumber(l.received_qty) }} / {{ formatNumber(l.pending_qty) }}</span>
        </button>
      </li>
      <li v-for="u in openUnknown" :key="u.name" class="flex items-center gap-3 border-b border-hasr-line bg-[#FFFAF0] px-4 py-3.5">
        <div class="flex size-12 shrink-0 items-center justify-center rounded-tile bg-hasr-warning-bg text-hasr-warning">
          <LucideScanBarcode class="size-6" />
        </div>
        <div class="min-w-0 flex-1">
          <p class="text-[17px]">{{ __('Unknown barcode') }}</p>
          <p class="truncate text-[14px] text-hasr-muted"><span class="ltr-text">{{ u.barcode }}</span> · {{ __('waiting for the supervisor') }}</p>
        </div>
        <span class="tabular text-[17px] font-semibold text-hasr-warning">{{ formatNumber(u.qty) }}</span>
      </li>
    </ul>

    <footer v-if="s" class="sticky bottom-0 space-y-3 bg-white px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-3">
      <ScanToast :toast="toast" @undo="undo" />
      <button
        v-if="s.editable"
        type="button"
        class="h-12 w-full rounded-hasr bg-hasr-ink text-[16px] font-medium text-white"
        @click="finishOpen = true"
      >
        {{ __('Finish shipment and send for review') }}
      </button>
    </footer>

    <LineSheet
      :line="activeLine"
      :session="s && s.name"
      :editable="s && s.editable"
      :expiry-warning-pct="s ? s.expiry_warning_pct : 0"
      @close="closeLine"
      @saved="onLineSaved"
      @details="(code) => router.push({ name: 'ItemDetails', params: { itemCode: code } })"
    />
    <UnknownBarcodeSheet :barcode="unknownBarcode" :session="s && s.name" @close="unknownBarcode = ''" @sent="onUnknownSent" />
    <CameraSheet v-model:open="cameraOpen" @scan="onScan" />
    <FinishSheet v-if="s" v-model:open="finishOpen" :session="s" @finished="onFinished" />
    <InvoiceSheet v-if="s" v-model:open="invoiceOpen" :session="s" />
    <ImageZoom v-model:open="zoomOpen" :src="zoomSrc" />
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import IconButton from '../components/IconButton.vue'
import Pill from '../components/Pill.vue'
import ItemThumb from '../components/ItemThumb.vue'
import ScanInput from '../components/ScanInput.vue'
import ScanToast from '../components/ScanToast.vue'
import LineSheet from '../components/LineSheet.vue'
import UnknownBarcodeSheet from '../components/UnknownBarcodeSheet.vue'
import CameraSheet from '../components/CameraSheet.vue'
import FinishSheet from '../components/FinishSheet.vue'
import InvoiceSheet from '../components/InvoiceSheet.vue'
import LastScanCard from '../components/LastScanCard.vue'
import ImageZoom from '../components/ImageZoom.vue'
import { barcodeRows, orderedText } from '../uom'
import { api, deviceId, errorMessage, uuid4 } from '../api'
import { __, formatNumber } from '../i18n'
import { feedbackError, feedbackSuccess } from '../sound'

const props = defineProps({ session: String, poItem: String })
const route = useRoute()
const router = useRouter()

const s = ref(null)
const loadError = ref('')
const filter = ref('all')
const toast = ref(null)
const unknownBarcode = ref('')
const cameraOpen = ref(false)
const finishOpen = ref(false)
const invoiceOpen = ref(false)
const zoomOpen = ref(false)
const zoomSrc = ref('')
const lastScan = ref(null)
const rowEls = {}
const lastLine = computed(() => (lastScan.value && s.value ? s.value.lines.find((l) => l.po_item === lastScan.value.po_item) : null))

function zoom(src) {
  if (!src) return
  zoomSrc.value = src
  zoomOpen.value = true
}
const online = ref(navigator.onLine)
const busy = ref(false)
let toastTimer = null

const activeLine = computed(() => (s.value && props.poItem ? s.value.lines.find((l) => l.po_item === props.poItem) : null))
const sheetOpen = computed(
  () => !!(activeLine.value || unknownBarcode.value || cameraOpen.value || finishOpen.value || invoiceOpen.value || zoomOpen.value),
)
const openUnknown = computed(() => (s.value ? s.value.unknown_barcodes.filter((u) => u.status === 'Open') : []))

const isOver = (l) => l.over_allowance_state === 'Over' || l.over_allowance_state === 'Accepted'
const isDone = (l) => l.received_qty + l.rejected_qty >= l.pending_qty
const isIssue = (l) => isOver(l) || l.needs_expiry
const counts = computed(() => {
  const lines = s.value ? s.value.lines : []
  const done = lines.filter((l) => isDone(l) && !isIssue(l)).length
  const issues = lines.filter(isIssue).length + openUnknown.value.length
  return { all: lines.length, done, open: lines.filter((l) => !isDone(l)).length, issues }
})
const percent = computed(() => (counts.value.all ? Math.round((counts.value.done / counts.value.all) * 100) : 0))
const filters = computed(() => {
  const list = [
    { value: 'all', label: __('All'), count: counts.value.all },
    { value: 'open', label: __('Open'), count: counts.value.open },
    { value: 'done', label: __('Done'), count: counts.value.done },
  ]
  if (counts.value.issues) list.push({ value: 'issues', label: __('Issues'), count: counts.value.issues, warn: true })
  return list
})
const shownLines = computed(() => {
  const lines = s.value ? s.value.lines : []
  if (filter.value === 'open') return lines.filter((l) => !isDone(l))
  if (filter.value === 'done') return lines.filter((l) => isDone(l) && !isIssue(l))
  if (filter.value === 'issues') return lines.filter(isIssue)
  // problems first, then lines still to do, then complete ones
  const rank = (l) => (isIssue(l) ? 0 : isDone(l) ? 2 : 1)
  return [...lines].sort((a, b) => rank(a) - rank(b) || a.idx - b.idx)
})
const statusTheme = computed(() => ({ 'Pending Approval': 'orange', Approved: 'green', 'Sent Back': 'red' })[s.value.status] || 'gray')

function filterClass(f) {
  if (filter.value === f.value) return 'bg-hasr-ink text-white'
  return f.warn ? 'bg-hasr-warning-bg text-hasr-warning' : 'bg-hasr-surface2 text-hasr-secondary'
}

function lineHint(l) {
  if (isOver(l)) {
    const over = l.already_received_qty + l.received_qty + l.rejected_qty - l.allowed_qty
    return __('{0} over the limit', [formatNumber(Math.ceil(over))])
  }
  if (l.needs_expiry) return __('expiry date needed')
  if (l.rejected_qty) return __('{0} rejected', [formatNumber(l.rejected_qty)])
  if (!l.received_qty) return __('not scanned')
  const left = l.pending_qty - l.received_qty - l.rejected_qty
  return left > 0 ? __('{0} to go', [formatNumber(left)]) : __('complete')
}

function qtyClass(l) {
  if (isIssue(l)) return 'text-hasr-warning'
  if (isDone(l)) return 'text-hasr-success'
  return l.received_qty ? 'text-hasr-ink' : 'text-hasr-muted'
}

async function load() {
  try {
    s.value = await api('receiving.get_session', { name: props.session })
    loadError.value = ''
  } catch (e) {
    loadError.value = errorMessage(e)
  }
}

function mergeLines(lines) {
  if (!s.value || !lines) return
  const byItem = Object.fromEntries(lines.map((l) => [l.po_item, l]))
  s.value.lines = s.value.lines.map((l) => byItem[l.po_item] || l)
}

function showToast(t) {
  toast.value = t
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toast.value = null), t.error ? 6000 : 8000)
}

async function push(scan) {
  const out = await api('sync.push_scans', { scans: [scan] })
  mergeLines(out.lines)
  return out.results[0]
}

async function onScan(code) {
  if (!s.value || !s.value.editable || busy.value) return
  busy.value = true
  try {
    const r = await push({
      client_uuid: uuid4(),
      session: s.value.name,
      session_type: 'Receiving',
      barcode: code,
      qty: 1,
      scanned_at: new Date().toISOString(),
      device_id: deviceId(),
    })
    if (r.status === 'applied') {
      feedbackSuccess()
      const line = s.value.lines.find((l) => l.po_item === r.po_item)
      const isCase = r.conversion_factor !== 1
      showToast({
        title: isCase
          ? __('Added 1 {0} of {1}', [__(r.uom), r.item_name])
          : __('Added {0}', [r.item_name]),
        subtitle: isCase
          ? __('1 {0} = {1} {2}', [__(r.uom), formatNumber(r.conversion_factor), __(line ? line.stock_uom : '')])
          : __('{0} of {1}', [formatNumber(r.received_qty), formatNumber(line ? line.pending_qty : 0)]),
        undo: r.client_uuid,
      })
      if (line && isOver(line)) feedbackError()
      lastScan.value = { po_item: r.po_item, barcode: code, uom: r.uom, conversion_factor: r.conversion_factor }
      await nextTick()
      rowEls[r.po_item]?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    } else if (r.code === 'unknown_barcode') {
      feedbackError()
      unknownBarcode.value = code
    } else if (r.status === 'rejected') {
      feedbackError()
      showToast({ title: r.message, error: true })
    }
  } catch (e) {
    feedbackError()
    showToast({ title: errorMessage(e), error: true })
  } finally {
    busy.value = false
  }
}

async function undo(t) {
  try {
    const r = await push({ client_uuid: uuid4(), session: s.value.name, session_type: 'Receiving', undo_of: t.undo, device_id: deviceId() })
    showToast({ title: r.status === 'applied' ? __('Scan undone') : r.message, error: r.status !== 'applied' })
  } catch (e) {
    showToast({ title: errorMessage(e), error: true })
  }
}

function openLine(l) {
  router.push({ name: 'ReceiveLine', params: { session: props.session, poItem: l.po_item } })
}

function closeLine() {
  if (route.name === 'ReceiveLine') router.replace({ name: 'Receive', params: { session: props.session } })
}

function onLineSaved(session) {
  s.value = session
  feedbackSuccess()
  closeLine()
}

async function onUnknownSent() {
  unknownBarcode.value = ''
  showToast({ title: __('Sent to the supervisor') })
  await load()
}

function onFinished(session) {
  s.value = session
  finishOpen.value = false
  showToast({ title: __('Sent for review') })
}

const setOnline = () => (online.value = navigator.onLine)
watch(() => props.session, load)
onMounted(() => {
  window.addEventListener('online', setOnline)
  window.addEventListener('offline', setOnline)
  load()
})
onBeforeUnmount(() => {
  window.removeEventListener('online', setOnline)
  window.removeEventListener('offline', setOnline)
  clearTimeout(toastTimer)
})
</script>
