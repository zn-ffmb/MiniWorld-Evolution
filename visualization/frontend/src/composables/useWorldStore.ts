import { reactive } from "vue";

export type AppPhase = "idle" | "building" | "built" | "evolving" | "evolved";

export interface WorldStoreState {
  phase: AppPhase;
  worldId: string | null;
  background: string;
  focus: string;
  perturbation: string;
  maxTicks: number;
  tickUnit: string;
  worldDescription: string;
  // 构建统计
  buildIteration: number;
  buildMaxIterations: number;
  humanCount: number;
  natureCount: number;
  totalEntities: number;
  totalEdges: number;
  converged: boolean;
  convergenceReport: string;
  // 演变统计
  currentTick: number;
  maxTicksSetting: number;
  // 时间线叙事
  narratives: Array<{ tick: number; narrative: string }>;
  // 事件日志
  logs: Array<{ time: string; type: string; message: string }>;
  // 选中的节点
  selectedNode: any | null;
  // 实体历史状态（entity_id → tick 变更记录数组）
  entityHistory: Record<string, Array<{
    tick: number;
    old_status: string;
    new_status: string;
    change_reason: string;
  }>>;
}

const state = reactive<WorldStoreState>({
  phase: "idle",
  worldId: null,
  background: "",
  focus: "",
  perturbation: "",
  maxTicks: 10,
  tickUnit: "",
  worldDescription: "",
  buildIteration: 0,
  buildMaxIterations: 0,
  humanCount: 0,
  natureCount: 0,
  totalEntities: 0,
  totalEdges: 0,
  converged: false,
  convergenceReport: "",
  currentTick: 0,
  maxTicksSetting: 10,
  narratives: [],
  logs: [],
  selectedNode: null,
  entityHistory: {},
});

function addLog(type: string, message: string) {
  const time = new Date().toLocaleTimeString("zh-CN");
  state.logs.push({ time, type, message });
  // 限制日志数量
  if (state.logs.length > 500) {
    state.logs.splice(0, state.logs.length - 500);
  }
}

function reset() {
  state.phase = "idle";
  state.worldId = null;
  state.buildIteration = 0;
  state.buildMaxIterations = 0;
  state.humanCount = 0;
  state.natureCount = 0;
  state.totalEntities = 0;
  state.totalEdges = 0;
  state.converged = false;
  state.convergenceReport = "";
  state.currentTick = 0;
  state.narratives = [];
  state.logs = [];
  state.selectedNode = null;
  state.entityHistory = {};
  state.worldDescription = "";
  state.tickUnit = "";
}

export function useWorldStore() {
  return { state, addLog, reset };
}
