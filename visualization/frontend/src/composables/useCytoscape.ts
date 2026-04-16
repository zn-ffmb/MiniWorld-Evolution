import { ref, shallowRef, type Ref } from "vue";
import cytoscape, { type Core, type Stylesheet } from "cytoscape";
import coseBilkent from "cytoscape-cose-bilkent";
import type { EntityUpdate } from "../types/entity";

// 注册力导向布局插件（仅注册一次）
cytoscape.use(coseBilkent);

/** Cytoscape 图样式表 */
const GRAPH_STYLE: Stylesheet[] = [
  {
    selector: "node",
    style: {
      label: "data(label)",
      "text-valign": "center",
      "text-halign": "center",
      "font-size": "12px",
      "text-wrap": "wrap",
      "text-max-width": "100px",
      color: "#1F2937",
      "text-outline-color": "#fff",
      "text-outline-width": 2,
      "border-width": 2,
      "border-color": "#CBD5E1",
      width: 60,
      height: 60,
    },
  },
  {
    selector: 'node[type="human"]',
    style: {
      "background-color": "#3B82F6",
      shape: "round-rectangle",
      width: 80,
      height: 50,
      color: "#1E3A5F",
    },
  },
  {
    selector: 'node[type="nature"]',
    style: {
      "background-color": "#10B981",
      shape: "ellipse",
      width: 60,
      height: 60,
      color: "#064E3B",
    },
  },
  {
    selector: "node.focus-entity",
    style: {
      "border-width": 4,
      "border-color": "#F59E0B",
      width: 80,
      height: 70,
    },
  },
  {
    selector: "edge",
    style: {
      width: 2,
      "line-color": "#9CA3AF",
      "target-arrow-color": "#9CA3AF",
      "target-arrow-shape": "triangle",
      "curve-style": "bezier",
      label: "data(label)",
      "font-size": "9px",
      "text-rotation": "autorotate",
      color: "#6B7280",
      "text-outline-color": "#fff",
      "text-outline-width": 1,
    },
  },
  {
    selector: 'edge[direction="bidirectional"]',
    style: {
      "source-arrow-shape": "triangle",
      "source-arrow-color": "#9CA3AF",
    },
  },
  // 动态状态样式
  {
    selector: "node.active-agent",
    style: {
      "border-width": 5,
      "border-color": "#3B82F6",
      "border-style": "double",
      "shadow-blur": 15,
      "shadow-color": "#3B82F6",
      "shadow-opacity": 0.6,
      "shadow-offset-x": 0,
      "shadow-offset-y": 0,
    },
  },
  {
    selector: "node.updated",
    style: {
      "background-color": "#F97316",
      "border-color": "#EA580C",
      "border-width": 3,
    },
  },
  {
    selector: "edge.propagating",
    style: {
      width: 4,
      "line-color": "#F97316",
      "target-arrow-color": "#F97316",
      "line-style": "solid",
    },
  },
  {
    selector: "node.new-node",
    style: {
      "border-width": 3,
      "border-color": "#8B5CF6",
      "border-style": "dashed",
    },
  },
  // v3: 认知风格样式（仅对 human 节点生效）
  {
    selector: 'node[cognitionStyle="intuitive"]',
    style: {
      "border-style": "dashed",
      "border-color": "#8B5CF6",
      "border-width": 3,
    },
  },
  {
    selector: 'node[cognitionStyle="reactive"]',
    style: {
      "border-style": "dotted",
      "border-color": "#EF4444",
      "border-width": 3,
    },
  },
];

/**
 * Cytoscape 图实例管理 composable。
 *
 * 封装 Cytoscape.js 的初始化、增量添加节点/边、
 * 演变阶段的高亮和传播动画。
 */
