<template>
  <Sheet :open="!!line" :label="__('The product does not match')" @update:open="!$event && $emit('close')">
    <div v-if="line" class="space-y-4 pb-2">
      <div class="flex items-start gap-3">
        <div class="flex size-11 shrink-0 items-center justify-center rounded-full bg-hasr-warning-bg text-hasr-warning">
          <LucideScanSearch class="size-5" />
        </div>
        <div class="min-w-0 flex-1">
          <h2 class="text-lg font-semibold">{{ __('The product does not match') }}</h2>
          <p class="text-sm text-hasr-muted">{{ __('Photograph what you received. The supervisor compares it with the item and decides.') }}</p>
        </div>
        <IconButton :label="__('Close')" @click="$emit('close')"><LucideX class="size-5" /></IconButton>
      </div>

      <div class="grid grid-cols-2 gap-3">
        <div class="space-y-1">
          <p class="text-[13px] text-hasr-muted">{{ __('Expected item') }}</p>
          <div class="flex aspect-square items-center justify-center overflow-hidden rounded-tile bg-hasr-surface2">
            <img v-if="line.image" :src="line.image" alt="" class="h-full w-full object-contain" />
            <LucidePackage v-else class="size-10 text-hasr-muted" />
          </div>
          <p class="text-[14px] leading-snug" dir="auto">{{ line.item_name }}</p>
          <p v-if="barcode" class="ltr-text tabular text-[13px] text-hasr-muted">{{ barcode }}</p>
        </div>
        <div class="space-y-1">
          <p class="text-[13px] text-hasr-muted">{{ __('What you received') }}</p>
          <label
            class="flex aspect-square cursor-pointer flex-col items-center justify-center gap-1 overflow-hidden rounded-tile border border-dashed border-gray-300 bg-gray-50 text-center"
          >
            <img v-if="photo" :src="photo" alt="" class="h-full w-full object-cover" />
            <template v-else>
              <LucideCamera class="size-7 text-hasr-secondary" />
              <span class="px-2 text-[13px]">{{ __('Take a photo of the product') }}</span>
            </template>
            <input type="file" accept="image/*" capture="environment" class="sr-only" @change="pick" />
          </label>
        </div>
      </div>

      <div class="flex gap-3">
        <label class="w-24 shrink-0 space-y-1">
          <span class="text-sm text-hasr-secondary">{{ __('Qty') }}</span>
          <input v-model.number="qty" type="number" min="1" inputmode="decimal" class="tabular h-11 w-full rounded-hasr border-0 bg-hasr-surface2 text-center" />
        </label>
        <label class="min-w-0 flex-1 space-y-1">
          <span class="text-sm text-hasr-secondary">{{ __('What is different?') }}</span>
          <input v-model="note" type="text" maxlength="500" class="h-11 w-full rounded-hasr border-0 bg-hasr-surface2 px-3" />
        </label>
      </div>
      <p class="text-[13px] text-hasr-muted">{{ __('Quantity in {0}. Keep scanning the rest normally.', [__(line.stock_uom)]) }}</p>

      <p v-if="error" class="rounded-hasr bg-hasr-danger-bg p-3 text-sm text-hasr-danger">{{ error }}</p>

      <div class="flex gap-3">
        <button
          type="button"
          class="h-11 flex-1 rounded-hasr bg-hasr-ink text-[15px] font-medium text-white disabled:opacity-50"
          :disabled="sending || !photo"
          @click="send"
        >
          {{ sending ? __('Sending…') : __('Send to supervisor') }}
        </button>
        <button type="button" class="h-11 rounded-hasr bg-hasr-surface2 px-5 text-[15px] font-medium" @click="$emit('close')">
          {{ __('Cancel') }}
        </button>
      </div>
    </div>
  </Sheet>
</template>

<script setup>
import { ref, watch } from 'vue'
import Sheet from './Sheet.vue'
import IconButton from './IconButton.vue'
import { api, errorMessage, uuid4 } from '../api'

const props = defineProps({ line: Object, session: String, barcode: String, defaultQty: Number })
const emit = defineEmits(['close', 'sent'])
const qty = ref(1)
const note = ref('')
const photo = ref('')
const error = ref('')
const sending = ref(false)
let clientUuid = ''

watch(
  () => props.line,
  (line) => {
    if (!line) return
    qty.value = props.defaultQty || 1
    note.value = ''
    photo.value = ''
    error.value = ''
    clientUuid = uuid4()
  },
)

function pick(event) {
  const file = event.target.files && event.target.files[0]
  event.target.value = ''
  if (!file) return
  const img = new Image()
  img.onload = () => {
    const scale = Math.min(1, 1600 / Math.max(img.width, img.height))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(img.width * scale)
    canvas.height = Math.round(img.height * scale)
    canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height)
    photo.value = canvas.toDataURL('image/jpeg', 0.85)
    URL.revokeObjectURL(img.src)
  }
  img.src = URL.createObjectURL(file)
}

async function send() {
  sending.value = true
  error.value = ''
  try {
    const session = await api('receiving.report_mismatch', {
      session: props.session,
      po_item: props.line.po_item,
      qty: qty.value,
      photo: photo.value,
      note: note.value,
      barcode: props.barcode || null,
      client_uuid: clientUuid,
    })
    emit('sent', session)
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    sending.value = false
  }
}
</script>
