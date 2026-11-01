<template>
  <Sheet :open="open" :label="__('Type item code')" @update:open="$emit('update:open', $event)">
    <div class="space-y-4 pb-2">
      <div class="flex items-start gap-3">
        <div class="min-w-0 flex-1">
          <h2 class="text-lg font-semibold">{{ __('Type item code') }}</h2>
          <p class="text-sm text-hasr-muted">{{ __('For a damaged or missing label. Choose the unit you are counting.') }}</p>
        </div>
        <IconButton :label="__('Close')" @click="$emit('update:open', false)"><LucideX class="size-5" /></IconButton>
      </div>

      <input
        ref="search"
        v-model="query"
        type="text"
        autocapitalize="characters"
        autocomplete="off"
        :placeholder="__('Item code or name')"
        class="h-11 w-full rounded-hasr border-0 bg-hasr-surface2 px-3"
      />
      <ul v-if="!picked" class="max-h-64 divide-y divide-hasr-line overflow-y-auto rounded-tile border border-hasr-line">
        <li v-for="l in matches" :key="l.po_item">
          <button type="button" class="flex w-full items-center gap-3 p-2 text-start" @click="pick(l)">
            <ItemThumb :src="l.image" :size="44" />
            <span class="min-w-0 flex-1">
              <span class="block truncate text-[15px]" dir="auto">{{ l.item_name }}</span>
              <span class="ltr-text block text-[13px] text-hasr-muted">{{ l.item_code }}</span>
            </span>
          </button>
        </li>
        <li v-if="!matches.length" class="p-3 text-sm text-hasr-muted">{{ __('No line on this order matches.') }}</li>
      </ul>

      <template v-if="picked">
        <div class="flex items-center gap-3 rounded-tile border border-hasr-ink p-2">
          <ItemThumb :src="picked.image" :size="56" />
          <div class="min-w-0 flex-1">
            <p class="text-[15px] font-medium" dir="auto">{{ picked.item_name }}</p>
            <p class="ltr-text text-[13px] text-hasr-muted">{{ picked.item_code }}</p>
          </div>
          <button type="button" class="text-sm text-hasr-info" @click="picked = null">{{ __('Change') }}</button>
        </div>
        <div class="space-y-1">
          <p class="text-sm text-hasr-secondary">{{ __('Unit') }}</p>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="u in picked.uoms"
              :key="u.uom"
              type="button"
              class="h-11 rounded-full px-4 text-[15px]"
              :class="uom === u.uom ? 'bg-hasr-ink text-white' : 'bg-hasr-surface2'"
              @click="uom = u.uom"
            >
              {{ u.conversion_factor === 1 ? __(u.uom) : `${__(u.uom)} ×${formatNumber(u.conversion_factor)}` }}
            </button>
          </div>
        </div>
        <label class="block space-y-1">
          <span class="text-sm text-hasr-secondary">{{ uom ? __('How many {0}?', [__(uom)]) : __('How many?') }}</span>
          <input v-model.number="qty" type="number" min="1" inputmode="decimal" class="tabular h-12 w-full rounded-hasr border border-hasr-line text-center text-2xl font-semibold" />
        </label>
        <button
          type="button"
          class="h-12 w-full rounded-hasr bg-hasr-ink text-[15px] font-medium text-white disabled:opacity-50"
          :disabled="!uom || !(qty > 0)"
          @click="$emit('confirm', { item_code: picked.item_code, uom, qty })"
        >
          {{ __('Add') }}
        </button>
      </template>
    </div>
  </Sheet>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import Sheet from './Sheet.vue'
import IconButton from './IconButton.vue'
import ItemThumb from './ItemThumb.vue'
import { formatNumber } from '../i18n'

const props = defineProps({ open: Boolean, lines: Array, itemCode: String })
const emit = defineEmits(['update:open', 'confirm'])
const query = ref('')
const picked = ref(null)
const uom = ref('')
const qty = ref(1)
const search = ref(null)

const matches = computed(() => {
  const q = query.value.trim().toLowerCase()
  const lines = props.lines || []
  if (!q) return lines
  return lines.filter((l) => l.item_code.toLowerCase().includes(q) || (l.item_name || '').toLowerCase().includes(q))
})

function pick(l) {
  picked.value = l
  uom.value = '' // the worker must say what they are counting
  qty.value = 1
}

watch(
  () => props.open,
  async (open) => {
    if (!open) return
    query.value = props.itemCode || ''
    picked.value = null
    uom.value = ''
    const exact = (props.lines || []).find((l) => l.item_code === props.itemCode)
    if (exact) pick(exact)
    await nextTick()
    search.value?.focus()
  },
)
</script>
