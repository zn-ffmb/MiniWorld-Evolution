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
# Agent 决策 Prompt — v3 策略推理版 (user_prompt 部分)
# ============================================================

AGENT_DECISION_USER_PROMPT = """当前是 Tick {tick}（{tick_unit}）。

【公开事件时间线】（所有参与方均可知）
{world_timeline}

【当前世界状态快照】
{visible_context}

【你的行动记录】
{action_history}

【你的行动能力】
- 做 (do): {do_capability}
- 定 (decide): {decide_capability}
- 说 (say): {say_capability}

请按以下步骤进行策略推理，然后做出决策:

第一步 — 局势研判:
基于公开事件和当前状态，评估世界正在朝什么方向发展。当前局势对你的核心利益有什么影响？

第二步 — 关键方预判（前瞻 1 步）:
列出 2-3 个与你利益最相关的其他参与方（无论是竞争方、合作方还是博弈方）。在当前局势下，他们最可能采取什么行动？为什么？（从他们各自的立场和利益出发思考）

第三步 — 行动-反应评估:
对于你考虑的每个可能行动，推演:
  - 你执行该行动后，相关方最可能的反应是什么？
  - 那些反应对你的核心利益影响如何？
  - 不行动（wait）的后果是什么？局势会自动好转还是恶化？

第四步 — 最终决策:
综合以上推理，选择最符合你利益的行动方案（0~2 个动作，或 wait）。

注意:
- 你的决策应忠实体现你在真实世界中的行为特征和决策倾向
- 不要重复执行已经产生效果的行动——如果你之前的行动已达成目标，考虑推进新的策略
- 你可以在能力范围内自由决定具体行动内容

输出严格 JSON 格式（不要 ```json 标记）:
{{
  "situation_assessment": "局势研判（1-2 句）",
  "key_party_predictions": [
    {{
      "party": "相关方名称",
      "relationship": "竞争/合作/博弈/中立",
      "predicted_action": "预计行动",
      "reasoning": "为什么"
    }}
  ],
  "action_evaluation": [
    {{
      "candidate_action": "你考虑的行动",
      "expected_reactions": "相关方预计反应",
      "net_impact_on_interests": "对你利益的净影响"
    }}
  ],
  "counterfactual": "如果你不行动，局势会如何发展",
  "actions": [
    {{
      "type": "do/decide/say/wait",
      "description": "具体行动描述",
      "reasoning": "基于上述推理的最终理由",
      "target_entities": ["受影响的实体名"]
    }}
  ]
}}

如果选择不行动:
{{
  "situation_assessment": "局势研判",
  "key_party_predictions": [...],  
  "action_evaluation": [],
  "counterfactual": "不行动的后果分析",
  "actions": [
    {{
      "type": "wait",
      "description": "保持观望",
      "reasoning": "基于推理的理由"
    }}
  ]
}}
"""


# ============================================================
# Agent 审议 Prompt — v3 深度审议（红队审视）
# ============================================================

AGENT_DELIBERATION_PROMPT = """你是 {entity_name}，现在进入深度审议阶段。

你在策略推理阶段的分析:
局势研判: {situation_assessment}

对手推演:
{opponent_predictions_text}

反事实分析: {counterfactual}

你的候选行动方案:
{candidate_actions_text}

你之前的行动记录:
{action_history}

请从以下角度审议每个候选方案:

1. 关键方视角（换位审视）: 站在对你影响最大的其他参与方角度，你的这个行动有什么弱点或不利影响？他们会如何应对？
2. 历史一致性: 该行动是否与你之前的行为模式和公开立场一致？突然转变是否会损害信誉？
3. 时机评估: 现在是执行该行动的最佳时机吗？等一个 tick 是否能获得更好的条件？
4. 风险评估: 最坏情况下会发生什么？你能承受那个结果吗？

经过审议后，你可以:
- 维持原方案（如果经得起审视）
- 调整行动（改变力度、目标或措辞）
- 放弃行动改为观望（如果风险过高或时机不对）

输出严格 JSON 格式（不要 ```json 标记）:
{{
  "deliberation": [
    {{
      "option": "方案描述",
      "red_team_critique": "换位审视：关键方视角的弱点分析",
      "historical_consistency": "与历史行为的一致性",
      "timing": "时机评估",
      "risk": "最坏情况"
    }}
  ],
  "final_decision": "维持/调整/放弃",
  "actions": [
    {{
      "type": "do/decide/say/wait",
      "description": "审议后的最终行动",
      "reasoning": "综合审议后的决策理由",
      "target_entities": ["受影响的实体名"]
    }}
  ]
}}
"""


