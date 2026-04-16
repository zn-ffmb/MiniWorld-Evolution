/**
 * 全局 Cytoscape 操作接口。
 *
 * CenterCanvas 注册其 Cytoscape 操作方法到此处，
 * LeftPanel 的事件处理器通过此接口调用图操作。
 */

import { reactive } from "vue";
import type { EntityUpdate } from "../types/entity";

interface CytoscapeGlobal {
  addEntities: ((entities: any[], edges: any[]) => void) | null;
  loadFullGraph: ((entities: any[], edges: any[]) => void) | null;
  highlightAgents: ((agentIds: string[]) => void) | null;
  pulseAgent: ((agentId: string, targets: string[]) => void) | null;
  showPropagation: ((updates: EntityUpdate[]) => void) | null;
  clearTickHighlights: (() => void) | null;
  fitView: (() => void) | null;
  runLayout: (() => void) | null;
  applyNetworkMetrics: ((nodeMetrics: Record<string, any>) => void) | null;
}

const cyGlobal = reactive<CytoscapeGlobal>({
  addEntities: null,
  loadFullGraph: null,
  highlightAgents: null,
  pulseAgent: null,
  showPropagation: null,
  clearTickHighlights: null,
  fitView: null,
  runLayout: null,
  applyNetworkMetrics: null,
});

export function useCytoscapeGlobal() {
  return cyGlobal;
}
