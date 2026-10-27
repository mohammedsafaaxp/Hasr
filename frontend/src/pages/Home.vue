<template>
  <div class="flex min-h-full flex-col">
    <header class="space-y-4 px-4 pt-5">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2.5">
          <AppLogo :size="36" />
          <span class="text-[26px] font-bold tracking-[-0.045em]">{{ lang === 'ar' ? 'حَصر' : 'hasr' }}</span>
        </div>
        <button
          type="button"
          class="flex size-11 items-center justify-center rounded-full bg-hasr-surface2 text-sm font-medium"
          :aria-label="__('Account')"
          @click="menuOpen = true"
        >
          {{ initials(session.fullName || session.user) }}
        </button>
      </div>

      <label class="inline-flex h-11 max-w-full items-center gap-2 rounded-hasr bg-hasr-surface2 px-3">
        <LucideWarehouse class="size-5 shrink-0 text-hasr-secondary" />
        <select v-model="warehouse" class="min-w-0 border-0 bg-transparent p-0 pe-7 text-[15px] focus:ring-0" :aria-label="__('Warehouse')">
          <option value="">{{ __('All warehouses') }}</option>
          <option v-for="w in warehouses" :key="w.name" :value="w.name">{{ w.warehouse_name }}</option>
        </select>
      </label>

      <TabButtons v-model="tab" :options="tabs" fluid class="w-full" />

      <label v-if="tab === 'receive'" class="flex h-11 items-center gap-2 rounded-hasr bg-hasr-surface2 px-3">
        <LucideSearch class="size-5 text-hasr-secondary" />
        <input
          v-model="search"
          type="search"
          :placeholder="__('Search by PO number or supplier')"
          class="h-full w-full min-w-0 border-0 bg-transparent p-0 text-[15px] placeholder:text-hasr-muted focus:ring-0"
        />
      </label>
    </header>

    <main v-if="tab === 'receive'" class="flex-1 pt-4">
      <div class="flex items-center justify-between border-b border-hasr-line px-4 pb-3 text-[15px] text-hasr-secondary">
        <span>{{ __('Waiting to be received') }}</span>
        <span class="tabular">{{ orders.length === 1 ? __('1 order') : __('{0} orders', [orders.length]) }}</span>
      </div>
      <p v-if="error" class="m-4 rounded-hasr bg-hasr-danger-bg p-3 text-sm text-hasr-danger">{{ error }}</p>
      <p v-else-if="loaded && !orders.length" class="p-8 text-center text-[15px] text-hasr-muted">{{ __('No purchase orders are waiting.') }}</p>
      <ul>
        <li v-for="o in orders" :key="o.name">
          <button
            type="button"
            class="flex w-full items-center gap-3 border-b border-hasr-line px-4 py-4 text-start active:bg-hasr-surface2 disabled:opacity-60"
            :disabled="opening === o.name"
            @click="open(o)"
          >
            <div class="min-w-0 flex-1 space-y-1">
              <div class="flex items-center justify-between gap-2">
                <span class="truncate text-[17px]" dir="auto">{{ o.supplier_name || o.supplier }}</span>
                <Pill :theme="badge(o).theme">{{ badge(o).label }}</Pill>
              </div>
              <p class="truncate text-[15px] text-hasr-muted">
                <span class="ltr-text">{{ o.name }}</span> · {{ o.item_count === 1 ? __('1 item') : __('{0} items', [o.item_count]) }}
                <template v-if="o.shipments"> · {{ __('shipment {0}', [o.shipments + (o.open_session ? 0 : 1)]) }}</template>
              </p>
            </div>
            <LucideChevronRight class="size-5 shrink-0 text-hasr-muted rtl:-scale-x-100" />
          </button>
        </li>
      </ul>
    </main>

    <main v-else class="flex flex-1 flex-col items-center justify-center gap-2 p-8 text-center">
      <LucideClipboardList class="size-8 text-hasr-muted" />
      <p class="text-[15px] font-medium">{{ __('Stock counts are coming in version 0.3') }}</p>
      <p class="text-sm text-hasr-muted">{{ __('For now hasr receives purchase orders.') }}</p>
    </main>

    <footer class="sticky bottom-0 flex items-center justify-between border-t border-hasr-line bg-white px-4 py-3">
      <span class="flex items-center gap-2 text-[15px] text-hasr-secondary">
        <span class="size-2.5 rounded-full" :class="online ? 'bg-green-600' : 'bg-hasr-warning'" />
        {{ online ? __('Online · {0}', [syncedAt]) : __('Offline') }}
      </span>
      <IconButton :label="__('Refresh')" @click="load"><LucideRefreshCw class="size-5" :class="loading ? 'animate-spin' : ''" /></IconButton>
    </footer>

    <Sheet v-model:open="menuOpen" :label="__('Account')">
      <div class="space-y-3 pb-2">
        <p class="text-[15px] font-medium">{{ session.fullName || session.user }}</p>
        <p class="text-sm text-hasr-muted">{{ session.user }}</p>
        <LanguageSelect class="w-full" />
        <a href="/app/hasr-receiving-session" class="flex h-11 items-center rounded-hasr bg-hasr-surface2 px-3 text-[15px]">{{ __('Open Desk') }}</a>
        <button type="button" class="h-11 w-full rounded-hasr bg-hasr-surface2 text-[15px] text-hasr-danger" @click="logout">{{ __('Sign out') }}</button>
      </div>
    </Sheet>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { TabButtons } from 'frappe-ui'
