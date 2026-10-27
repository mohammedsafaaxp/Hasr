<template>
  <label class="inline-flex h-11 items-center gap-2 rounded-hasr bg-hasr-surface2 px-3">
    <LucideGlobe class="size-5 text-hasr-secondary" />
    <select
      :value="lang"
      class="border-0 bg-transparent p-0 pe-6 text-[15px] focus:ring-0"
      :aria-label="__('Language')"
      @change="setLanguage($event.target.value, { remember: true })"
    >
      <option v-for="l in LANGUAGES" :key="l.value" :value="l.value">{{ l.label }}</option>
    </select>
  </label>
</template>

<script setup>
import { LANGUAGES, lang, setLanguage } from '../i18n'
</script>
