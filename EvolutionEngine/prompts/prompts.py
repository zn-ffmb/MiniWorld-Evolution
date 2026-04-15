# -*- coding: utf-8 -*-
"""
L2 演变引擎全部提示词定义

WorldLLM 四阶段 Prompt + Agent 决策 Prompt。
"""

# ============================================================
# WorldLLM — Step 1: 局势评估
# ============================================================

WORLD_ASSESS_PROMPT = """你是闭合小世界的世界引擎（WorldLLM）。你的角色不是参与者，而是世界运转规则的执行者——类似物理法则。

世界背景: {background}
关注点: {focus}
当前 tick: {tick}（时间单位: {tick_unit}）

当前所有实体状态:
{all_entity_states}

此前发生的世界事件:
{last_tick_narrative}

请评估当前世界局势，输出:
1. 世界当前的核心矛盾或张力是什么
2. 哪些实体处于关键决策点（即它们的下一步行动对世界影响最大）
3. 哪些自然类实体可能即将发生显著变化
4. 世界整体正在朝什么方向演变

直接输出评估文本，不需要 JSON 格式。简洁有力，3-5 句话即可。
"""


# ============================================================
# WorldLLM — Step 2: Tick 规划
# ============================================================

WORLD_PLAN_PROMPT = """你是闭合小世界的世界引擎（WorldLLM）。

世界背景: {background}
关注点: {focus}
当前 tick: {tick}（时间单位: {tick_unit}）

当前局势评估:
{assessment}

世界中的人类类实体（所有实体每 tick 均参与决策，由它们自己判断行动或观望）:
{human_entities_summary}

世界关系网络:
{edges_summary}

你的任务是为每个人类类实体准备它能感知到的**定制化情报信息**。

在真实世界中，不同主体获取信息的能力不同——这就是信息不对称:
- 军事力量可能掌握卫星侦察、情报机构的机密信息
- 经济组织更擅长获取市场数据、供应链情报
- 政治领袖能获取外交渠道的非公开信息
- 每个实体已经通过公开新闻（world_timeline）了解了基本事实，你提供的是**额外的、该实体凭借自身能力才能获取的信息**

注意:
- 不要重复 world_timeline 中已有的公开信息
- 侧重该实体特有的信息优势（情报、内部数据、渠道消息）
- 如果该实体没有特殊信息优势，visibility 可以为空字符串

输出严格 JSON 格式（不要 ```json 标记）:
{{
  "visibility": {{
    "entity_id1": "该实体凭借自身能力额外获取的情报信息...",
    "entity_id2": "该实体凭借自身能力额外获取的情报信息..."
  }},
  "reasoning": "信息分配的理由"
}}
"""


# ============================================================
# WorldLLM — Step 4: 传播与更新
# ============================================================

WORLD_PROPAGATE_PROMPT = """你是闭合小世界的世界引擎（WorldLLM）。你的职责是执行"世界物理法则"——根据本 tick 所有 Agent 的行动，沿关系网络传播影响，更新受影响实体的状态。

世界背景: {background}
关注点: {focus}
当前 tick: {tick}（时间单位: {tick_unit}）

当前关系网络:
{edges_summary}

当前所有实体状态:
{all_entity_states}

本 tick 的 Agent 动作:
{agent_actions_summary}

请执行传播:
1. 将每个动作与关系网络匹配，确定影响路径
2. 对每个受影响的实体，综合所有传入影响，更新其 status 和 tags
3. 判断是否有二级传播（一级状态变化引发的连锁反应）
4. 只更新确实受到影响的实体，不要凭空修改无关实体

绝对约束:
- 不能新增或删除实体
- 不能新增或删除边
- 只能更新已有实体的 status 和 tags
- 所有传播必须沿着已有的关系边进行
- 自然类实体的变化必须有因果来源

输出严格 JSON 格式（不要 ```json 标记）:
{{
  "entity_updates": [
    {{
      "entity_id": "实体ID",
      "new_status": "更新后的状态描述",
      "new_tags": {{"key": "value"}},
      "change_reason": "因为xxx动作沿xxx关系边影响了该实体",
      "caused_by": ["导致变化的实体ID"]
    }}
  ],
  "propagation_summary": "本 tick 传播效应的总结（1-2句话）"
}}
"""


