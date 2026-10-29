<template>
  <Sheet :open="open" :label="__('Supplier invoice')" @update:open="$emit('update:open', $event)">
    <div class="space-y-4 pb-2">
      <div class="flex items-start gap-3">
        <div class="min-w-0 flex-1">
          <h2 class="text-lg font-semibold">{{ __('Supplier invoice') }}</h2>
          <p class="text-sm text-hasr-muted">{{ __('Photograph every page so the supervisor can check the receipt against it') }}</p>
        </div>
        <IconButton :label="__('Close')" @click="$emit('update:open', false)"><LucideX class="size-5" /></IconButton>
      </div>
      <InvoiceFiles :session="session.name" :files="session.invoices" :editable="session.editable" @update:files="session.invoices = $event" />
      <button type="button" class="h-11 w-full rounded-hasr bg-hasr-surface2 text-[15px] font-medium" @click="$emit('update:open', false)">
        {{ __('Close') }}
      </button>
    </div>
  </Sheet>
</template>

<script setup>
import Sheet from './Sheet.vue'
import IconButton from './IconButton.vue'
import InvoiceFiles from './InvoiceFiles.vue'

defineProps({ open: Boolean, session: Object })
defineEmits(['update:open'])
</script>
