<template>
  <main class="flex-1 pt-4">
    <div class="flex items-center justify-between border-b border-hasr-line px-4 pb-3 text-[15px] text-hasr-secondary">
      <span>{{ __('Your stock counts') }}</span>
      <span class="tabular">{{ counts.length }}</span>
    </div>
    <p v-if="error" class="m-4 rounded-hasr bg-hasr-danger-bg p-3 text-sm text-hasr-danger">{{ error }}</p>
    <div v-else-if="loaded && !counts.length" class="flex flex-col items-center gap-2 p-8 text-center">
      <LucideClipboardList class="size-8 text-hasr-muted" />
      <p class="text-[15px] font-medium">{{ __('No stock count for you right now') }}</p>
      <p class="text-sm text-hasr-muted">{{ __('When a supervisor starts a count and gives you a zone, it shows here.') }}</p>
    </div>
    <ul>
      <li v-for="c in counts" :key="c.name">
        <button
          type="button"
          class="flex w-full items-center gap-3 border-b border-hasr-line px-4 py-4 text-start active:bg-hasr-surface2"
          @click="router.push({ name: 'Count', params: { session: c.name } })"
        >
          <div class="min-w-0 flex-1 space-y-1">
            <div class="flex items-center justify-between gap-2">
              <span class="truncate text-[17px]">{{ c.warehouse_name }}</span>
              <Pill :theme="badge(c).theme">{{ badge(c).label }}</Pill>
            </div>
            <p class="truncate text-[15px] text-hasr-muted">
              {{ c.round === 'Recount' ? __('Recount') : __('Zone {0}', [c.zone]) }} ·
              {{ c.count_type === 'Full' ? __('Full count') : __('Cycle count') }} ·
              {{ c.round === 'Recount' ? __('{0} to recount', [c.to_recount]) : __('{0} counted', [c.counted]) }}
            </p>
          </div>
          <LucideChevronRight class="size-5 shrink-0 text-hasr-muted rtl:-scale-x-100" />
        </button>
      </li>
    </ul>
  </main>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import Pill from '../components/Pill.vue'
import { errorMessage } from '../api'
import { cachedApi } from '../offline'
import { __ } from '../i18n'

const emit = defineEmits(['loaded'])
const router = useRouter()
const counts = ref([])
const loaded = ref(false)
const error = ref('')

function badge(c) {
  if (c.handed_over) return { theme: 'green', label: __('Handed over') }
  if (c.round === 'Recount') return { theme: 'orange', label: __('Recount') }
  return { theme: 'blue', label: __('Counting') }
}

async function load() {
  try {
    const r = await cachedApi('my_counts', 'counting.my_counts')
    counts.value = r.data
    error.value = ''
    emit('loaded', r)
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loaded.value = true
  }
}

const onVisible = () => document.visibilityState === 'visible' && load()
onMounted(() => {
  document.addEventListener('visibilitychange', onVisible)
  load()
})
onBeforeUnmount(() => document.removeEventListener('visibilitychange', onVisible))
defineExpose({ load })
</script>
