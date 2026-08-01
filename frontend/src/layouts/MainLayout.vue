<template>
  <div class="main-layout" :class="{ 'sidebar-collapsed': collapsed }">
    <AppSidebar :collapsed="collapsed" @toggle="collapsed = !collapsed" />
    <AppTopbar :collapsed="collapsed" @toggle="collapsed = !collapsed" />
    <main class="main-content">
      <router-view v-slot="{ Component, route: childRoute }">
        <component :is="Component" :key="childRoute.fullPath" />
      </router-view>
    </main>
    <div v-if="isMobile && !collapsed" class="sidebar-overlay" @click="collapsed = true"></div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import AppSidebar from '../components/AppSidebar.vue'
import AppTopbar from '../components/AppTopbar.vue'

const collapsed = ref(window.innerWidth < 768)
const isMobile = ref(window.innerWidth < 768)
let mediaQuery: MediaQueryList

function onResize() {
  const mobile = window.innerWidth < 768
  isMobile.value = mobile
  collapsed.value = mobile
}

onMounted(() => {
  mediaQuery = window.matchMedia('(max-width: 767px)')
  mediaQuery.addEventListener('change', onResize)
})

onUnmounted(() => {
  mediaQuery?.removeEventListener('change', onResize)
})
</script>

<style scoped>
.main-layout {
  height: 100%;
  display: flex;
}

.main-content {
  flex: 1;
  margin-left: var(--sidebar-width);
  margin-top: var(--topbar-height);
  min-height: calc(100vh - var(--topbar-height));
  overflow-y: auto;
  transition: margin-left 0.25s ease;
}

.sidebar-collapsed .main-content {
  margin-left: 0;
}

.sidebar-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  z-index: 95;
}
</style>
