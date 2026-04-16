import type { EntityData, EdgeData, EntityUpdate } from "./entity";

/** SSE 事件通用结构 */
export interface SSEEvent {
  event: string;
  data: any;
  timestamp: Date;
}

/** build:start */
export interface BuildStartData {
  background: string;
  focus: string;
  max_iterations: number;
}

/** build:entities_extracted */
export interface BuildEntitiesExtractedData {
  new_entities: Array<{
    id: string;
    name: string;
    type: string;
    description: string;
  }>;
  updated_entities: string[];
  new_edges: Array<{
    source: string;
    target: string;
    relation: string;
    direction: string;
    description: string;
  }>;
}

/** build:convergence */
export interface BuildConvergenceData {
  converged: boolean;
  report: string;
}

/** build:complete */
export interface BuildCompleteData {
  world_id: string;
  snapshot_summary: {
    human_entity_count: number;
    nature_entity_count: number;
    edge_count: number;
    build_iterations: number;
    world_description: string;
    tick_unit: string;
  };
}

/** evolve:start */
export interface EvolveStartData {
  world_id: string;
  perturbation: string;
  max_ticks: number;
  tick_unit: string;
  entities: EntityData[];
  edges: EdgeData[];
}

/** evolve:plan */
export interface EvolvePlanData {
  tick: number;
  active_agents: string[];
  execution_order: string[];
  visibility: Record<string, string>;
}

/** evolve:agent_action */
export interface EvolveAgentActionData {
  tick: number;
  agent_id: string;
  agent_name: string;
  action_type: string;
  action_description: string;
  reasoning: string;
  target_entities: string[];
}

/** evolve:propagation */
export interface EvolvePropagationData {
  tick: number;
  entity_updates: EntityUpdate[];
  propagation_summary: string;
}

/** evolve:narrative */
export interface EvolveNarrativeData {
  tick: number;
  narrative: string;
}

/** evolve:equilibrium */
export interface EvolveEquilibriumData {
  tick: number;
  reason: string;
}

/** evolve:complete */
export interface EvolveCompleteData {
  total_ticks: number;
  termination_reason?: string;
  summary: {
    total_agent_actions: number;
    total_entity_updates: number;
    most_active_agent: string;
    most_changed_entity: string;
  };
}
