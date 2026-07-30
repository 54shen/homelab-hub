<template>
  <n-message-provider>
    <n-notification-provider>
      <n-dialog-provider>
        <router-view />
      </n-dialog-provider>
    </n-notification-provider>
  </n-message-provider>
</template>

<script setup lang="ts">
import { NMessageProvider, NNotificationProvider, NDialogProvider } from 'naive-ui'
</script>
