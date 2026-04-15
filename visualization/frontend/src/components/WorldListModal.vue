<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="历史世界记录"
    width="650px"
    destroy-on-close
  >
    <el-table :data="worlds" v-loading="loading" empty-text="暂无世界记录" size="small">
      <el-table-column prop="background" label="背景" width="120" />
      <el-table-column prop="focus" label="关注点" width="100" />
      <el-table-column label="实体" width="80">
        <template #default="{ row }">
          {{ row.human_entity_count + row.nature_entity_count }}
        </template>
      </el-table-column>
      <el-table-column prop="edge_count" label="关系" width="60" />
      <el-table-column prop="created_at" label="创建时间" width="160">
        <template #default="{ row }">
          {{ row.created_at?.slice(0, 19).replace("T", " ") }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click="handleLoad(row)">
            加载
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";
import { listWorlds, getWorld } from "../api/client";
import { useWorldStore } from "../composables/useWorldStore";
import { useCytoscapeGlobal } from "./cytoscapeProvider";
import type { WorldSummary } from "../types/api";

const props = defineProps<{ visible: boolean }>();
const emit = defineEmits(["update:visible"]);

const { state, addLog, reset } = useWorldStore();
const cyGlobal = useCytoscapeGlobal();

const worlds = ref<WorldSummary[]>([]);
const loading = ref(false);

watch(
  () => props.visible,
  async (v) => {
    if (v) {
      loading.value = true;
      try {
        const resp = await listWorlds();
        worlds.value = resp.worlds;
      } catch (err) {
        console.error(err);
      } finally {
        loading.value = false;
      }
    }
  }
);

async function handleLoad(row: WorldSummary) {
  try {
    const data = await getWorld(row.world_id);
    reset();
    state.phase = "built";
    state.worldId = row.world_id;
    state.background = row.background;
    state.focus = row.focus;
    state.humanCount = row.human_entity_count;
    state.natureCount = row.nature_entity_count;
    state.totalEntities = row.human_entity_count + row.nature_entity_count;
    state.totalEdges = row.edge_count;
    state.worldDescription = data.world_description || "";
    state.tickUnit = data.tick_unit || "";
    state.converged = true;

    // 加载到图上
    if (cyGlobal.loadFullGraph && data.entities && data.edges) {
      const entities = data.entities.map((e: any) => ({
        id: e.id,
        name: e.name,
        type: e.type,
        status: e.initial_status || "",
      }));
      const edges = data.edges.map((e: any) => ({
        source: e.source,
        target: e.target,
        relation: e.relation,
        direction: e.direction,
      }));
      cyGlobal.loadFullGraph(entities, edges);
    }

    addLog("success", `已加载世界: ${row.world_id}`);
    emit("update:visible", false);
  } catch (err: any) {
    addLog("error", `加载世界失败: ${err.message}`);
  }
}
</script>
