<template>
  <div class="flex gap-3 rounded-tile border border-hasr-line p-3" role="status" aria-live="polite">
    <button type="button" class="shrink-0" :aria-label="__('Photo')" @click="$emit('zoom', line.image)">
      <ItemThumb :src="line.image" :size="112" />
    </button>
    <div class="min-w-0 flex-1 space-y-1">
      <p class="text-[13px] text-hasr-muted">{{ __('Last scanned') }}</p>
      <p class="text-[17px] font-semibold leading-snug" dir="auto">{{ line.item_name }}</p>
      <p class="ltr-text tabular text-[15px] font-medium">{{ scan.barcode }}</p>
      <div class="flex flex-wrap gap-1.5">
        <Pill :theme="scan.conversion_factor !== 1 ? 'blue' : 'gray'">
          {{ scan.conversion_factor !== 1 ? conversionText(scan.uom, scan.conversion_factor, line.stock_uom) : __(scan.uom) }}
        </Pill>
        <Pill v-if="line.has_batch_no" :theme="line.needs_expiry ? 'orange' : 'green'">
          {{ line.needs_expiry ? __('Expiry date needed') : __('Expiry entered') }}
        </Pill>
      </div>
      <p class="tabular text-[15px]">
        <b>{{ formatNumber(line.received_qty) }}</b> / {{ formatNumber(line.pending_qty) }} {{ __(line.stock_uom) }}
      </p>
    </div>
  </div>
</template>

<script setup>
import ItemThumb from './ItemThumb.vue'
import Pill from './Pill.vue'
import { formatNumber } from '../i18n'
import { conversionText } from '../uom'

defineProps({ line: Object, scan: Object })
defineEmits(['zoom'])
</script>
