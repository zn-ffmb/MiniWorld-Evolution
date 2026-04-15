<template>
  <aside class="w-[350px] bg-white border-l border-slate-200 flex flex-col overflow-hidden flex-shrink-0">
    <!-- 选项卡 -->
    <el-tabs v-model="activeTab" class="flex-1 flex flex-col px-2 pt-2">
      <!-- 事件日志 -->
      <el-tab-pane label="事件日志" name="logs" class="flex-1 overflow-hidden">
        <div ref="logContainer" class="h-full overflow-y-auto pr-1">
          <div
            v-for="(log, i) in state.logs"
            :key="i"
            class="text-xs py-1 border-b border-slate-50 flex gap-2"
          >
            <span class="text-slate-400 flex-shrink-0 w-16">{{ log.time }}</span>
            <el-tag
              :type="logTagType(log.type)"
              size="small"
              effect="plain"
              class="flex-shrink-0"
              style="font-size: 10px"
            >
              {{ logTagLabel(log.type) }}
            </el-tag>
            <span class="text-slate-600 break-all">{{ log.message }}</span>
          </div>
          <div v-if="state.logs.length === 0" class="text-xs text-slate-400 text-center py-8">
            等待事件...
          </div>
        </div>
      </el-tab-pane>

      <!-- 时间线叙事 -->
      <el-tab-pane label="时间线" name="timeline" class="flex-1 overflow-hidden">
        <div class="h-full overflow-y-auto pr-1">
          <div
            v-for="item in state.narratives"
            :key="item.tick"
            class="mb-3 p-3 bg-slate-50 rounded-lg"
          >
            <div class="flex items-center gap-2 mb-1">
              <el-tag size="small" type="danger" effect="dark">Tick {{ item.tick }}</el-tag>
            </div>
            <p class="text-xs text-slate-600 leading-relaxed">{{ item.narrative }}</p>
          </div>
          <div v-if="state.narratives.length === 0" class="text-xs text-slate-400 text-center py-8">
            演变开始后将显示每个 Tick 的叙事...
          </div>
        </div>
      </el-tab-pane>

      <!-- 实体详情 -->
      <el-tab-pane label="实体详情" name="detail" class="flex-1 overflow-hidden">
        <div class="h-full overflow-y-auto pr-1">
          <div v-if="state.selectedNode" class="space-y-3">
            <div>
              <div class="text-sm font-semibold text-slate-700">
                {{ state.selectedNode.label }}
              </div>
              <el-tag
                :type="state.selectedNode.type === 'human' ? 'primary' : 'success'"
                size="small"
                class="mt-1"
              >
                {{ state.selectedNode.type === "human" ? "人类类" : "自然类" }}
              </el-tag>
            </div>
            <div v-if="state.selectedNode.status" class="text-xs text-slate-500">
              <div class="font-semibold text-slate-600 mb-1">当前状态</div>
              <p class="leading-relaxed">{{ state.selectedNode.status }}</p>
            </div>
            <!-- 历史状态变更 -->
            <div v-if="nodeHistory.length > 0" class="text-xs">
              <div class="font-semibold text-slate-600 mb-2">状态变更历史</div>
              <div
                v-for="(h, i) in nodeHistory"
                :key="i"
                class="mb-2 p-2 bg-slate-50 rounded border-l-2 border-blue-300"
              >
                <div class="flex items-center gap-1 mb-1">
                  <el-tag size="small" type="info" effect="dark">Tick {{ h.tick }}</el-tag>
                </div>
                <p class="text-slate-500 leading-relaxed">{{ h.new_status }}</p>
                <p v-if="h.change_reason" class="text-slate-400 mt-1 italic">
                  原因: {{ h.change_reason }}
                </p>
              </div>
            </div>
          </div>
          <div v-else class="text-xs text-slate-400 text-center py-8">
            点击图上的节点查看详情
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </aside>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, computed } from "vue";
import { useWorldStore } from "../composables/useWorldStore";

const { state } = useWorldStore();
const activeTab = ref("logs");
const logContainer = ref<HTMLElement | null>(null);

// 当前选中实体的历史状态
const nodeHistory = computed(() => {
  if (!state.selectedNode?.id) return [];
  return state.entityHistory[state.selectedNode.id] || [];
});

// 自动滚动日志到底部
watch(
  () => state.logs.length,
  async () => {
    await nextTick();
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight;
    }
  }
);

// 当有叙事时自动切换到时间线标签
watch(
  () => state.narratives.length,
  (newLen, oldLen) => {
    if (newLen > 0 && oldLen === 0) {
      activeTab.value = "timeline";
    }
  }
);

// 选中节点时切换到详情标签
watch(
  () => state.selectedNode,
  (node) => {
    if (node) {
      activeTab.value = "detail";
    }
  }
);

function logTagType(type: string) {
  const map: Record<string, string> = {
    info: "info",
    success: "success",
    warning: "warning",
    error: "danger",
    search: "info",
    extract: "",
    assess: "info",
    plan: "warning",
    action: "primary",
    propagate: "danger",
    narrative: "success",
  };
  return (map[type] as any) || "info";
}

function logTagLabel(type: string) {
  const map: Record<string, string> = {
    info: "信息",
    success: "完成",
    warning: "警告",
    error: "错误",
    search: "搜索",
    extract: "提取",
    assess: "评估",
    plan: "规划",
    action: "动作",
    propagate: "传播",
    narrative: "叙事",
  };
  return map[type] || type;
}
</script>

<style scoped>
:deep(.el-tabs__content) {
  flex: 1;
  overflow: hidden;
}
:deep(.el-tab-pane) {
  height: 100%;
}
:deep(.el-tabs) {
  display: flex;
  flex-direction: column;
  height: 100%;
}
</style>
