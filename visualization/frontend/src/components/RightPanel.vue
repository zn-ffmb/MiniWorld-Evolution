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
          <!-- v3: 均衡终止摘要 -->
          <div
            v-if="state.equilibriumDetected"
            class="mb-3 p-3 bg-orange-50 rounded-lg border border-orange-200"
          >
            <div class="flex items-center gap-2 mb-1">
              <span class="text-sm">⚖️</span>
              <span class="text-xs font-semibold text-orange-700">均衡检测终止</span>
            </div>
            <p class="text-xs text-orange-600 leading-relaxed">
              触发 Tick: {{ state.equilibriumTick }}<br/>
              原因: {{ state.equilibriumReason }}
            </p>
          </div>
          <div v-if="state.narratives.length === 0" class="text-xs text-slate-400 text-center py-8">
            演变开始后将显示每个 Tick 的叙事...
          </div>
        </div>
      </el-tab-pane>

      <!-- 决策详情 (v3) -->
      <el-tab-pane label="决策详情" name="decisions" class="flex-1 overflow-hidden">
        <div class="h-full overflow-y-auto pr-1">
          <!-- 选中某个行动时显示详情 -->
          <template v-if="state.selectedAction">
            <div class="mb-3">
              <div class="flex items-center gap-2 mb-2">
                <el-tag size="small" type="danger" effect="dark">Tick {{ state.selectedAction.tick }}</el-tag>
                <span class="text-sm font-semibold text-slate-700">{{ state.selectedAction.agent_name }}</span>
                <el-tag size="small" :type="cognitionTagType(state.selectedAction.cognition_style)" effect="plain">
                  {{ cognitionLabel(state.selectedAction.cognition_style) }}
                </el-tag>
              </div>
              <div class="p-2 bg-blue-50 rounded text-xs text-slate-600 mb-2">
                <span class="font-semibold">[{{ state.selectedAction.action_type }}]</span>
                {{ state.selectedAction.action_description }}
              </div>
            </div>

            <!-- 局势研判 -->
            <div v-if="state.selectedAction.situation_assessment" class="mb-3">
              <div class="text-xs font-semibold text-slate-600 mb-1 flex items-center gap-1">
                <span>📋</span> 局势研判
              </div>
              <p class="text-xs text-slate-500 leading-relaxed p-2 bg-slate-50 rounded">
                {{ state.selectedAction.situation_assessment }}
              </p>
            </div>

            <!-- 关键方预判 -->
            <div v-if="state.selectedAction.key_party_predictions?.length" class="mb-3">
              <div class="text-xs font-semibold text-slate-600 mb-1 flex items-center gap-1">
                <span>🔮</span> 关键方预判
              </div>
              <div
                v-for="(pred, i) in state.selectedAction.key_party_predictions"
                :key="i"
                class="text-xs p-2 mb-1 bg-slate-50 rounded"
              >
                <div class="flex items-center gap-1 mb-1">
                  <span class="font-semibold text-slate-600">{{ pred.party }}</span>
                  <el-tag size="small" effect="plain" style="font-size: 10px">
                    {{ pred.relationship }}
                  </el-tag>
                </div>
                <p class="text-slate-500">{{ pred.predicted_action }}</p>
              </div>
            </div>

            <!-- 反事实分析 -->
            <div v-if="state.selectedAction.counterfactual" class="mb-3">
              <div class="text-xs font-semibold text-slate-600 mb-1 flex items-center gap-1">
                <span>⚖️</span> 反事实分析
              </div>
              <p class="text-xs text-slate-500 leading-relaxed p-2 bg-slate-50 rounded">
                {{ state.selectedAction.counterfactual }}
              </p>
            </div>

            <!-- 审议记录 -->
            <div v-if="state.selectedAction.deliberation?.length" class="mb-3">
              <div class="text-xs font-semibold text-slate-600 mb-1 flex items-center gap-1">
                <span>🤔</span> 换位审议
              </div>
              <div
                v-for="(d, i) in state.selectedAction.deliberation"
                :key="i"
                class="text-xs p-2 mb-1 bg-amber-50 rounded border-l-2 border-amber-300"
              >
                <p class="font-semibold text-amber-700 mb-1">{{ d.perspective }}</p>
                <p class="text-slate-500 mb-1">质疑: {{ d.challenge }}</p>
                <p class="text-slate-600">回应: {{ d.response }}</p>
              </div>
            </div>

            <!-- 直觉/应激上下文 -->
            <div v-if="state.selectedAction.cognition_context && state.selectedAction.cognition_style !== 'strategic'" class="mb-3">
              <div class="text-xs font-semibold text-slate-600 mb-1 flex items-center gap-1">
                <span>{{ state.selectedAction.cognition_style === 'intuitive' ? '⚡' : '🔥' }}</span>
                {{ state.selectedAction.cognition_style === 'intuitive' ? '直觉判断' : '情绪反应' }}
              </div>
              <div class="text-xs p-2 bg-slate-50 rounded space-y-1">
                <p v-for="(val, key) in state.selectedAction.cognition_context" :key="key" class="text-slate-500">
                  <span class="text-slate-600">{{ String(key) }}:</span> {{ val }}
                </p>
              </div>
            </div>

            <el-button size="small" text type="info" @click="state.selectedAction = null">
              ← 返回行动列表
            </el-button>
          </template>

          <!-- 行动列表（按 Tick 分组） -->
          <template v-else>
            <template v-for="tick in sortedActionTicks" :key="tick">
              <div class="mb-1 mt-2">
                <el-tag size="small" type="danger" effect="dark">Tick {{ tick }}</el-tag>
              </div>
              <div
                v-for="action in state.agentActions[tick]"
                :key="`${tick}-${action.agent_id}`"
                class="text-xs py-2 px-2 mb-1 bg-slate-50 rounded cursor-pointer hover:bg-blue-50 transition-colors"
                @click="state.selectedAction = action"
              >
                <div class="flex items-center gap-1 mb-1">
                  <el-tag size="small" :type="cognitionTagType(action.cognition_style)" effect="plain" style="font-size: 10px">
                    {{ cognitionLabel(action.cognition_style) }}
                  </el-tag>
                  <span class="font-semibold text-slate-600">{{ action.agent_name }}</span>
                </div>
                <p class="text-slate-500 truncate">[{{ action.action_type }}] {{ action.action_description }}</p>
                <p v-if="hasReasoningDetail(action)" class="text-blue-400 mt-1">点击查看推理详情 →</p>
              </div>
            </template>
            <div v-if="sortedActionTicks.length === 0" class="text-xs text-slate-400 text-center py-8">
              演变开始后将显示 Agent 决策详情...
            </div>
          </template>
        </div>
      </el-tab-pane>

      <!-- 实体详情 -->
      <el-tab-pane label="实体详情" name="detail" class="flex-1 overflow-hidden">
        <div class="h-full overflow-y-auto pr-1">
          <!-- v3: 网络概况（折叠） -->
          <div v-if="state.networkAnalysis" class="mb-3">
            <div
              class="text-xs font-semibold text-slate-600 cursor-pointer flex items-center gap-1 py-1"
              @click="showNetworkPanel = !showNetworkPanel"
            >
              📊 网络结构概况
              <span class="text-slate-400">{{ showNetworkPanel ? '▼' : '▶' }}</span>
            </div>
            <div v-if="showNetworkPanel" class="text-xs p-2 bg-slate-50 rounded mb-2 space-y-1">
              <div class="flex gap-3">
                <span>密度: <b>{{ state.networkAnalysis.global_metrics?.density }}</b></span>
                <span>聚类: <b>{{ state.networkAnalysis.global_metrics?.clustering_coefficient }}</b></span>
                <span>直径: <b>{{ state.networkAnalysis.global_metrics?.diameter }}</b></span>
              </div>
              <div v-if="state.networkAnalysis.hub_nodes?.length" class="mt-1">
                <span class="text-red-500">🔴 枢纽:</span>
                {{ state.networkAnalysis.hub_nodes.map((h: any) => h.name || h.id).join(', ') }}
              </div>
              <div v-if="state.networkAnalysis.vulnerable_nodes?.length" class="mt-1">
                <span class="text-yellow-500">🟡 脆弱:</span>
                {{ state.networkAnalysis.vulnerable_nodes.map((v: any) => v.name || v.id).join(', ') }}
              </div>
              <div v-if="state.networkAnalysis.communities?.length > 1" class="mt-1">
                <span class="text-blue-500">🔵 {{ state.networkAnalysis.communities.length }} 个社区</span>
              </div>
            </div>
          </div>

          <div v-if="state.selectedNode" class="space-y-3">
            <div>
              <div class="text-sm font-semibold text-slate-700">
                {{ state.selectedNode.label }}
              </div>
              <div class="flex items-center gap-1 mt-1">
                <el-tag
                  :type="state.selectedNode.type === 'human' ? 'primary' : 'success'"
                  size="small"
                >
                  {{ state.selectedNode.type === "human" ? "人类类" : "自然类" }}
                </el-tag>
                <el-tag
                  v-if="state.selectedNode.cognitionStyle && state.selectedNode.type === 'human'"
                  :type="cognitionTagType(state.selectedNode.cognitionStyle)"
                  size="small"
                  effect="plain"
                >
                  {{ cognitionLabel(state.selectedNode.cognitionStyle) }}
                </el-tag>
              </div>
            </div>

            <!-- v3: 证据时效性 -->
            <div v-if="selectedEntityRich?.evidence_freshness" class="text-xs">
              <div class="flex items-center gap-2">
                <span
                  class="inline-block w-2 h-2 rounded-full"
                  :class="{
                    'bg-green-500': selectedEntityRich.evidence_freshness === 'mostly_fresh',
                    'bg-yellow-500': selectedEntityRich.evidence_freshness === 'mixed',
                    'bg-red-500': selectedEntityRich.evidence_freshness === 'mostly_stale',
                  }"
                ></span>
                <span class="text-slate-500">
                  证据时效: {{ freshnessLabel(selectedEntityRich.evidence_freshness) }}
                  <span v-if="selectedEntityRich.evidence_date_range" class="text-slate-400">
                    ({{ selectedEntityRich.evidence_date_range }})
                  </span>
                </span>
              </div>
              <div v-if="selectedEntityRich.status_trend" class="text-slate-400 mt-1">
                📈 趋势: {{ selectedEntityRich.status_trend }}
              </div>
            </div>

            <div v-if="state.selectedNode.status" class="text-xs text-slate-500">
              <div class="font-semibold text-slate-600 mb-1">当前状态</div>
              <p class="leading-relaxed">{{ state.selectedNode.status }}</p>
            </div>

            <!-- v3: 利益维度 -->
            <div v-if="selectedEntityRich?.interests?.length" class="text-xs">
              <div
                class="font-semibold text-slate-600 cursor-pointer flex items-center gap-1"
                @click="showInterests = !showInterests"
              >
                📌 利益维度 ({{ selectedEntityRich.interests.length }})
                <span class="text-slate-400">{{ showInterests ? '▼' : '▶' }}</span>
              </div>
              <div v-if="showInterests" class="mt-1 space-y-1">
                <div
                  v-for="(interest, i) in selectedEntityRich.interests"
                  :key="i"
                  class="p-2 bg-slate-50 rounded"
                >
                  <div class="flex items-center gap-1 mb-1">
                    <span class="font-semibold text-slate-600">{{ interest.dimension }}</span>
                    <el-tag size="small" effect="plain" style="font-size: 10px">
                      {{ interest.priority === 'core' ? '核心' : interest.priority === 'important' ? '重要' : '次要' }}
                    </el-tag>
                    <span>{{ satisfactionEmoji(interest.current_satisfaction) }}</span>
                  </div>
                  <p class="text-slate-400">{{ interest.description }}</p>
                </div>
              </div>
            </div>

            <!-- v3: 目标结构 -->
            <div v-if="selectedEntityRich?.goal_structure" class="text-xs">
              <div
                class="font-semibold text-slate-600 cursor-pointer flex items-center gap-1"
                @click="showGoals = !showGoals"
              >
                🎯 目标结构
                <span class="text-slate-400">{{ showGoals ? '▼' : '▶' }}</span>
              </div>
              <div v-if="showGoals" class="mt-1 p-2 bg-slate-50 rounded space-y-1">
                <div v-if="selectedEntityRich.goal_structure.survival_goals?.length">
                  <span class="text-red-500">🔴 生存:</span>
                  <span v-for="(g, i) in selectedEntityRich.goal_structure.survival_goals" :key="i">
                    {{ g }}{{ i < selectedEntityRich.goal_structure.survival_goals.length - 1 ? '、' : '' }}
                  </span>
                </div>
                <div v-if="selectedEntityRich.goal_structure.strategic_goals?.length">
                  <span class="text-yellow-500">🟡 战略:</span>
                  <span v-for="(g, i) in selectedEntityRich.goal_structure.strategic_goals" :key="i">
                    {{ g }}{{ i < selectedEntityRich.goal_structure.strategic_goals.length - 1 ? '、' : '' }}
                  </span>
                </div>
                <div v-if="selectedEntityRich.goal_structure.opportunistic_goals?.length">
                  <span class="text-green-500">🟢 机会:</span>
                  <span v-for="(g, i) in selectedEntityRich.goal_structure.opportunistic_goals" :key="i">
                    {{ g }}{{ i < selectedEntityRich.goal_structure.opportunistic_goals.length - 1 ? '、' : '' }}
                  </span>
                </div>
                <div v-if="selectedEntityRich.goal_structure.rationality_constraints?.length">
                  <span class="text-slate-500">⚖️ 约束:</span>
                  <span v-for="(g, i) in selectedEntityRich.goal_structure.rationality_constraints" :key="i">
                    {{ g }}{{ i < selectedEntityRich.goal_structure.rationality_constraints.length - 1 ? '、' : '' }}
                  </span>
                </div>
              </div>
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
import type { EvolveAgentActionData } from "../types/events";

