import { createApp } from 'vue'
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import '@fontsource/inter/700.css'
import '@fontsource/ibm-plex-sans-arabic/400.css'
import '@fontsource/ibm-plex-sans-arabic/500.css'
import '@fontsource/ibm-plex-sans-arabic/600.css'
import '@fontsource/ibm-plex-sans-arabic/700.css'
import './index.css'
import App from './App.vue'
import router from './router'
import { loadBoot, session } from './session'
import { pickLanguage, setLanguage, translationPlugin } from './i18n'

async function start() {
  await loadBoot().catch(() => {})
  await setLanguage(pickLanguage(session.lang))
  const app = createApp(App)
  app.use(translationPlugin)
  app.use(router)
  app.mount('#app')
}

start()
