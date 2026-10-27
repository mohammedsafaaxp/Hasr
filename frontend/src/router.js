import { createRouter, createWebHistory } from 'vue-router'
import { session } from './session'

const routes = [
  { path: '/', name: 'Home', component: () => import('./pages/Home.vue') },
  { path: '/login', name: 'Login', component: () => import('./pages/Login.vue'), meta: { public: true } },
  { path: '/receive/:session', name: 'Receive', component: () => import('./pages/Receive.vue'), props: true },
  {
    path: '/receive/:session/line/:poItem',
    name: 'ReceiveLine',
    component: () => import('./pages/Receive.vue'),
    props: true,
  },
  { path: '/items/:itemCode', name: 'ItemDetails', component: () => import('./pages/ItemDetails.vue'), props: true },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory('/hasr'), routes })

router.beforeEach((to) => {
  if (!to.meta.public && !session.loggedIn) return { name: 'Login' }
  if (to.name === 'Login' && session.loggedIn) return { name: 'Home' }
})

export default router
