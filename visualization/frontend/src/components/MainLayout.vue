<template>
  <div class="flex flex-1 overflow-hidden">
    <!-- 左侧面板 -->
    <LeftPanel />
    <!-- 中央画布 -->
    <CenterCanvas />
    <!-- 右侧面板 -->
    <RightPanel />
  </div>
</template>

<script setup lang="ts">
import LeftPanel from "./LeftPanel.vue";
import CenterCanvas from "./CenterCanvas.vue";
import RightPanel from "./RightPanel.vue";
</script>
