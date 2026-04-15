# MiniWorld-Evolution

基于真实事件构建闭合小世界，并通过扰动模拟未来演变的推演系统。

![可视化界面截图](screenshot.png)

## 架构概览

```
真实世界事件 ──→ [L1 WorldEngine] ──→ 闭合小世界快照 ──→ [L2 EvolutionEngine] ──→ 演变时间线
                   5阶段迭代管线          实体+关系图谱      WorldLLM × Agent 逐Tick推演
```

### L1 WorldEngine — 闭合小世界构建

五阶段迭代管线，每轮直到三级收敛检测通过才终止：

```
输入: 背景 + 关注点
        │
Phase 1  SearchPlanNode       → 假设驱动，生成三维度定向搜索任务
Phase 2  SearchExecutionNode  → 并行搜索 (Tavily / Bocha)
Phase 3  EntityExtractionNode → 实体 & 关系提取 + 证据溯源校验
Phase 4  WorldMergeNode       → 实体图谱增量融合（去重 & 合并）
Phase 5  ConvergenceCheckNode → 三级收敛检测:
              ├── L1 结构完整性（NetworkX 弱连通图 + 孤立节点）
              ├── L2 功能完整性（角色覆盖 & 关系密度）
              └── L3 语义完整性（LLM 反思，仅 L1+L2 通过后执行）
              ↓ 收敛后单次执行
Phase 6  PromptGenerationNode → 为 human 类实体生成 agent_prompt + action_space
Phase 7  WorldMetaNode        → 生成世界元信息（标题 / 描述 / tick_unit 等）
Phase 8  SnapshotExportNode   → 导出 WorldSnapshot（JSON + Markdown）
```

### L2 EvolutionEngine — 闭合小世界演变

WorldLLM（世界规则引擎）× AgentRunner（Agent 决策执行器）逐 Tick 协作推演：

```
输入: WorldSnapshot + 扰动事件
        │
Tick 0   WorldLLM.inject_perturbation → 扰动即时冲击，初始化实体运行时状态
        │
        ▼  ── 循环 max_ticks 次 ──────────────────────────────────
Step 1   WorldLLM.assess    → 局势评估（核心矛盾 & 关键决策实体）
Step 2   WorldLLM.plan      → 信息不对称分发（为每个 Agent 生成专属情报）
Step 3   AgentRunner × N    → 所有 human 类 Agent 并发自主决策
                               每个 Agent 获得: 公开事件时间线 + 专属情报 + 历史行动
                               自主选择: do（执行）/ decide（决策）/ say（声明）/ wait（观望）
Step 4   WorldLLM.propagate → 将 Agent 行动传播为实体状态 & 关系更新
Step 5   WorldLLM.narrate   → 生成本 Tick 叙事摘要 & 检测演变是否终止
        │
        ▼  ─────────────────────────────────────────────────────
TimelineExporter → 导出 EvolutionTimeline（JSON + Markdown）
```

### 实体双态

| 类型 | 描述 | L2 行为 |
|------|------|---------|
| `human` | 具有主观意志的参与者（国家、组织、人物等） | 由 AgentRunner 驱动，自主 LLM 决策 |
| `nature` | 客观自然/市场状态（油价、气候、舆论等） | 由 WorldLLM 直接更新，无自主行动 |

### 核心原则

- **闭合世界约束**：全部推理基于 L1 搜索到的真实证据，**LLM 不允许创造情报**
- **Agent 自主决策**：每个 human 类 Agent 自行判断是否行动及行动方式，WorldLLM 不指定具体行为
- **信息不对称**：同一 Tick 内，不同 Agent 依据自身角色能力获取差异化情报（军事情报 / 市场数据 / 外交电报），再加上相同的公开事件时间线，构成差异化决策基础
- **三级收敛验证**：结构完整性（图论连通）→ 功能完整性（角色覆盖）→ 语义完整性（LLM 反思），确保快照质量
- **WorldLLM 是裁定者而非参与者**：类比物理法则，只评估结果合理性、分发情报、传播状态，不替 Agent 做决策

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填写：

