<template>
  <div class="flex min-h-full flex-col">
    <header class="space-y-4 px-4 pt-4">
      <div class="flex items-start gap-3">
        <IconButton :label="__('Back')" @click="router.push({ name: 'Home', query: { tab: 'count' } })">
          <LucideChevronLeft class="size-5 rtl:-scale-x-100" />
        </IconButton>
        <div class="min-w-0 flex-1">
          <h1 class="truncate text-lg font-semibold">{{ c ? c.warehouse_name : '' }}</h1>
          <p v-if="c" class="text-[15px] text-hasr-muted">
            <span class="ltr-text">{{ c.name }}</span> ·
            {{ c.round === 'Recount' ? __('Recount') : __('Zone {0}', [c.zone]) }}
          </p>
        </div>
        <Pill v-if="queue && queue.pending.value.length" :theme="queue.offline.value || !online ? 'orange' : 'gray'">
          <LucideCloudOff v-if="queue.offline.value || !online" class="size-4" />
          <LucideLoader v-else class="size-4 animate-spin" />
          {{ __('{0} waiting', [queue.pending.value.length]) }}
        </Pill>
        <Pill v-else-if="!online" theme="orange"><LucideCloudOff class="size-4" />{{ __('Offline') }}</Pill>
      </div>

      <p v-if="loadError" class="rounded-hasr bg-hasr-danger-bg p-3 text-sm text-hasr-danger">{{ loadError }}</p>

      <template v-if="c">
        <div v-if="c.handed_over" class="flex items-center gap-2 rounded-hasr bg-hasr-info-bg p-3 text-sm text-hasr-info">
          <LucideCheck class="size-4" />{{ __('You handed over this zone. The supervisor reviews it.') }}
        </div>
        <div v-else-if="c.round === 'Recount'" class="rounded-hasr bg-hasr-warning-bg p-3 text-sm text-hasr-warning">
          <b>{{ __('Recount') }}</b>: {{ __('these items did not match. Count them again carefully; the earlier count is not shown.') }}
        </div>
        <p v-if="c.note" class="rounded-hasr bg-hasr-surface2 p-3 text-[15px]" dir="auto">{{ c.note }}</p>

        <ScanInput v-if="c.editable" :active="!sheetOpen" @scan="onScan" @camera="cameraOpen = true" @type="searchOpen = !searchOpen" />

        <label v-if="showList || searchOpen" class="flex h-11 items-center gap-2 rounded-hasr bg-hasr-surface2 px-3">
          <LucideSearch class="size-5 text-hasr-secondary" />
          <input
            v-model="search"
            type="search"
            :placeholder="__('Item code or name')"
            class="h-full w-full min-w-0 border-0 bg-transparent p-0 text-[15px] placeholder:text-hasr-muted focus:ring-0"
          />
        </label>

        <div class="flex justify-between text-[15px] text-hasr-secondary">
          <span>{{ showList ? __('{0} of {1} items counted', [countedItems.length, c.items.length]) : __('{0} items counted', [countedItems.length]) }}</span>
        </div>
      </template>
    </header>

    <ul v-if="c" class="mt-2 flex-1 border-t border-hasr-line">
      <li v-for="i in shownItems" :key="i.item_code">
        <button type="button" class="flex w-full items-center gap-3 border-b border-hasr-line px-4 py-3 text-start active:bg-hasr-surface2" @click="openItem(i)">
          <ItemThumb :src="i.image" :size="56" />
          <span class="min-w-0 flex-1">
            <span class="block text-[17px] leading-snug" dir="auto">{{ i.item_name }}</span>
            <span class="ltr-text block text-[14px] text-hasr-muted">{{ i.item_code }}</span>
          </span>
          <span v-if="totalOf(i) !== null" class="tabular flex items-center gap-1 text-[17px] font-semibold text-hasr-success">
            <LucideCheck class="size-5" />{{ formatNumber(totalOf(i)) }}
          </span>
          <span v-else class="text-[14px] text-hasr-muted">{{ __('not counted') }}</span>
        </button>
      </li>
      <li v-if="!shownItems.length" class="p-8 text-center text-[15px] text-hasr-muted">
        {{ showList || search ? __('No items match.') : __('Scan each item, then type how many are on the shelf.') }}
      </li>
    </ul>

    <footer v-if="c && c.editable && c.round === 'Count'" class="sticky bottom-0 space-y-3 bg-white px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-3">
      <ScanToast :toast="toast" />
      <button type="button" class="h-12 w-full rounded-hasr bg-hasr-ink text-[16px] font-medium text-white" @click="handOverOpen = true">
        {{ __('Finish zone and hand over') }}
      </button>
    </footer>
    <footer v-else-if="c" class="sticky bottom-0 bg-white px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-3">
      <ScanToast :toast="toast" />
    </footer>

    <CountSheet
      :item="activeItem"
      :entry="activeEntry"
      :counts="counts"
      :editable="!!(c && c.editable)"
      @close="activeItem = null"
      @save="onSave"
      @details="(code) => router.push({ name: 'ItemDetails', params: { itemCode: code } })"
    />
    <CameraSheet v-model:open="cameraOpen" @scan="onScan" />
    <Sheet v-model:open="handOverOpen" :label="__('Finish zone and hand over')">
      <div class="space-y-4 pb-2">
        <h2 class="text-lg font-semibold">{{ __('Finish zone {0}?', [c ? c.zone : '']) }}</h2>
        <p class="text-[15px] text-hasr-secondary">
          {{ __('You counted {0} items. After handing over you cannot change the counts; anything not counted is taken as not found.', [countedItems.length]) }}
        </p>
        <p v-if="handOverError" class="rounded-hasr bg-hasr-danger-bg p-3 text-sm text-hasr-danger">{{ handOverError }}</p>
        <button type="button" class="h-12 w-full rounded-hasr bg-hasr-ink text-[16px] font-medium text-white disabled:opacity-50" :disabled="handingOver" @click="handOver">
          {{ __('Hand over') }}
        </button>
        <button type="button" class="h-11 w-full rounded-hasr bg-hasr-surface2 text-[15px]" @click="handOverOpen = false">{{ __('Keep counting') }}</button>
      </div>
    </Sheet>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { useRouter } from 'vue-router'
