<template>
  <Sheet :open="open" :label="__('Finish shipment {0}', [session.shipment_no])" @update:open="$emit('update:open', $event)">
    <div class="space-y-4 pb-2">
      <div class="flex items-start gap-3">
        <div class="min-w-0 flex-1">
          <h2 class="text-lg font-semibold">{{ __('Finish shipment {0}', [session.shipment_no]) }}</h2>
          <p class="text-sm text-hasr-muted">{{ __('The supervisor reviews it before anything changes in stock') }}</p>
        </div>
        <IconButton :label="__('Close')" @click="$emit('update:open', false)"><LucideX class="size-5" /></IconButton>
      </div>

      <div class="divide-y divide-hasr-line rounded-tile border border-hasr-line">
        <div class="flex justify-between p-3"><span>{{ __('Arrived in full') }}</span><b class="tabular text-hasr-success">{{ counts.full }}</b></div>
        <div class="flex justify-between p-3"><span>{{ __('Arrived in part') }}</span><b class="tabular">{{ counts.partial }}</b></div>
        <div class="flex justify-between p-3"><span>{{ __('Not in this shipment') }}</span><b class="tabular text-hasr-muted">{{ counts.none }}</b></div>
      </div>

      <template v-if="counts.partial || counts.none">
        <p class="text-sm text-hasr-secondary">{{ __('What about the rest?') }}</p>
        <label
          v-for="option in options"
          :key="option.value"
          class="flex cursor-pointer items-start gap-3 rounded-tile border p-3"
          :class="remaining === option.value ? 'border-hasr-ink border-[1.5px]' : 'border-hasr-line'"
        >
          <input v-model="remaining" type="radio" name="remaining" :value="option.value" class="mt-1 text-hasr-ink focus:ring-hasr-ink" />
          <span>
            <span class="block text-[15px]">{{ option.label }}</span>
            <span class="block text-[13px] text-hasr-muted">{{ option.help }}</span>
          </span>
        </label>
      </template>

      <label class="block space-y-1">
        <span class="text-sm text-hasr-secondary">{{ __('Supplier delivery note') }}</span>
        <input v-model="deliveryNote" type="text" maxlength="140" class="h-11 w-full rounded-hasr border-0 bg-hasr-surface2 px-3" />
      </label>

      <p v-if="error" class="rounded-hasr bg-hasr-danger-bg p-3 text-sm text-hasr-danger">{{ error }}</p>

      <div class="flex gap-3">
        <button
          type="button"
          class="h-11 flex-1 rounded-hasr bg-hasr-ink text-[15px] font-medium text-white disabled:opacity-50"
          :disabled="sending"
          @click="finish"
        >
          {{ sending ? __('Sending…') : __('Finish and send for review') }}
        </button>
        <button type="button" class="h-11 rounded-hasr bg-hasr-surface2 px-5 text-[15px] font-medium" @click="$emit('update:open', false)">
          {{ __('Back') }}
        </button>
      </div>
    </div>
  </Sheet>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import Sheet from './Sheet.vue'
import IconButton from './IconButton.vue'
import { api, errorMessage } from '../api'
import { __ } from '../i18n'

const props = defineProps({ open: Boolean, session: Object })
const emit = defineEmits(['update:open', 'finished'])
const remaining = ref('Still coming')
const deliveryNote = ref('')
const error = ref('')
const sending = ref(false)

const options = computed(() => [
  { value: 'Still coming', label: __('Keep it open for another shipment'), help: __('The rest stays on the same purchase order') },
  { value: 'Supplier will not send', label: __('The supplier will not send the rest'), help: __('The supervisor decides whether to close the order') },
])

const counts = computed(() => {
  const c = { full: 0, partial: 0, none: 0 }
  for (const l of props.session.lines) {
    const got = l.received_qty + l.rejected_qty
    if (got >= l.pending_qty) c.full++
    else if (got > 0) c.partial++
    else c.none++
  }
  return c
})

watch(
  () => props.open,
  (open) => {
    if (!open) return
    deliveryNote.value = props.session.supplier_delivery_note || ''
    remaining.value = props.session.remaining_expected || 'Still coming'
    error.value = ''
  },
)

async function finish() {
  sending.value = true
  error.value = ''
  try {
    const session = await api('receiving.finish_session', {
      session: props.session.name,
      supplier_delivery_note: deliveryNote.value,
      remaining_expected: counts.value.partial || counts.value.none ? remaining.value : null,
    })
    emit('finished', session)
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    sending.value = false
  }
}
</script>
