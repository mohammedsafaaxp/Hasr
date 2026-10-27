<template>
  <div class="flex min-h-full flex-col px-6 pb-6 pt-4">
    <div class="flex justify-end"><LanguageSelect /></div>
    <div class="flex flex-1 flex-col items-center justify-center gap-3 py-10 text-center">
      <AppLogo :size="88" />
      <h1 class="text-5xl font-bold tracking-[-0.045em]">{{ lang === 'ar' ? 'حَصر' : 'hasr' }}</h1>
      <p class="text-[15px] text-hasr-secondary">{{ __('Receiving and stock counts for ERPNext') }}</p>
      <span class="inline-flex items-center gap-2 rounded-full bg-hasr-surface2 px-3 py-1 text-sm text-hasr-secondary">
        <span class="size-2 rounded-full bg-green-600" />{{ host }}
      </span>
    </div>
    <form class="space-y-3" @submit.prevent="submit">
      <label class="block space-y-1">
        <span class="text-sm text-hasr-secondary">{{ __('Email or username') }}</span>
        <input v-model="usr" type="text" autocomplete="username" autocapitalize="off" required class="h-12 w-full rounded-hasr border-0 bg-hasr-surface2 px-4 text-[15px]" />
      </label>
      <label class="block space-y-1">
        <span class="text-sm text-hasr-secondary">{{ __('Password') }}</span>
        <input v-model="pwd" type="password" autocomplete="current-password" required class="h-12 w-full rounded-hasr border-0 bg-hasr-surface2 px-4 text-[15px]" />
      </label>
      <p v-if="error" class="rounded-hasr bg-hasr-danger-bg p-3 text-sm text-hasr-danger">{{ error }}</p>
      <button type="submit" class="h-12 w-full rounded-hasr bg-hasr-ink text-[15px] font-medium text-white disabled:opacity-50" :disabled="busy">
        {{ busy ? __('Signing in…') : __('Sign in') }}
      </button>
      <p class="text-center text-sm text-hasr-muted">{{ __('Use your ERPNext account') }}</p>
    </form>
    <p class="mt-6 text-center text-xs text-hasr-muted">{{ __('Open source') }} · GPLv3 · v{{ session.version || '0.1' }}</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import AppLogo from '../components/AppLogo.vue'
import LanguageSelect from '../components/LanguageSelect.vue'
import { login, session } from '../session'
import { errorMessage } from '../api'
import { __, lang } from '../i18n'

const usr = ref('')
const pwd = ref('')
const busy = ref(false)
const error = ref('')
const host = window.location.host

async function submit() {
  busy.value = true
  error.value = ''
  try {
    await login(usr.value.trim(), pwd.value)
  } catch (e) {
    error.value = e && e.status === 401 ? __('Wrong email or password.') : errorMessage(e)
    busy.value = false
  }
}
</script>
