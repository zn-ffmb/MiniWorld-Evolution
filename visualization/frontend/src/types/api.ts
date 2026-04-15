/** API 请求/响应类型 */

export interface BuildRequest {
  background: string;
  focus: string;
  max_iterations?: number;
}

export interface BuildResponse {
  task_id: string;
  status: string;
  stream_url: string;
}

export interface EvolveRequest {
  world_id: string;
  perturbation: string;
  max_ticks?: number;
}

export interface EvolveResponse {
  task_id: string;
  status: string;
  stream_url: string;
}

export interface WorldSummary {
  world_id: string;
  background: string;
  focus: string;
  human_entity_count: number;
  nature_entity_count: number;
  edge_count: number;
  created_at: string;
  world_description: string;
}

export interface WorldListResponse {
  worlds: WorldSummary[];
}
