<template>
  <Sheet :open="!!barcode" :label="__('Unknown barcode')" @update:open="!$event && $emit('close')">
    <div v-if="barcode" class="space-y-4 pb-2">
      <div class="flex items-start gap-3">
        <div class="flex size-11 shrink-0 items-center justify-center rounded-full bg-hasr-warning-bg text-hasr-warning">
          <LucideScanBarcode class="size-5" />
        </div>
        <div class="min-w-0 flex-1">
          <h2 class="text-lg font-semibold">{{ __('Unknown barcode') }}</h2>
          <p class="ltr-text tabular text-[15px]">{{ barcode }}</p>
        </div>
        <IconButton :label="__('Close')" @click="$emit('close')"><LucideX class="size-5" /></IconButton>
      </div>
      <p class="text-[15px] text-hasr-secondary">
        {{ __('This barcode is not linked to any item. Take a photo and send it to the supervisor to link it. You can keep receiving the rest.') }}
      </p>

      <label
        class="flex cursor-pointer flex-col items-center justify-center gap-1 overflow-hidden rounded-tile border border-dashed border-gray-300 bg-gray-50 text-center"
        :class="photo ? 'h-48' : 'h-36'"
      >
        <img v-if="photo" :src="photo" alt="" class="h-full w-full object-contain" />
        <template v-else>
          <LucideCamera class="size-7 text-hasr-secondary" />
          <span class="text-[15px]">{{ __('Take a photo of the product') }}</span>
          <span class="text-[13px] text-hasr-muted">{{ __('One clear photo of the pack is enough') }}</span>
        </template>
        <input type="file" accept="image/*" capture="environment" class="sr-only" @change="pick" />
      </label>

      <div class="flex gap-3">
        <label class="w-24 shrink-0 space-y-1">
          <span class="text-sm text-hasr-secondary">{{ __('Qty') }}</span>
          <input v-model.number="qty" type="number" min="1" inputmode="decimal" class="tabular h-11 w-full rounded-hasr border-0 bg-hasr-surface2 text-center" />
        </label>
        <label class="min-w-0 flex-1 space-y-1">
          <span class="text-sm text-hasr-secondary">{{ __('Note for the supervisor') }}</span>
          <input v-model="note" type="text" maxlength="500" class="h-11 w-full rounded-hasr border-0 bg-hasr-surface2 px-3" />
        </label>
      </div>

      <p v-if="error" class="rounded-hasr bg-hasr-danger-bg p-3 text-sm text-hasr-danger">{{ error }}</p>

      <div class="flex gap-3">
        <button
          type="button"
          class="h-11 flex-1 rounded-hasr bg-hasr-ink text-[15px] font-medium text-white disabled:opacity-50"
          :disabled="sending"
          @click="send"
        >
          {{ sending ? __('Sending…') : __('Send to supervisor') }}
        </button>
        <button type="button" class="h-11 rounded-hasr bg-hasr-surface2 px-4 text-[15px] font-medium" @click="$emit('close')">
          {{ __('Scan again') }}
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

const props = defineProps({ barcode: String, session: String })
const emit = defineEmits(['close', 'sent'])
const qty = ref(1)
const note = ref('')
const photo = ref('')
const error = ref('')
const sending = ref(false)
let clientUuid = ''

watch(
  () => props.barcode,
  (code) => {
    if (!code) return
    qty.value = 1
    note.value = ''
    photo.value = ''
    error.value = ''
    clientUuid = uuid4()
  },
)

// shrink the camera photo before upload: 1280px JPEG is plenty for a supervisor to recognise a pack
function pick(event) {
  const file = event.target.files && event.target.files[0]
  if (!file) return
  const img = new Image()
  img.onload = () => {
    const scale = Math.min(1, 1280 / Math.max(img.width, img.height))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(img.width * scale)
    canvas.height = Math.round(img.height * scale)
    canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height)
    photo.value = canvas.toDataURL('image/jpeg', 0.82)
    URL.revokeObjectURL(img.src)
  }
  img.src = URL.createObjectURL(file)
}

async function send() {
  sending.value = true
  error.value = ''
  try {
    await api('receiving.report_unknown_barcode', {
      session: props.session,
      barcode: props.barcode,
      qty: qty.value || 1,
      note: note.value,
      photo: photo.value || null,
      client_uuid: clientUuid,
    })
    emit('sent')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    sending.value = false
  }
}
</script>
