<template>
  <aside class="w-[300px] bg-white border-r border-slate-200 flex flex-col overflow-y-auto flex-shrink-0">
    <!-- 构建表单 -->
    <div class="p-4 border-b border-slate-100">
      <h3 class="text-sm font-semibold text-slate-600 mb-3">世界构建</h3>
      <el-form :model="buildForm" label-position="top" size="small">
        <el-form-item label="背景">
          <el-input
            v-model="buildForm.background"
            placeholder="如: 美伊战争"
            :disabled="isRunning"
          />
        </el-form-item>
        <el-form-item label="关注点">
          <el-input
            v-model="buildForm.focus"
            placeholder="如: 石油价格"
            :disabled="isRunning"
          />
        </el-form-item>
        <el-form-item label="最大迭代次数">
          <el-input-number
            v-model="buildForm.maxIterations"
            :min="1"
            :max="10"
            :disabled="isRunning"
            style="width: 100%"
          />
        </el-form-item>
        <el-button
          type="primary"
          :loading="state.phase === 'building'"
          :disabled="isRunning || !buildForm.background || !buildForm.focus"
          @click="handleBuild"
          style="width: 100%"
        >
          {{ state.phase === "building" ? "构建中..." : "构建世界" }}
        </el-button>
      </el-form>
    </div>

    <!-- 演变表单 -->
    <div class="p-4 border-b border-slate-100">
      <h3 class="text-sm font-semibold text-slate-600 mb-3">演变模拟</h3>
      <el-form :model="evolveForm" label-position="top" size="small">
        <el-form-item label="扰动事件">
          <el-input
            v-model="evolveForm.perturbation"
            type="textarea"
            :rows="2"
            placeholder="如: 霍尔木兹海峡被伊朗完全封锁"
            :disabled="!canEvolve"
          />
        </el-form-item>
        <el-form-item label="最大 Tick 数">
          <el-input-number
            v-model="evolveForm.maxTicks"
            :min="1"
            :max="50"
            :disabled="!canEvolve"
            style="width: 100%"
          />
        </el-form-item>
        <el-button
          type="danger"
          :loading="state.phase === 'evolving'"
          :disabled="!canEvolve || !evolveForm.perturbation"
          @click="handleEvolve"
          style="width: 100%"
        >
          {{ state.phase === "evolving" ? "演变中..." : "开始演变" }}
        </el-button>
      </el-form>
    </div>

    <!-- 世界统计 -->
    <div class="p-4">
      <h3 class="text-sm font-semibold text-slate-600 mb-3">世界统计</h3>
      <div class="space-y-2 text-xs text-slate-500">
        <div class="flex justify-between">
          <span>人类类实体</span>
          <span class="font-mono text-blue-600">{{ state.humanCount }}</span>
        </div>
        <div class="flex justify-between">
          <span>自然类实体</span>
          <span class="font-mono text-green-600">{{ state.natureCount }}</span>
        </div>
        <div class="flex justify-between">
          <span>关系边</span>
          <span class="font-mono text-slate-700">{{ state.totalEdges }}</span>
        </div>
        <div class="flex justify-between">
          <span>收敛状态</span>
          <el-tag :type="state.converged ? 'success' : 'warning'" size="small" effect="plain">
            {{ state.converged ? "已收敛" : state.phase === "building" ? "构建中" : "—" }}
          </el-tag>
        </div>
        <div v-if="state.tickUnit" class="flex justify-between">
          <span>时间单位</span>
          <span class="font-mono">{{ state.tickUnit }}</span>
        </div>
        <div v-if="state.worldDescription" class="mt-2 text-xs text-slate-400 leading-relaxed">
          {{ state.worldDescription.slice(0, 150) }}...
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { reactive, computed } from "vue";
import { useWorldStore } from "../composables/useWorldStore";
import { startBuild, startEvolve } from "../api/client";
import { useSSE } from "../composables/useSSE";
import { useCytoscapeGlobal } from "./cytoscapeProvider";

const { state, addLog, reset } = useWorldStore();
const sse = useSSE();
const cyGlobal = useCytoscapeGlobal();

const buildForm = reactive({
  background: "",
  focus: "",
  maxIterations: 3,
});

const evolveForm = reactive({
  perturbation: "",
  maxTicks: 10,
});

const isRunning = computed(
  () => state.phase === "building" || state.phase === "evolving"
);
const canEvolve = computed(
  () =>
    (state.phase === "built" || state.phase === "evolved") && state.worldId !== null
);

