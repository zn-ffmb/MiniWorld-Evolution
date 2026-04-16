<template>
  <main class="flex-1 flex flex-col bg-slate-50 relative">
    <!-- 画布 -->
    <div ref="graphContainer" class="flex-1" />

    <!-- 控制栏 -->
    <div
      class="absolute bottom-4 left-1/2 -translate-x-1/2 bg-white/90 backdrop-blur rounded-lg shadow-md px-4 py-2 flex items-center gap-3"
    >
      <el-button size="small" @click="handleFit" :icon="FullScreen">居中</el-button>
      <el-button size="small" @click="handleRelayout" :icon="Refresh">重排</el-button>
    </div>
  </main>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import { FullScreen, Refresh } from "@element-plus/icons-vue";
import { useCytoscape } from "../composables/useCytoscape";
import { useCytoscapeGlobal } from "./cytoscapeProvider";
import { useWorldStore } from "../composables/useWorldStore";

const graphContainer = ref<HTMLElement | null>(null);
const { state } = useWorldStore();
const cyGlobal = useCytoscapeGlobal();

const {
  init,
  destroy,
  addEntities,
  loadFullGraph,
  runLayout,
  highlightAgents,
  pulseAgent,
  showPropagation,
  clearTickHighlights,
  fitView,
  applyNetworkMetrics,
  onNodeClick,
} = useCytoscape(graphContainer);

onMounted(() => {
  init();

  // 注册全局操作方法
  cyGlobal.addEntities = addEntities;
  cyGlobal.loadFullGraph = loadFullGraph;
  cyGlobal.highlightAgents = highlightAgents;
  cyGlobal.pulseAgent = pulseAgent;
  cyGlobal.showPropagation = showPropagation;
  cyGlobal.clearTickHighlights = clearTickHighlights;
  cyGlobal.fitView = fitView;
  cyGlobal.runLayout = runLayout;
  cyGlobal.applyNetworkMetrics = applyNetworkMetrics;

  // 节点点击
  onNodeClick((data) => {
    state.selectedNode = data;
  });
});

onUnmounted(() => {
  destroy();
  cyGlobal.addEntities = null;
  cyGlobal.loadFullGraph = null;
  cyGlobal.highlightAgents = null;
  cyGlobal.pulseAgent = null;
  cyGlobal.showPropagation = null;
  cyGlobal.clearTickHighlights = null;
  cyGlobal.fitView = null;
  cyGlobal.runLayout = null;
});

function handleFit() {
  fitView();
}

function handleRelayout() {
  runLayout();
}
</script>
