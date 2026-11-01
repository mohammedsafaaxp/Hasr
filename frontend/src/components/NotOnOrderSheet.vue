<template>
  <Sheet :open="!!item" :label="__('Not on this purchase order')" @update:open="!$event && $emit('close')">
    <div v-if="item" class="space-y-4 pb-2">
      <div class="flex items-start gap-3 rounded-tile bg-hasr-danger-bg p-4 text-hasr-danger" role="alert">
        <LucideCircleX class="mt-0.5 size-6 shrink-0" />
        <div class="min-w-0 flex-1 space-y-1">
          <h2 class="text-lg font-semibold leading-tight">{{ __('Wrong item: not on this purchase order') }}</h2>
          <p class="text-sm">{{ item.message }}</p>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <button type="button" class="shrink-0" :aria-label="__('Enlarge photo')" @click="zoomOpen = !!item.image">
          <ItemThumb :src="item.image" :size="80" />
        </button>
        <div class="min-w-0 flex-1">
          <p class="text-[17px] font-semibold leading-tight" dir="auto">{{ item.item_name }}</p>
          <p class="text-sm text-hasr-muted"><span class="ltr-text">{{ item.item_code }}</span></p>
          <p v-if="item.barcode" class="ltr-text tabular text-sm">{{ item.barcode }}</p>
        </div>
      </div>

      <p class="text-[15px] text-hasr-secondary">{{ __('Put it aside. If it came with the shipment, report it so the supervisor decides.') }}</p>

      <div v-if="reporting" class="space-y-3 rounded-tile border border-hasr-line p-3">
        <p class="text-[15px] font-medium">{{ __('How many arrived?') }}</p>
        <div class="flex items-center gap-2">
          <button type="button" class="size-12 rounded-hasr bg-hasr-surface2 text-2xl" :aria-label="__('Less')" @click="qty = Math.max(1, qty - 1)">−</button>
          <input
            v-model.number="qty"
            type="number"
            min="1"
            inputmode="numeric"
            class="tabular h-12 min-w-0 flex-1 rounded-hasr border-0 bg-hasr-surface2 text-center text-xl font-semibold"
            :aria-label="__('Qty')"
          />
          <button type="button" class="size-12 rounded-hasr bg-hasr-surface2 text-2xl" :aria-label="__('More')" @click="qty += 1">+</button>
          <span class="shrink-0 text-[15px]">{{ __(item.uom) }}</span>
        </div>
        <button
          type="button"
          class="h-12 w-full rounded-hasr bg-hasr-ink text-[16px] font-medium text-white disabled:opacity-50"
          :disabled="!(qty > 0)"
          @click="$emit('report', qty)"
        >
          {{ __('Send to the supervisor') }}
        </button>
      </div>

      <div v-else class="flex gap-2">
        <button type="button" class="h-12 flex-1 rounded-hasr bg-hasr-ink text-[16px] font-medium text-white" @click="$emit('close')">
          {{ __('OK, put it aside') }}
        </button>
        <button type="button" class="h-12 rounded-hasr bg-hasr-surface2 px-4 text-[15px] font-medium" @click="reporting = true">
          {{ __('Report to the supervisor') }}
        </button>
      </div>
    </div>
    <ImageZoom v-model:open="zoomOpen" :src="item && item.image" />
  </Sheet>
</template>

<script setup>
import { ref, watch } from 'vue'
import Sheet from './Sheet.vue'
import ItemThumb from './ItemThumb.vue'
import ImageZoom from './ImageZoom.vue'

// A scanned item that has no line on this order: refused clearly, and only recorded if the worker reports it.
const props = defineProps({ item: Object })
defineEmits(['close', 'report'])
const reporting = ref(false)
const qty = ref(1)
const zoomOpen = ref(false)

watch(
  () => props.item,
  (item) => {
    reporting.value = false
    qty.value = Math.max(1, Number(item?.qty) || 1)
  },
)
</script>
