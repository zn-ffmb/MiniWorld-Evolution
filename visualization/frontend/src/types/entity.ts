/** 实体（节点）数据 */
export interface EntityData {
  id: string;
  name: string;
  type: "human" | "nature";
  description?: string;
  status?: string;
  tags?: Record<string, string>;
  initial_status?: string;
  initial_tags?: Record<string, string>;
  evidence_freshness?: string;
  evidence_date_range?: string;
  status_trend?: string;
  cognition_style?: string;
}

/** 关系边数据 */
export interface EdgeData {
  source: string;
  target: string;
  relation: string;
  direction: "directed" | "bidirectional";
  description?: string;
}

/** 实体状态更新 */
export interface EntityUpdate {
  entity_id: string;
  entity_name: string;
  old_status: string;
  new_status: string;
  old_tags?: Record<string, string>;
  new_tags?: Record<string, string>;
  change_reason: string;
  caused_by: string[];
}
