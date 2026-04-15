<template>
  <header
    class="h-12 bg-slate-800 text-white flex items-center justify-between px-6 flex-shrink-0"
  >
    <div class="flex items-center gap-3">
      <span class="text-lg font-bold tracking-wide">MINI WORLD</span>
      <span class="text-xs text-slate-400">闭合小世界构建与演变可视化</span>
    </div>
    <div class="flex items-center gap-4">
      <el-tag v-if="state.phase === 'building'" type="warning" effect="dark" size="small"
        >构建中 {{ state.buildIteration }}/{{ state.buildMaxIterations }}</el-tag
      >
      <el-tag v-else-if="state.phase === 'evolving'" type="danger" effect="dark" size="small"
        >演变中 Tick {{ state.currentTick }}/{{ state.maxTicksSetting }}</el-tag
      >
      <el-tag v-else-if="state.phase === 'built'" type="success" effect="dark" size="small"
        >世界已构建</el-tag
      >
      <el-tag v-else-if="state.phase === 'evolved'" type="info" effect="dark" size="small"
        >演变完成</el-tag
      >
      <el-button size="small" @click="showWorldList = true">历史记录</el-button>
    </div>

    <WorldListModal v-model:visible="showWorldList" />
  </header>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useWorldStore } from "../composables/useWorldStore";
import WorldListModal from "./WorldListModal.vue";

const { state } = useWorldStore();
const showWorldList = ref(false);
</script>
