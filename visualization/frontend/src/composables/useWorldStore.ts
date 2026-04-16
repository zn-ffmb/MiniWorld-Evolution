import { reactive } from "vue";
import type { EvolveAgentActionData } from "../types/events";

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
  // v3: Agent 行动详情（tick → 行动数组）
  agentActions: Record<number, EvolveAgentActionData[]>;
  // v3: 当前选中查看的 Agent 行动
  selectedAction: EvolveAgentActionData | null;
  // v3: 均衡检测
  equilibriumDetected: boolean;
  equilibriumReason: string;
  equilibriumTick: number;
  // v3: 网络分析
  networkAnalysis: any | null;
  // v3: 实体富信息（entity_id → interests, goal_structure, evidence）
  entityRichData: Record<string, {
    interests?: any[];
    goal_structure?: any;
    evidence_freshness?: string;
    evidence_date_range?: string;
    status_trend?: string;
  }>;
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
  agentActions: {},
  selectedAction: null,
  equilibriumDetected: false,
  equilibriumReason: "",
  equilibriumTick: 0,
  networkAnalysis: null,
  entityRichData: {},
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
  state.agentActions = {};
  state.selectedAction = null;
  state.equilibriumDetected = false;
  state.equilibriumReason = "";
  state.equilibriumTick = 0;
  state.networkAnalysis = null;
  state.entityRichData = {};
  state.worldDescription = "";
  state.tickUnit = "";
}

export function useWorldStore() {
  return { state, addLog, reset };
}