import IconButton from '../components/IconButton.vue'
import Pill from '../components/Pill.vue'
import ItemThumb from '../components/ItemThumb.vue'
import ScanInput from '../components/ScanInput.vue'
import ScanToast from '../components/ScanToast.vue'
import CameraSheet from '../components/CameraSheet.vue'
import CountSheet from '../components/CountSheet.vue'
import Sheet from '../components/Sheet.vue'
import { api, errorMessage, isNetworkError, uuid4 } from '../api'
import { cachedApi, writeCache } from '../offline'
import { createScanQueue } from '../scanQueue'
import { gtinCandidates, parseGs1 } from '../gs1'
import { __, formatNumber } from '../i18n'
import { feedbackError, feedbackSuccess, feedbackWarning } from '../sound'

const props = defineProps({ session: String })
const router = useRouter()

const c = ref(null)
const loadError = ref('')
const search = ref('')
const searchOpen = ref(false)
const cameraOpen = ref(false)
const handOverOpen = ref(false)
const handingOver = ref(false)
const handOverError = ref('')
const activeItem = ref(null)
const activeEntry = ref(null)
const toast = ref(null)
const online = ref(navigator.onLine)
const queue = shallowRef(null)
let toastTimer = null

const sheetOpen = computed(() => !!(activeItem.value || cameraOpen.value || handOverOpen.value))
const showList = computed(() => c.value && (c.value.entry_method === 'List' || c.value.round === 'Recount'))

// what this person counted, "item|batch" → qty: the server's answer plus counts still waiting on the phone
const counts = computed(() => {
  const out = {}
  for (const e of c.value?.counts || []) out[`${e.item_code}|${e.batch_no || ''}`] = e.qty
  for (const q of queue.value?.pending.value || []) {
    if (q.method === 'counting.set_count') out[`${q.args.item_code}|${q.args.batch_no || ''}`] = q.args.qty
  }
  return out
})
const countedItems = computed(() => [...new Set(Object.keys(counts.value).map((k) => k.split('|')[0]))])

function totalOf(item) {
  const prefix = `${item.item_code}|`
  const keys = Object.keys(counts.value).filter((k) => k.startsWith(prefix))
  return keys.length ? keys.reduce((t, k) => t + counts.value[k], 0) : null
}

const shownItems = computed(() => {
  if (!c.value) return []
  const q = search.value.trim().toLowerCase()
  let items = c.value.items
  if (!showList.value && !q) {
    const done = countedItems.value
    items = items.filter((i) => done.includes(i.item_code)).sort((a, b) => done.indexOf(b.item_code) - done.indexOf(a.item_code))
  }
  if (q) items = items.filter((i) => i.item_code.toLowerCase().includes(q) || i.item_name.toLowerCase().includes(q))
  return items.slice(0, 300)
})

