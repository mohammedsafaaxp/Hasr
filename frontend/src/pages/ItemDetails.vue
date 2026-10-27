<template>
  <div class="flex min-h-full flex-col">
    <header class="flex items-center gap-3 px-4 pt-4">
      <IconButton :label="__('Back')" @click="back"><LucideChevronLeft class="size-5 rtl:-scale-x-100" /></IconButton>
      <h1 class="text-lg font-semibold">{{ __('Item details') }}</h1>
    </header>

    <p v-if="error" class="m-4 rounded-hasr bg-hasr-danger-bg p-3 text-sm text-hasr-danger">{{ error }}</p>

    <main v-if="item" class="flex-1 space-y-4 px-4 pb-4 pt-4">
      <div class="relative aspect-[4/3] overflow-hidden rounded-tile bg-hasr-surface2">
        <div
          v-if="item.images.length"
          ref="strip"
          class="flex h-full snap-x snap-mandatory overflow-x-auto"
          @scroll.passive="onStripScroll"
        >
          <img
            v-for="(url, i) in item.images"
            :key="url"
            :src="url"
            alt=""
            class="h-full w-full shrink-0 snap-center object-contain"
            @click="zoomAt(i)"
          />
        </div>
        <div v-else class="flex h-full flex-col items-center justify-center gap-2 text-hasr-muted">
          <LucidePackage class="size-12" />
          <span class="text-sm">{{ __('No photo in ERPNext yet') }}</span>
        </div>
        <button
          v-if="item.images.length"
          type="button"
          class="absolute end-3 top-3 inline-flex h-11 items-center gap-1.5 rounded-full bg-white px-4 text-[15px] shadow-sm"
          @click="zoomAt(current)"
        >
          <LucideMaximize2 class="size-4" />{{ __('Zoom') }}
        </button>
        <div v-if="item.images.length > 1" class="absolute inset-x-0 bottom-3 flex justify-center gap-1.5">
          <span v-for="(url, i) in item.images" :key="url" class="size-1.5 rounded-full" :class="i === current ? 'bg-hasr-ink' : 'bg-gray-300'" />
        </div>
      </div>

      <div class="space-y-2">
        <h2 class="text-2xl font-semibold" dir="auto">{{ item.item_name }}</h2>
        <div class="flex flex-wrap gap-2">
          <Pill><span class="ltr-text">{{ item.item_code }}</span></Pill>
          <Pill v-if="item.has_batch_no" theme="blue">{{ __('Batch and expiry tracked') }}</Pill>
          <Pill v-if="item.hasr_storage" :theme="item.hasr_storage === 'Ambient' ? 'gray' : item.hasr_storage === 'Frozen' ? 'blue' : 'green'">
            {{ __(item.hasr_storage) }}
          </Pill>
          <Pill v-if="item.disabled" theme="red">{{ __('Disabled') }}</Pill>
        </div>
        <p v-if="item.description && item.description !== item.item_name" class="text-[15px] text-hasr-secondary" dir="auto">{{ item.description }}</p>
      </div>

      <dl class="divide-y divide-hasr-line rounded-tile border border-hasr-line text-[15px]">
        <div v-for="row in rows" :key="row.label" class="flex justify-between gap-4 p-3">
          <dt class="shrink-0 text-hasr-muted">{{ row.label }}</dt>
          <dd class="text-end">
            <div v-for="(v, i) in row.values" :key="i">{{ v }}</div>
          </dd>
        </div>
      </dl>
    </main>

    <footer class="sticky bottom-0 border-t border-hasr-line bg-white px-4 py-3">
      <button type="button" class="h-12 w-full rounded-hasr bg-hasr-surface2 text-[15px] font-medium" @click="back">{{ __('Back to line') }}</button>
    </footer>

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

const rows = computed(() => {
  const i = item.value
  const unit = (u) => __(u)
  const list = [
    { label: __('Item group'), values: [(i.item_group_path.length ? i.item_group_path : [i.item_group]).join(' › ')] },
    { label: __('Brand'), values: [i.brand || '—'] },
    {
      label: __('Units'),
      values: [
        [unit(i.stock_uom), ...i.uoms.filter((u) => u.uom !== i.stock_uom).map((u) => __('1 {0} = {1} {2}', [unit(u.uom), formatNumber(u.conversion_factor), unit(i.stock_uom)]))].join(' · '),
      ],
    },
    { label: __('Barcodes'), values: i.barcodes.length ? i.barcodes.map((b) => `${b.barcode} ${unit(b.uom || i.stock_uom)}`) : ['—'] },
    { label: __('Shelf life'), values: [i.shelf_life_in_days ? __('{0} days', [i.shelf_life_in_days]) : '—'] },
    { label: __('Weight'), values: [i.weight_per_unit ? `${formatNumber(i.weight_per_unit)} ${unit(i.weight_uom || '')}` : '—'] },
    {
      label: __('Last received'),
      values: [i.last_receipt ? `${formatDate(i.last_receipt.posting_date)} · ${formatNumber(i.last_receipt.stock_qty)} ${unit(i.stock_uom)}` : '—'],
    },
  ]
  return list
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