export function useCytoscape(containerRef: Ref<HTMLElement | null>) {
  const cy = shallowRef<Core | null>(null);
  const nodeCount = ref(0);
  const edgeCount = ref(0);

  function init() {
    if (!containerRef.value) return;
    cy.value = cytoscape({
      container: containerRef.value,
      style: GRAPH_STYLE,
      layout: { name: "preset" },
      minZoom: 0.2,
      maxZoom: 3,
      wheelSensitivity: 0.3,
    });
  }

  function destroy() {
    cy.value?.destroy();
    cy.value = null;
  }

  /**
   * 增量添加实体和边（L1 构建阶段）。
   * 新节点添加后自动触发增量布局。
   */
  function addEntities(
    entities: Array<{ id: string; name: string; type: string; [k: string]: any }>,
    edges: Array<{
      source: string;
      target: string;
      relation: string;
      direction: string;
    }>
  ) {
    if (!cy.value) return;

    let addedNodes = 0;

    for (const entity of entities) {
      if (cy.value.getElementById(entity.id).length > 0) continue;
      cy.value.add({
        group: "nodes",
        data: {
          id: entity.id,
          label: entity.name,
          type: entity.type,
          status: entity.initial_status || entity.status || "",
        },
      });
      // 短暂高亮新节点
      const node = cy.value.getElementById(entity.id);
      node.addClass("new-node");
      setTimeout(() => node.removeClass("new-node"), 3000);
      addedNodes++;
    }

    for (const edge of edges) {
      const edgeId = `${edge.source}-${edge.target}-${edge.relation}`;
      if (cy.value.getElementById(edgeId).length > 0) continue;
      // 确保源和目标节点存在
      if (
        cy.value.getElementById(edge.source).length === 0 ||
        cy.value.getElementById(edge.target).length === 0
      ) {
        continue;
      }
      cy.value.add({
        group: "edges",
        data: {
          id: edgeId,
          source: edge.source,
          target: edge.target,
          label: edge.relation,
          direction: edge.direction,
        },
      });
    }

    nodeCount.value = cy.value.nodes().length;
    edgeCount.value = cy.value.edges().length;

    // 增量布局
    if (addedNodes > 0) {
      runLayout();
    }
  }

  /**
   * 加载完整的世界网络（L2 演变开始时）。
   */
  function loadFullGraph(
    entities: Array<{ id: string; name: string; type: string; status?: string; tags?: any; cognition_style?: string }>,
    edges: Array<{
      source: string;
      target: string;
      relation: string;
      direction: string;
    }>
  ) {
    if (!cy.value) return;
    cy.value.elements().remove();

    for (const entity of entities) {
      cy.value.add({
        group: "nodes",
        data: {
          id: entity.id,
          label: entity.name,
          type: entity.type,
          status: entity.status || "",
          cognitionStyle: entity.cognition_style || "strategic",
        },
      });
    }

    for (const edge of edges) {
      const edgeId = `${edge.source}-${edge.target}-${edge.relation}`;
      if (
        cy.value.getElementById(edge.source).length === 0 ||
        cy.value.getElementById(edge.target).length === 0
      ) {
        continue;
      }
      cy.value.add({
        group: "edges",
        data: {
          id: edgeId,
          source: edge.source,
          target: edge.target,
          label: edge.relation,
          direction: edge.direction,
        },
      });
    }

    nodeCount.value = cy.value.nodes().length;
    edgeCount.value = cy.value.edges().length;

    runLayout();
  }

  /** 运行力导向布局 */
  function runLayout() {
    if (!cy.value) return;
    cy.value
      .layout({
        name: "cose-bilkent",
        animate: true,
        animationDuration: 800,
        fit: true,
        padding: 50,
        randomize: cy.value.nodes().length <= 5,
        nodeRepulsion: 8000,
        idealEdgeLength: 120,
        edgeElasticity: 0.45,
        nestingFactor: 0.1,
        gravity: 0.25,
        numIter: 2500,
        tile: true,
      } as any)
      .run();
  }

  /** 高亮激活的 Agent 节点 */
  function highlightAgents(agentIds: string[]) {
    if (!cy.value) return;
    for (const id of agentIds) {
      cy.value.getElementById(id).addClass("active-agent");
    }
  }

  /** Agent 执行动作时的脉冲动画 */
  function pulseAgent(agentId: string, targetEntities: string[]) {
    if (!cy.value) return;
    const node = cy.value.getElementById(agentId);

    // 脉冲效果
    node.animate(
      { style: { width: 100, height: 70 } },
      {
        duration: 300,
        complete: () => {
          node.animate({ style: { width: 80, height: 50 } }, { duration: 300 });
        },
      }
    );

    // 目标边短暂高亮
    for (const targetId of targetEntities) {
      const targetNode = cy.value.getElementById(targetId);
      if (targetNode.length === 0) continue;
      const connEdges = node.edgesWith(targetNode);
      connEdges.addClass("propagating");
      setTimeout(() => connEdges.removeClass("propagating"), 2000);
    }
  }

  /** 传播效果可视化 */
  function showPropagation(entityUpdates: EntityUpdate[]) {
    if (!cy.value) return;

    for (const update of entityUpdates) {
      const node = cy.value.getElementById(update.entity_id);
      if (node.length === 0) continue;

      // 更新节点数据
      node.data("status", update.new_status);
      node.addClass("updated");
      setTimeout(() => node.removeClass("updated"), 3000);

      // 高亮因果边
      for (const causeId of update.caused_by || []) {
        const causeNode = cy.value.getElementById(causeId);
        if (causeNode.length === 0) continue;
        const edges = causeNode.edgesWith(node);
        edges.addClass("propagating");
        setTimeout(() => edges.removeClass("propagating"), 2500);
      }
    }
  }

  /** 清除所有 tick 高亮 */
  function clearTickHighlights() {
    if (!cy.value) return;
    cy.value.elements().removeClass("active-agent propagating updated");
  }

  /** 居中适应 */
  function fitView() {
    cy.value?.fit(undefined, 50);
  }

  /** v3: 根据网络分析中心性调整节点大小 */
  function applyNetworkMetrics(nodeMetrics: Record<string, { degree: number; betweenness: number; closeness: number }>) {
    if (!cy.value) return;
    const values = Object.values(nodeMetrics).map(m => m.betweenness);
    const max = Math.max(...values, 0.001);
    for (const [nodeId, metrics] of Object.entries(nodeMetrics)) {
      const node = cy.value.getElementById(nodeId);
      if (node.length) {
        const scale = 0.7 + (metrics.betweenness / max) * 0.6; // 0.7x ~ 1.3x
        const baseW = node.data("type") === "human" ? 80 : 60;
        const baseH = node.data("type") === "human" ? 50 : 60;
        node.style({ width: baseW * scale, height: baseH * scale });
      }
    }
  }

  /** 获取点击的节点数据 */
  function onNodeClick(callback: (nodeData: any) => void) {
    cy.value?.on("tap", "node", (evt) => {
      callback(evt.target.data());
    });
  }

  return {
    cy,
    nodeCount,
    edgeCount,
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
  };
}