function showToast(t) {
  toast.value = t
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toast.value = null), t.error ? 6000 : 4000)
}

async function load() {
  try {
    c.value = (await cachedApi(`count_${props.session}`, 'counting.get_count', { name: props.session })).data
    loadError.value = ''
  } catch (e) {
    loadError.value = errorMessage(e)
  }
  if (!queue.value) {
    queue.value = createScanQueue(`count_${props.session}`, onQueueResult)
    queue.value.flush()
  }
}

function onQueueResult({ answer, error }, entry) {
  if (error) {
    feedbackError()
    showToast({ title: errorMessage(error), error: true })
    load()
    return
  }
  if (!c.value || !answer || answer.status === 'duplicate') return
  const rest = c.value.counts.filter((e) => !(e.item_code === answer.item_code && (e.batch_no || '') === (answer.batch_no || '')))
  c.value.counts = [...rest, { item_code: answer.item_code, batch_no: answer.batch_no, qty: answer.qty }]
}

/** The item a code belongs to, from what the phone has: a barcode (GS1 too) or the item code. */
function findLocal(code) {
  const gs1 = parseGs1(code)
  const codes = gs1 && gs1.gtin ? gtinCandidates(gs1.gtin) : [code]
  const upper = code.toUpperCase()
  for (const i of c.value.items) {
    const b = i.barcodes.find((x) => codes.includes(x.barcode))
    if (b || (!gs1 && i.item_code.toUpperCase() === upper)) {
      const batch = gs1 && gs1.batch ? i.batches.find((x) => x.batch_no === gs1.batch) : null
      return { item: i, entry: { uom: b ? b.uom || i.stock_uom : null, batch_no: batch ? batch.batch_no : null } }
    }
  }
  return null
}

async function onScan(code) {
  code = (code || '').trim()
  cameraOpen.value = false
  if (!code || !c.value || !c.value.editable) return
  let hit = findLocal(code)
  if (!hit) {
    let r
    try {
      r = await api('counting.identify', { session: c.value.name, code })
    } catch (e) {
      feedbackError()
      showToast({ title: isNetworkError(e) ? __('Not on this phone, and there is no connection to look it up.') : errorMessage(e), error: true })
      return
    }
    if (r.status !== 'item') {
      feedbackError()
      showToast({ title: r.message, error: true })
      return
    }
    let item = c.value.items.find((i) => i.item_code === r.item_code)
    if (!item && r.item) {
      item = r.item // found on the shelf during a whole-warehouse count
      c.value.items = [...c.value.items, item]
    }
    if (!item) return
    hit = { item, entry: { uom: r.uom, batch_no: r.batch_no } }
  }
  feedbackSuccess()
  openItem(hit.item, hit.entry)
}

function openItem(item, entry = null) {
  activeEntry.value = entry
  activeItem.value = item
}

function onSave({ item_code, batch_no, qty }) {
  activeItem.value = null
  const client_uuid = uuid4()
  queue.value.add({
    method: 'counting.set_count',
    client_uuid,
    args: { session: c.value.name, item_code, batch_no, qty, client_uuid, counted_at: new Date().toISOString() },
  })
  feedbackSuccess()
  const item = c.value.items.find((i) => i.item_code === item_code)
  showToast({ title: __('Counted {0}', [item ? item.item_name : item_code]), subtitle: `${formatNumber(qty)} ${__(item ? item.stock_uom : '')}` })
}

async function handOver() {
  if (queue.value.pending.value.length) {
    feedbackWarning()
    handOverError.value = __('Connect to the network; the zone can be handed over once all counts are sent.')
    if (navigator.onLine) queue.value.flush()
    return
  }
  handingOver.value = true
  handOverError.value = ''
  try {
    c.value = await api('counting.hand_over', { session: c.value.name })
    handOverOpen.value = false
    showToast({ title: __('Zone handed over') })
  } catch (e) {
    handOverError.value = errorMessage(e)
  } finally {
    handingOver.value = false
  }
}

const setOnline = () => {
  online.value = navigator.onLine
  if (online.value && queue.value) queue.value.flush()
}
watch(c, (v) => v && writeCache(`count_${v.name}`, v), { deep: true })
onMounted(() => {
  window.addEventListener('online', setOnline)
  window.addEventListener('offline', setOnline)
  load()
})
onBeforeUnmount(() => {
  window.removeEventListener('online', setOnline)
  window.removeEventListener('offline', setOnline)
  clearTimeout(toastTimer)
  if (queue.value) queue.value.stop()
})
</script>
