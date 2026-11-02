<template>
  <div class="flex min-h-full flex-col">
    <header class="flex items-center gap-3 px-4 pt-4">
      <IconButton :label="__('Back')" @click="back"><LucideChevronLeft class="size-5 rtl:-scale-x-100" /></IconButton>
      <h1 class="text-lg font-semibold">{{ __('Item details') }}</h1>
    </header>

    <p v-if="error" class="m-4 rounded-hasr bg-hasr-danger-bg p-3 text-sm text-hasr-danger">{{ error }}</p>

    <main v-if="item" class="flex-1 space-y-5 px-4 pb-6 pt-4">
      <!-- photo: a gallery when there are photos, a small placeholder next to the name when there are none -->
      <div v-if="item.images.length" class="relative aspect-[4/3] overflow-hidden rounded-tile bg-hasr-surface2">
        <div ref="strip" class="flex h-full snap-x snap-mandatory overflow-x-auto" @scroll.passive="onStripScroll">
          <img
            v-for="(url, i) in item.images"
            :key="url"
            :src="url"
            alt=""
            class="h-full w-full shrink-0 snap-center object-contain"
            @click="zoomAt(i)"
          />
        </div>
        <button
          type="button"
          class="absolute end-3 top-3 inline-flex h-10 items-center gap-1.5 rounded-full bg-white px-3.5 text-[14px] shadow-sm"
          @click="zoomAt(current)"
        >
          <LucideMaximize2 class="size-4" />{{ __('Zoom') }}
        </button>
        <div v-if="item.images.length > 1" class="absolute inset-x-0 bottom-3 flex justify-center gap-1.5">
          <span v-for="(url, i) in item.images" :key="url" class="size-1.5 rounded-full" :class="i === current ? 'bg-hasr-ink' : 'bg-gray-300'" />
        </div>
      </div>

      <div class="flex items-start gap-3">
        <div v-if="!item.images.length" class="flex size-20 shrink-0 flex-col items-center justify-center gap-1 rounded-tile bg-hasr-surface2 text-hasr-muted">
          <LucidePackage class="size-7" />
          <span class="text-[11px]">{{ __('No photo') }}</span>
        </div>
        <div class="min-w-0 flex-1 space-y-2">
          <h2 class="text-[22px] font-semibold leading-tight" dir="auto">{{ item.item_name }}</h2>
          <div class="flex flex-wrap gap-1.5">
            <Pill><span class="ltr-text">{{ item.item_code }}</span></Pill>
            <Pill v-if="item.brand">{{ item.brand }}</Pill>
            <Pill v-if="item.disabled" theme="red">{{ __('Disabled') }}</Pill>
          </div>
        </div>
      </div>
      <p v-if="item.description && item.description !== item.item_name" class="text-[15px] leading-relaxed text-hasr-secondary" dir="auto">
        {{ item.description }}
      </p>

      <!-- what the worker checks while receiving: which barcode counts what -->
      <section class="space-y-2">
        <h3 class="text-[13px] font-medium text-hasr-muted">{{ __('Barcodes and units') }}</h3>
        <ul class="divide-y divide-hasr-line rounded-tile border border-hasr-line">
          <li v-for="b in barcodeRows" :key="b.barcode" class="flex items-center justify-between gap-3 px-3 py-2.5">
            <span class="ltr-text tabular text-[17px] font-medium tracking-wide">{{ b.barcode }}</span>
            <span class="shrink-0 rounded-hasr bg-hasr-surface2 px-2 py-0.5 text-[13px] text-hasr-secondary">{{ b.unit }}</span>
          </li>
          <li v-if="!barcodeRows.length" class="px-3 py-2.5 text-[15px] text-hasr-muted">{{ __('No barcode in ERPNext yet') }}</li>
          <li v-for="u in unitsWithoutBarcode" :key="u.uom" class="flex items-center justify-between gap-3 px-3 py-2.5 text-[15px]">
            <span class="text-hasr-muted">{{ __('No barcode') }}</span>
            <span class="shrink-0 rounded-hasr bg-hasr-surface2 px-2 py-0.5 text-[13px] text-hasr-secondary">{{ unitText(u.uom) }}</span>
          </li>
        </ul>
      </section>

      <section class="space-y-2">
        <h3 class="text-[13px] font-medium text-hasr-muted">{{ __('Storage and expiry') }}</h3>
        <div class="grid grid-cols-2 gap-2">
          <div v-for="f in facts" :key="f.label" class="rounded-tile bg-hasr-surface2 p-3">
            <p class="text-[12px] text-hasr-muted">{{ f.label }}</p>
            <p class="text-[16px] font-medium" :class="f.cls" dir="auto">{{ f.value }}</p>
          </div>
        </div>
      </section>

      <section v-if="more.length" class="space-y-2">
        <h3 class="text-[13px] font-medium text-hasr-muted">{{ __('More') }}</h3>
        <dl class="divide-y divide-hasr-line rounded-tile border border-hasr-line text-[15px]">
          <div v-for="row in more" :key="row.label" class="flex justify-between gap-4 px-3 py-2.5">
            <dt class="shrink-0 text-hasr-muted">{{ row.label }}</dt>
            <dd class="text-end" dir="auto">{{ row.value }}</dd>
          </div>
        </dl>
      </section>

      <button type="button" class="h-12 w-full rounded-hasr bg-hasr-surface2 text-[15px] font-medium" @click="back">{{ __('Back to line') }}</button>
    </main>

    <ImageZoom v-model:open="zoomOpen" :src="item && item.images[current]" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import IconButton from '../components/IconButton.vue'