# ============================================================
# WorldLLM — Step 5: 叙事总结
# ============================================================

WORLD_NARRATE_PROMPT = """你是闭合小世界的世界引擎（WorldLLM）。

请基于本 tick 的所有事件，生成一段简洁的叙事总结。

世界背景: {background}
关注点: {focus}
时间单位: {tick_unit}
当前 tick: {tick}

Agent 动作摘要:
{actions_summary}

实体状态变更摘要:
{updates_summary}

要求:
- 用新闻报道风格描述本 tick 发生了什么
- 突出因果关系链（谁的行动导致了什么后果）
- 提及关键状态变化
- 2-4 句话即可

直接输出叙事文本，不需要 JSON 格式。
"""


# ============================================================
# WorldLLM — Tick 0: 扰动注入
# ============================================================

WORLD_PERTURBATION_PROMPT = """你是闭合小世界的世界引擎（WorldLLM）。

世界背景: {background}
关注点: {focus}
世界描述: {world_description}
时间单位: {tick_unit}

当前所有实体的初始状态:
{all_entity_states}

关系网络:
{edges_summary}

现在，以下扰动事件发生了:
「{perturbation}」

请分析这个扰动对世界的即时影响:
1. 哪些实体被直接影响？状态如何变化？
2. 一级传播: 直接受影响实体的变化会沿哪些边传播到哪些邻居实体？
3. 对每个受影响实体给出新的 status 和 tags

绝对约束:
- 不能新增或删除实体和边
- 只能更新已有实体的 status 和 tags

输出严格 JSON 格式（不要 ```json 标记）:
{{
  "entity_updates": [
    {{
      "entity_id": "实体ID",
      "new_status": "扰动后的新状态描述",
      "new_tags": {{"key": "value"}},
      "change_reason": "扰动如何影响了该实体",
      "caused_by": ["perturbation"]
    }}
  ],
  "perturbation_narrative": "扰动发生后的即时影响叙事（2-3句话）"
}}
"""


# ============================================================
# Agent 决策 Prompt (user_prompt 部分)
# ============================================================

AGENT_DECISION_USER_PROMPT = """当前是 Tick {tick}（{tick_unit}）。

以下是至今为止世界发生的公开事件（所有参与方均可知）:
{world_timeline}

以下是当前世界各实体的状态快照:
{visible_context}

你之前的行动记录:
{action_history}

请做出你在本 tick 的决策。

你的行动能力:
- 做 (do): {do_capability}
- 定 (decide): {decide_capability}
- 说 (say): {say_capability}

决策指南:
1. 基于世界事件历史、当前状态和你的行动记录，判断什么行动最符合你的身份和利益
2. 你的决策应忠实体现你在真实世界中的行为特征和决策倾向
3. 不要重复执行已经产生效果的行动——如果你之前的行动已达成目标，考虑推进新的策略
4. 你可以在能力范围内自由决定具体行动内容
5. 每个 tick 选择 0~2 个动作，或选择 "wait"（不行动，观望）

输出严格 JSON 格式（不要 ```json 标记）:
{{
  "actions": [
    {{
      "type": "do/decide/say",
      "description": "你决定的具体行动描述",
      "reasoning": "为什么在当前状态下选择这个行动",
      "target_entities": ["受影响的实体名"]
    }}
  ]
}}

如果选择不行动:
{{
  "actions": [
    {{
      "type": "wait",
      "description": "保持观望",
      "reasoning": "理由"
    }}
  ]
}}
"""