# ============================================================
# Agent 决策 Prompt — 直觉型 (intuitive)
# ============================================================

AGENT_DECISION_INTUITIVE_PROMPT = """当前是 Tick {tick}（{tick_unit}）。

【近期发生的公开事件】
{world_timeline}

【当前世界状态快照】
{visible_context}

【你的行动记录】
{action_history}

【你的行动能力】
- 做 (do): {do_capability}
- 定 (decide): {decide_capability}
- 说 (say): {say_capability}

请基于你的经验和直觉做出判断:

1. 当前局势让你最担心或最关注什么？（凭直觉，不需要系统化分析）
2. 你觉得接下来局势会怎么发展？（基于你的经验判断）
3. 你打算怎么做？为什么？

注意:
- 你更依靠经验和直觉做决策，而不是系统化的策略分析
- 你可能会被最近发生的事件过度影响（这很正常）
- 你可能高估自己影响局势的能力
- 你也可以选择不行动（wait），如果你觉得当前不需要做什么
- 每个 tick 选择 0~2 个动作，或选择 wait

输出严格 JSON 格式（不要 ```json 标记）:
{{
  "gut_feeling": "当前局势给你最直觉的感受（1句话）",
  "expectation": "你觉得接下来会怎样",
  "actions": [
    {{
      "type": "do/decide/say/wait",
      "description": "你决定做什么",
      "reasoning": "为什么（基于你的经验和判断）",
      "target_entities": ["受影响的实体名"]
    }}
  ]
}}
"""


# ============================================================
# Agent 决策 Prompt — 反应型 (reactive)
# ============================================================

AGENT_DECISION_REACTIVE_PROMPT = """当前是 Tick {tick}（{tick_unit}）。

【近期发生的公开事件】
{world_timeline}

【当前世界状态】
{visible_context}

【你之前的集体行为】
{action_history}

【你的行动能力】
- 做 (do): {do_capability}
- 定 (decide): {decide_capability}
- 说 (say): {say_capability}

你代表的是一个群体的集体反应。请基于当前局势做出反应:

1. 当前最引发群体关注或情绪反应的事件是什么？
2. 群体的主导情绪是什么？（如: 愤怒、恐慌、焦虑、乐观、漠不关心、失望、团结...）
3. 这种情绪最可能驱动什么集体行为？

注意:
- 群体反应主要受情绪和叙事驱动，不是理性分析
- 最近的、具象的、有情绪冲击力的事件影响最大
- 群体可能存在滞后反应（慢半拍）或过度反应（恐慌性行为）
- 群体内部不一定统一——可能存在分裂
- "别人都在做"可能比"这样做是否合理"更影响群体行为
- 你也可以选择不行动（wait），如果群体当前没有强烈反应
- 每个 tick 选择 0~2 个动作，或选择 wait

输出严格 JSON 格式（不要 ```json 标记）:
{{
  "emotional_trigger": "最引发群体情绪的事件",
  "dominant_emotion": "主导情绪",
  "emotion_intensity": "低/中/高/极端",
  "actions": [
    {{
      "type": "do/decide/say/wait",
      "description": "群体最可能的集体行为",
      "reasoning": "为什么群体会这样反应",
      "target_entities": ["受影响的实体名"]
    }}
  ]
}}
"""