import Pill from '../components/Pill.vue'
import ImageZoom from '../components/ImageZoom.vue'
import { api, errorMessage } from '../api'
import { __, formatDate, formatNumber } from '../i18n'

const props = defineProps({ itemCode: String })
const router = useRouter()
const item = ref(null)
const error = ref('')
const current = ref(0)
const zoomOpen = ref(false)
const strip = ref(null)

function unitText(uom) {
  const i = item.value
  if (!uom || uom === i.stock_uom) return __(i.stock_uom)
  const cf = i.uoms.find((u) => u.uom === uom)?.conversion_factor
  return cf ? __('1 {0} = {1} {2}', [__(uom), formatNumber(cf), __(i.stock_uom)]) : __(uom)
}

const barcodeRows = computed(() => item.value.barcodes.map((b) => ({ barcode: b.barcode, unit: unitText(b.uom || item.value.stock_uom) })))
// units the item has that no barcode counts, so the worker knows them too
const unitsWithoutBarcode = computed(() => {
  const i = item.value
  const used = new Set(i.barcodes.map((b) => b.uom || i.stock_uom))
  return i.uoms.filter((u) => !used.has(u.uom))
})

const facts = computed(() => {
  const i = item.value
  const storage = { Ambient: 'text-hasr-ink', Chilled: 'text-hasr-success', Frozen: 'text-hasr-info' }
  return [
    { label: __('Shelf life'), value: i.shelf_life_in_days ? __('{0} days', [i.shelf_life_in_days]) : __('Not set') },
    { label: __('Storage'), value: i.hasr_storage ? __(i.hasr_storage) : __('Not set'), cls: storage[i.hasr_storage] },
    { label: __('Expiry date at receipt'), value: i.has_batch_no ? __('Required') : __('Not needed'), cls: i.has_batch_no ? 'text-hasr-warning' : '' },
    {
      label: __('Last received'),
      value: i.last_receipt ? `${formatDate(i.last_receipt.posting_date)} · ${formatNumber(i.last_receipt.stock_qty)} ${__(i.stock_uom)}` : __('Never'),
    },
  ]
})

const more = computed(() => {
  const i = item.value
  return [
    { label: __('Item group'), value: (i.item_group_path.length ? i.item_group_path : [i.item_group]).filter(Boolean).join(' › ') },
    { label: __('Weight'), value: i.weight_per_unit ? `${formatNumber(i.weight_per_unit)} ${__(i.weight_uom || '')}` : '' },
  ].filter((r) => r.value)
})

function back() {
  if (window.history.length > 1) router.back()
  else router.push({ name: 'Home' })
}

function zoomAt(i) {
  current.value = i
  zoomOpen.value = true
}

function onStripScroll() {
  const el = strip.value
  if (el) current.value = Math.round(Math.abs(el.scrollLeft) / el.clientWidth)
}

onMounted(async () => {
  try {
    item.value = await api('items.get_item_details', { item_code: props.itemCode })
  } catch (e) {
    error.value = errorMessage(e)
  }
})
</script>