/** 启动世界构建 */
async function handleBuild() {
  reset();
  state.phase = "building";
  state.background = buildForm.background;
  state.focus = buildForm.focus;

  try {
    const resp = await startBuild({
      background: buildForm.background,
      focus: buildForm.focus,
      max_iterations: buildForm.maxIterations,
    });

    addLog("info", `构建任务已启动: ${resp.task_id}`);

    // 注册 SSE 事件处理器
    registerBuildHandlers();

    // 连接 SSE
    sse.connect(resp.stream_url);
  } catch (err: any) {
    state.phase = "idle";
    addLog("error", `启动构建失败: ${err.message}`);
  }
}

/** 启动演变模拟 */
async function handleEvolve() {
  if (!state.worldId) return;

  state.phase = "evolving";
  state.currentTick = 0;
  state.narratives = [];

  try {
    const resp = await startEvolve({
      world_id: state.worldId,
      perturbation: evolveForm.perturbation,
      max_ticks: evolveForm.maxTicks,
    });

    state.maxTicksSetting = evolveForm.maxTicks;
    addLog("info", `演变任务已启动: ${resp.task_id}`);

    // 注册 SSE 事件处理器
    registerEvolveHandlers();

    // 连接 SSE
    sse.connect(resp.stream_url);
  } catch (err: any) {
    state.phase = "built";
    addLog("error", `启动演变失败: ${err.message}`);
  }
}

/** 注册 L1 构建事件处理器 */
function registerBuildHandlers() {
  sse.clearListeners();

  sse.on("build:iteration_start", (data) => {
    state.buildIteration = data.iteration;
    state.buildMaxIterations = data.max_iterations;
    addLog("info", `迭代 ${data.iteration}/${data.max_iterations}`);
  });

  sse.on("build:search_plan", (data) => {
    addLog("search", `搜索计划: ${data.search_tasks?.length || 0} 个任务`);
  });

  sse.on("build:search_done", (data) => {
    addLog("search", `搜索完成: ${data.result_count} 条结果`);
  });

  sse.on("build:entities_extracted", (data) => {
    const newE = data.new_entities || [];
    const newEdges = data.new_edges || [];
    addLog(
      "extract",
      `提取: ${newE.length} 新实体, ${newEdges.length} 新关系`
    );

    // 在图上增量添加
    if (cyGlobal.addEntities) {
      cyGlobal.addEntities(newE, newEdges);
    }
  });

  sse.on("build:merge_done", (data) => {
    state.totalEntities = data.total_entities;
    state.totalEdges = data.total_edges;
    state.humanCount = data.human_count;
    state.natureCount = data.nature_count;
  });

  sse.on("build:convergence", (data) => {
    state.converged = data.converged;
    state.convergenceReport = data.report;
    addLog(
      data.converged ? "success" : "warning",
      data.converged ? "收敛检测通过 ✓" : `未收敛: ${data.report?.slice(0, 80)}`
    );
  });

  sse.on("build:extraction_failed", (data) => {
    addLog(
      "warning",
      `迭代 ${data.iteration} 实体提取失败: ${data.error}，将在下一轮重试`
    );
  });

  sse.on("build:prompts_start", (data) => {
    addLog("info", `开始为 ${data.total_agents} 个人类类实体生成 Agent Prompt...`);
  });

  sse.on("build:prompt_progress", (data) => {
    addLog(
      "info",
      `Agent Prompt (${data.progress}/${data.total}): ${data.agent_name} ${data.has_prompt ? "✓" : "✗"}`
    );
  });

  sse.on("build:prompts_generated", (data) => {
    addLog("success", `Agent Prompt 全部生成完成: ${data.agent_count} 个`);
  });

  sse.on("build:meta_generated", (data) => {
    state.tickUnit = data.tick_unit || "";
    state.worldDescription = data.world_description || "";
    addLog("info", `世界元信息已生成, tick 单位: ${data.tick_unit}`);
  });

  // v3: 网络分析结果
  sse.on("build:network_analysis", (data) => {
    state.networkAnalysis = data;
    addLog("info", `网络分析完成: 密度 ${data.global_metrics?.density}, 聚类系数 ${data.global_metrics?.clustering_coefficient}`);
    // 根据中心性调整节点大小
    if (cyGlobal.applyNetworkMetrics && data.node_metrics) {
      cyGlobal.applyNetworkMetrics(data.node_metrics);
    }
  });

  sse.on("build:complete", (data) => {
    state.phase = "built";
    state.worldId = data.world_id;
    const s = data.snapshot_summary;
    addLog(
      "success",
      `世界构建完成! ID: ${data.world_id}, ` +
        `人类: ${s.human_entity_count}, 自然: ${s.nature_entity_count}, 边: ${s.edge_count}`
    );
    sse.disconnect();
  });

  sse.on("build:error", (data) => {
    state.phase = "idle";
    addLog("error", `构建错误: ${data.message}`);
    sse.disconnect();
  });
}