const { state } = useWorldStore();
const activeTab = ref("logs");
const logContainer = ref<HTMLElement | null>(null);
const showNetworkPanel = ref(false);
const showInterests = ref(true);
const showGoals = ref(false);

// 当前选中实体的历史状态
const nodeHistory = computed(() => {
  if (!state.selectedNode?.id) return [];
  return state.entityHistory[state.selectedNode.id] || [];
});

// v3: 当前选中实体的富信息
const selectedEntityRich = computed(() => {
  if (!state.selectedNode?.id) return null;
  return state.entityRichData[state.selectedNode.id] || null;
});

// v3: 按 tick 排序的行动列表
const sortedActionTicks = computed(() => {
  return Object.keys(state.agentActions)
    .map(Number)
    .sort((a, b) => a - b);
});

// v3: 判断行动是否有推理详情
function hasReasoningDetail(action: EvolveAgentActionData): boolean {
  return !!(
    action.situation_assessment ||
    action.key_party_predictions?.length ||
    action.counterfactual ||
    action.deliberation?.length ||
    (action.cognition_context && Object.keys(action.cognition_context).length)
  );
}

// v3: 认知风格标签类型
function cognitionTagType(style?: string): string {
  if (style === "intuitive") return "warning";
  if (style === "reactive") return "danger";
  return "primary";
}

// v3: 认知风格标签文字
function cognitionLabel(style?: string): string {
  if (style === "intuitive") return "⚡直觉";
  if (style === "reactive") return "🔥应激";
  return "🎯策略";
}

// v3: 认知风格标签文字
function cognitionLabel(style?: string): string {
  if (style === "intuitive") return "⚡直觉";
  if (style === "reactive") return "🔥应激";
  return "🎯策略";
}

// v3: 证据时效性标签
function freshnessLabel(freshness: string): string {
  if (freshness === "mostly_fresh") return "较新";
  if (freshness === "mixed") return "混合";
  if (freshness === "mostly_stale") return "较旧";
  return freshness;
}

// v3: 利益满意度 emoji
function satisfactionEmoji(satisfaction: string): string {
  if (satisfaction === "satisfied") return "✅";
  if (satisfaction === "neutral") return "😐";
  if (satisfaction === "threatened") return "⚠️";
  if (satisfaction === "critical") return "🔴";
  return "";
}

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
