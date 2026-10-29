<template>
  <div class="space-y-2">
    <div class="flex items-center justify-between">
      <p class="text-sm text-hasr-secondary">{{ __('Supplier invoice') }}</p>
      <p class="text-[13px] text-hasr-muted">{{ __('Goes with the Purchase Receipt') }}</p>
    </div>
    <div class="flex flex-wrap gap-2">
      <div v-for="f in files" :key="f.name" class="relative">
        <a :href="f.file_url" target="_blank" class="block size-20 overflow-hidden rounded-tile border border-hasr-line bg-hasr-surface2">
          <img v-if="!isPdf(f)" :src="f.file_url" alt="" class="h-full w-full object-cover" />
          <span v-else class="flex h-full flex-col items-center justify-center gap-1 text-hasr-secondary">
            <LucideFileText class="size-7" /><span class="text-[11px]">PDF</span>
          </span>
        </a>
        <button
          v-if="editable"
          type="button"
          class="absolute -end-2 -top-2 flex size-7 items-center justify-center rounded-full bg-hasr-ink text-white"
          :aria-label="__('Remove')"
          @click="remove(f)"
        >
          <LucideX class="size-4" />
        </button>
      </div>
      <template v-if="editable">
        <label class="flex size-20 cursor-pointer flex-col items-center justify-center gap-1 rounded-tile border border-dashed border-gray-300 bg-gray-50 text-center text-[12px]">
          <LucideCamera class="size-6 text-hasr-secondary" />{{ __('Photo') }}
          <input type="file" accept="image/*" capture="environment" class="sr-only" @change="pick" />
        </label>
        <label class="flex size-20 cursor-pointer flex-col items-center justify-center gap-1 rounded-tile border border-dashed border-gray-300 bg-gray-50 text-center text-[12px]">
          <LucideUpload class="size-6 text-hasr-secondary" />{{ __('File') }}
          <input type="file" accept="image/*,application/pdf" class="sr-only" @change="pick" />
        </label>
      </template>
    </div>
    <p v-if="busy" class="text-sm text-hasr-muted">{{ __('Uploading…') }}</p>
    <p v-if="error" class="rounded-hasr bg-hasr-danger-bg p-3 text-sm text-hasr-danger">{{ error }}</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { api, errorMessage } from '../api'
import { __ } from '../i18n'

const props = defineProps({ session: String, files: Array, editable: Boolean })
const emit = defineEmits(['update:files'])
const busy = ref(false)
const error = ref('')
const MAX_BYTES = 10 * 1024 * 1024

const isPdf = (f) => /\.pdf$/i.test(f.file_name || f.file_url)

function readAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

// invoices must stay readable: keep up to 2000px, which is still far below the upload limit
function shrinkImage(file) {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      const scale = Math.min(1, 2000 / Math.max(img.width, img.height))
      const canvas = document.createElement('canvas')
      canvas.width = Math.round(img.width * scale)
      canvas.height = Math.round(img.height * scale)
      canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height)
      URL.revokeObjectURL(img.src)
      resolve(canvas.toDataURL('image/jpeg', 0.85))
    }
    img.onerror = reject
    img.src = URL.createObjectURL(file)
  })
}

async function pick(event) {
  const file = event.target.files && event.target.files[0]
  event.target.value = ''
  if (!file) return
  error.value = ''
  if (file.type !== 'application/pdf' && !file.type.startsWith('image/')) {
    error.value = __('The invoice must be a photo (JPEG, PNG, WebP) or a PDF.')
    return
  }
  if (file.type === 'application/pdf' && file.size > MAX_BYTES) {
    error.value = __('The invoice file is too large.')
    return
  }
  busy.value = true
  try {
    const dataUrl = file.type === 'application/pdf' ? await readAsDataUrl(file) : await shrinkImage(file)
    emit('update:files', await api('receiving.attach_invoice', { session: props.session, data_url: dataUrl }))
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}

async function remove(f) {
  error.value = ''
  try {
    emit('update:files', await api('receiving.remove_invoice', { session: props.session, file_name: f.name }))
  } catch (e) {
    error.value = errorMessage(e)
  }
}
</script>
