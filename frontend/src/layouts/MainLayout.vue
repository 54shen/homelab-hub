<template>
  <div class="main-layout">
    <AppSidebar />
    <AppTopbar />
    <main class="main-content">
      <router-view v-slot="{ Component, route: childRoute }">
        <component :is="Component" :key="childRoute.fullPath" />
      </router-view>
    </main>
  </div>
</template>

<script setup lang="ts">
import AppSidebar from '../components/AppSidebar.vue'
import AppTopbar from '../components/AppTopbar.vue'
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
}
</style>