import AppLogo from '../components/AppLogo.vue'
import Pill from '../components/Pill.vue'
import IconButton from '../components/IconButton.vue'
import Sheet from '../components/Sheet.vue'
import LanguageSelect from '../components/LanguageSelect.vue'
import { api, errorMessage } from '../api'
import { __, formatTime, lang } from '../i18n'
import { initials, logout, session } from '../session'
import { feedbackError } from '../sound'

const router = useRouter()
const tab = ref('receive')
const tabs = computed(() => [
  { value: 'receive', label: __('Receive') },
  { value: 'count', label: __('Count') },
])
const orders = ref([])
const warehouses = ref([])
const warehouse = ref(readWarehouse())
const search = ref('')
const loading = ref(false)
const loaded = ref(false)
const error = ref('')
const opening = ref(null)
const menuOpen = ref(false)
const online = ref(navigator.onLine)
const syncedAt = ref('')

function readWarehouse() {
  try {
    return localStorage.getItem('hasr_warehouse') || ''
  } catch (e) {
    return ''
  }
}

async function load() {
  loading.value = true
  try {
    orders.value = await api('receiving.list_open_orders', { warehouse: warehouse.value || null, search: search.value })
    error.value = ''
    syncedAt.value = formatTime(new Date())
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
    loaded.value = true
  }
}

function daysFromToday(date) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return Math.round((new Date(date + 'T00:00:00') - today) / 86400000)
}

function badge(o) {
  if (o.open_session) {
    if (o.open_session_by === session.user) return { theme: 'blue', label: __('In progress') }
    return { theme: 'gray', label: __('Being received') }
  }
  if (o.items_received > 0 || o.per_received > 0) {
    return { theme: 'orange', label: __('Partial {0} of {1}', [o.items_received, o.item_count]) }
  }
  const days = o.schedule_date ? daysFromToday(o.schedule_date) : null
  if (days === null) return { theme: 'gray', label: __('Open') }
  if (days < 0) return { theme: 'red', label: days === -1 ? __('1 day late') : __('{0} days late', [-days]) }
  if (days === 0) return { theme: 'blue', label: __('Today') }
  if (days === 1) return { theme: 'gray', label: __('Tomorrow') }
  return { theme: 'gray', label: new Intl.DateTimeFormat(lang.value, { day: 'numeric', month: 'short' }).format(new Date(o.schedule_date + 'T00:00:00')) }
}

async function open(o) {
  if (o.open_session && o.open_session_by === session.user) {
    return router.push({ name: 'Receive', params: { session: o.open_session } })
  }
  opening.value = o.name
  try {
    const s = await api('receiving.start_session', { purchase_order: o.name })
    router.push({ name: 'Receive', params: { session: s.name } })
  } catch (e) {
    feedbackError()
    error.value = errorMessage(e)
  } finally {
    opening.value = null
  }
}

let timer = null
watch(search, () => {
  clearTimeout(timer)
  timer = setTimeout(load, 300)
})
watch(warehouse, (w) => {
  try {
    localStorage.setItem('hasr_warehouse', w)
  } catch (e) {
    /* not remembered */
  }
  load()
})

const setOnline = () => (online.value = navigator.onLine)
onMounted(async () => {
  window.addEventListener('online', setOnline)
  window.addEventListener('offline', setOnline)
  warehouses.value = await api('receiving.list_warehouses').catch(() => [])
  if (warehouse.value && !warehouses.value.some((w) => w.name === warehouse.value)) warehouse.value = ''
  load()
})
onBeforeUnmount(() => {
  window.removeEventListener('online', setOnline)
  window.removeEventListener('offline', setOnline)
})
</script>
