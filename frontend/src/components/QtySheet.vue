<template>
  <Sheet :open="!!barcode" :label="__('How many?')" @update:open="!$event && $emit('close')">
    <form v-if="barcode" class="space-y-4 pb-2" @submit.prevent="confirm">
      <div class="flex items-start gap-3">
        <ItemThumb :src="line && line.image" :size="72" />
        <div class="min-w-0 flex-1">
          <p class="text-[17px] font-semibold leading-snug" dir="auto">{{ info ? info.item_name : __('Barcode') }}</p>
          <p class="ltr-text tabular text-[14px] text-hasr-muted">{{ barcode }}</p>
          <p v-if="info && info.conversion_factor !== 1" class="text-[13px] text-hasr-info">
            {{ conversionText(info.uom, info.conversion_factor, info.stock_uom) }}
          </p>
        </div>
        <IconButton :label="__('Close')" @click="$emit('close')"><LucideX class="size-5" /></IconButton>
      </div>
      <label class="block space-y-1">
        <span class="text-sm text-hasr-secondary">{{ info ? __('How many {0}?', [__(info.uom)]) : __('How many?') }}</span>
        <input
          ref="input"
          v-model.number="qty"
          type="number"
          min="1"
          inputmode="decimal"
          enterkeyhint="done"
          class="tabular h-14 w-full rounded-hasr border border-hasr-line text-center text-3xl font-semibold focus:border-hasr-ink focus:ring-0"
        />
      </label>
      <p v-if="info && qty > 0 && info.conversion_factor !== 1" class="tabular text-sm text-hasr-muted">
        = {{ formatNumber(qty * info.conversion_factor) }} {{ __(info.stock_uom) }}
      </p>
      <button type="submit" class="h-12 w-full rounded-hasr bg-hasr-ink text-[15px] font-medium text-white disabled:opacity-50" :disabled="!(qty > 0)">
        {{ __('Add') }}
      </button>
    </form>
  </Sheet>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import Sheet from './Sheet.vue'
import IconButton from './IconButton.vue'
import ItemThumb from './ItemThumb.vue'
import { api } from '../api'
import { formatNumber } from '../i18n'
import { conversionText } from '../uom'

// "Scan once, type the quantity": the barcode tells the item and unit, the worker types how many.
const props = defineProps({ barcode: String, lines: Array })
const emit = defineEmits(['close', 'confirm'])
const qty = ref(null)
const info = ref(null)
const input = ref(null)
const line = computed(() => (info.value && props.lines ? props.lines.find((l) => l.item_code === info.value.item_code) : null))

watch(
  () => props.barcode,
  async (code) => {
    qty.value = null
    info.value = null
    if (!code) return
    await nextTick()
    input.value?.focus()
    // best effort: without a connection the worker still types the quantity
    const r = await api('items.resolve_barcode', { code }).catch(() => null)
    if (r && r.found && props.barcode === code) info.value = r
  },
)

function confirm() {
  if (qty.value > 0) emit('confirm', { barcode: props.barcode, qty: qty.value })
}
</script>