```env
# LLM API（必填）
WORLD_ENGINE_API_KEY=your_api_key
EVOLUTION_ENGINE_API_KEY=your_api_key

# 搜索 API（至少填一个）
TAVILY_API_KEY=your_tavily_key
BOCHA_API_KEY=your_bocha_key
```

### 3. 构建闭合小世界（L1）

```bash
python run_build_world.py --background "霍尔木兹海峡局势" --focus "石油价格与航运"
```

输出保存到 `worlds/` 目录。

### 4. 运行演变推演（L2）

```bash
python run_evolution.py \
  --world worlds/world_20260412_175043.json \
  --perturbation "伊朗宣布完全封锁霍尔木兹海峡" \
  --max-ticks 10
```

输出保存到 `evolutions/` 目录。

### 5. 可视化平台（可选）

```bash
# 后端
cd visualization/backend
uvicorn main:app --reload --port 8000

# 前端
cd visualization/frontend
npm install
npm run dev
```

访问 `http://localhost:5173` 使用可视化界面。

## 项目结构

```
├── WorldEngine/              # L1 闭合小世界构建引擎
│   ├── builder.py           # 构建调度中心
│   ├── nodes/               # 管线节点（搜索规划·执行·实体提取·验证·融合·收敛·Prompt生成·导出）
│   ├── search/              # 搜索协调 + 自包含 API 客户端（Tavily / Bocha）
│   │   └── vendors/         # 解耦后的搜索 API 客户端与重试工具
│   ├── state/               # 世界状态模型（Entity, Edge, WorldSnapshot）
│   ├── llms/                # LLM 客户端抽象
│   ├── prompts/             # L1 Prompt 模板
│   └── utils/               # 文本处理工具
│
├── EvolutionEngine/          # L2 闭合小世界演变引擎
│   ├── engine.py            # 演变调度中心
│   ├── world_llm.py         # 世界规则引擎（评估 + 传播）
│   ├── agent_runner.py      # Agent 决策执行器
│   ├── exporters/           # 时间线导出
│   ├── state/               # 演变状态模型
│   └── prompts/             # L2 Prompt 模板
│
├── visualization/            # Web 可视化平台
│   ├── backend/             # FastAPI + SSE 后端
│   └── frontend/            # Vue 3 + Cytoscape.js 前端
│
├── worlds/                   # L1 输出（世界快照 JSON + Markdown）
├── evolutions/               # L2 输出（演变时间线 JSON + Markdown）
├── docs/                     # 开发文档与架构说明
├── config.py                 # 全局配置（pydantic-settings，从 .env 加载）
├── run_build_world.py        # L1 命令行入口
└── run_evolution.py          # L2 命令行入口
```

## 配置说明

所有配置通过 `.env` 文件管理，支持的参数见 `config.py`：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `WORLD_ENGINE_MODEL` | `qwen-plus` | L1 构建用 LLM 模型 |
| `EVOLUTION_ENGINE_MODEL` | `qwen-plus` | L2 演变用 LLM 模型 |
| `MAX_BUILD_ITERATIONS` | `3` | L1 最大迭代次数 |
| `EVOLUTION_MAX_TICKS` | `10` | L2 最大演变轮次 |
| `EVOLUTION_AGENT_TEMPERATURE` | `0.7` | Agent 决策温度 |
| `SEARCH_CONCURRENCY` | `5` | 搜索并行线程数 |
| `BOCHA_BASE_URL` | `https://api.bocha.cn/v1/ai-search` | Bocha API 地址 |

## 致谢

本项目的搜索工具层（`WorldEngine/search/vendors/`）基于 [BettaFish](https://github.com/666ghj/BettaFish) 项目的搜索客户端与重试机制改写。感谢 BettaFish 团队的优秀开源工作。

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=zn-ffmb/MiniWorld-Evolution&type=Date)](https://star-history.com/#zn-ffmb/MiniWorld-Evolution&Date)

## License

本项目采用 [GPL-2.0](LICENSE) 许可证。