/** 注册 L2 演变事件处理器 */
function registerEvolveHandlers() {
  sse.clearListeners();

  sse.on("evolve:start", (data) => {
    addLog("info", `演变开始: ${data.perturbation}`);
    // 加载完整图
    if (cyGlobal.loadFullGraph) {
      cyGlobal.loadFullGraph(data.entities, data.edges);
    }
    // v3: 存储实体富信息（利益/目标/时效性）
    for (const e of data.entities || []) {
      if (e.interests || e.goal_structure || e.evidence_freshness) {
        state.entityRichData[e.id] = {
          interests: e.interests,
          goal_structure: e.goal_structure,
          evidence_freshness: e.evidence_freshness,
          evidence_date_range: e.evidence_date_range,
          status_trend: e.status_trend,
        };
      }
    }
  });

  sse.on("evolve:tick_start", (data) => {
    state.currentTick = data.tick;
    if (cyGlobal.clearTickHighlights) {
      cyGlobal.clearTickHighlights();
    }
  });

  sse.on("evolve:assessment", (data) => {
    addLog("assess", `Tick ${data.tick} 评估: ${data.assessment || ''}`);
  });

  sse.on("evolve:plan", (data) => {
    addLog("plan", `Tick ${data.tick} 激活 ${data.active_agents?.length || 0} 个 Agent`);
    if (cyGlobal.highlightAgents) {
      cyGlobal.highlightAgents(data.active_agents);
    }
  });

  sse.on("evolve:agent_action", (data) => {
    const styleTag = data.cognition_style === "intuitive" ? "[⚡直觉] "
      : data.cognition_style === "reactive" ? "[🔥应激] "
      : "[🎯策略] ";
    addLog(
      "action",
      `${styleTag}${data.agent_name} [${data.action_type}]: ${data.action_description || ''}`
    );
    // v3: 存储完整行动数据
    if (!state.agentActions[data.tick]) {
      state.agentActions[data.tick] = [];
    }
    state.agentActions[data.tick].push(data);

    if (cyGlobal.pulseAgent) {
      cyGlobal.pulseAgent(data.agent_id, data.target_entities || []);
    }
  });

  sse.on("evolve:propagation", (data) => {
    const updates = data.entity_updates || [];
    addLog("propagate", `Tick ${data.tick} 传播: ${updates.length} 个实体更新`);
    // 收集实体历史状态
    for (const u of updates) {
      if (!u.entity_id) continue;
      if (!state.entityHistory[u.entity_id]) {
        state.entityHistory[u.entity_id] = [];
      }
      state.entityHistory[u.entity_id].push({
        tick: data.tick,
        old_status: u.old_status || "",
        new_status: u.new_status || "",
        change_reason: u.change_reason || "",
      });
    }
    if (cyGlobal.showPropagation) {
      cyGlobal.showPropagation(updates);
    }
  });

  sse.on("evolve:narrative", (data) => {
    state.narratives.push({ tick: data.tick, narrative: data.narrative });
    addLog("narrative", `Tick ${data.tick}: ${data.narrative || ''}`);
  });

  sse.on("evolve:equilibrium", (data) => {
    state.equilibriumDetected = true;
    state.equilibriumReason = data.reason;
    state.equilibriumTick = data.tick;
    addLog("warning", `⚖️ 均衡检测触发终止 (Tick ${data.tick}): ${data.reason}`);
  });

  sse.on("evolve:complete", (data) => {
    state.phase = "evolved";
    const s = data.summary;
    addLog(
      "success",
      `演变完成! 总 tick: ${data.total_ticks}, ` +
        `动作: ${s.total_agent_actions}, 变更: ${s.total_entity_updates}` +
        (data.termination_reason ? ` | 终止原因: ${data.termination_reason}` : "")
    );
    sse.disconnect();
  });

  sse.on("evolve:error", (data) => {
    state.phase = "built";
    addLog("error", `演变错误: ${data.message}`);
    sse.disconnect();
  });
}
</script>
