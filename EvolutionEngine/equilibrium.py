# -*- coding: utf-8 -*-
"""
动态均衡检测器 — L2 v3 升级 E

通过算法检测世界是否趋向均衡，提供比 WorldLLM 判断更可靠的终止条件。

三种检测机制:
  1. 行动衰减 — 所有 Agent 连续 N 轮 wait
  2. 状态收敛 — 实体变化幅度逐 Tick 递减
  3. 循环检测 — 行动模式出现周期性重复
"""

from typing import Tuple, List
from loguru import logger

from EvolutionEngine.state.models import EvolutionState, TickRecord, AgentAction


class EquilibriumDetector:
    """
    动态均衡检测器。

    理论基础:
      - 纳什均衡: 所有参与者都不愿单方面改变策略时，博弈达到均衡
      - 李雅普诺夫稳定性: 系统状态偏差持续减小，则趋向稳态
      - 吸引子理论: 检测固定点收敛或极限环（周期循环）
    """

    def __init__(self, window_size: int = 3):
        """
        Args:
            window_size: 检测窗口大小（连续 N 个 tick）
        """
        self.window_size = window_size

    def check(self, state: EvolutionState) -> Tuple[bool, str]:
        """
        检测世界是否趋向均衡。

        Returns:
            (is_equilibrium, reason)
        """
        # 排除 tick 0（扰动注入），只分析 tick >= 1 的记录
        evolution_ticks = [r for r in state.timeline if r.tick >= 1]

        if len(evolution_ticks) < self.window_size:
            return False, ""

        recent_ticks = evolution_ticks[-self.window_size:]

        # 检测 1: 行动衰减
        exhaustion, exhaustion_reason = self._check_action_exhaustion(recent_ticks)
        if exhaustion:
            return True, exhaustion_reason

        # 检测 2: 状态收敛
        convergence, convergence_reason = self._check_state_convergence(recent_ticks)
        if convergence:
            return True, convergence_reason

        # 检测 3: 循环检测（需要较长历史）
        if len(evolution_ticks) >= self.window_size * 2:
            cycle, cycle_reason = self._check_cycle(evolution_ticks)
            if cycle:
                return True, cycle_reason

        return False, ""

    def _check_action_exhaustion(self, recent_ticks: List[TickRecord]) -> Tuple[bool, str]:
        """
        检测 1: 所有 Agent 连续 N tick 全部 wait。

        当没有任何 Agent 有动力改变现状时，世界到达准纳什均衡。
        """
        for record in recent_ticks:
            actions = record.agent_actions or []
            has_real_action = any(
                (a.action_type if isinstance(a, AgentAction) else a.get("action_type", ""))
                != "wait"
                for a in actions
            )
            if has_real_action:
                return False, ""

        tick_range = f"Tick {recent_ticks[0].tick}-{recent_ticks[-1].tick}"
        reason = (
            f"行动衰减均衡: 所有 Agent 在 {tick_range} 连续 "
            f"{self.window_size} 轮未采取行动，无方有动力改变现状"
        )
        return True, reason

    def _check_state_convergence(self, recent_ticks: List[TickRecord]) -> Tuple[bool, str]:
        """
        检测 2: 实体状态变更数量连续递减（趋向稳态）。

        当每轮变化幅度持续缩小时，系统正在收敛到稳态。
        """
        update_counts = [len(r.entity_updates) for r in recent_ticks]

        # 全部为 0: 完全静止
        if all(c == 0 for c in update_counts):
            tick_range = f"Tick {recent_ticks[0].tick}-{recent_ticks[-1].tick}"
            return True, f"状态静止: {tick_range} 连续 {self.window_size} 轮无实体变更"

        # 严格递减: 变化幅度逐轮缩小
        is_decreasing = all(
            update_counts[i] > update_counts[i + 1]
            for i in range(len(update_counts) - 1)
        )

        if is_decreasing and update_counts[-1] <= 1:
            tick_range = f"Tick {recent_ticks[0].tick}-{recent_ticks[-1].tick}"
            return True, (
                f"状态收敛: {tick_range} 实体变更数持续递减 "
                f"({' → '.join(str(c) for c in update_counts)})，趋向稳态"
            )

        return False, ""

    def _check_cycle(self, evolution_ticks: List[TickRecord]) -> Tuple[bool, str]:
        """
        检测 3: 行动模式的周期性循环。

        将每个 Tick 的 Agent 行动组合编码为指纹，检测重复模式。
        如果检测到周期，说明系统进入了僵局循环。
        """
        # 编码每个 Tick 的行动模式指纹
        fingerprints = []
        for record in evolution_ticks:
            actions = record.agent_actions or []
            action_items = []
            for a in actions:
                if isinstance(a, AgentAction):
                    if a.action_type != "wait":
                        action_items.append(f"{a.agent_id}:{a.action_type}")
                elif isinstance(a, dict):
                    if a.get("action_type", "") != "wait":
                        action_items.append(f"{a.get('agent_id', '')}:{a.get('action_type', '')}")
            fingerprints.append("|".join(sorted(action_items)) if action_items else "idle")

        # 检测周期 2: ABAB...
        if len(fingerprints) >= 4:
            last4 = fingerprints[-4:]
            if last4[0] == last4[2] and last4[1] == last4[3] and last4[0] != last4[1]:
                return True, (
                    f"周期循环(周期=2): 检测到 Tick {evolution_ticks[-4].tick}-"
                    f"{evolution_ticks[-1].tick} 行动模式出现 ABAB 重复"
                )

        # 检测周期 3: ABCABC...
        if len(fingerprints) >= 6:
            last6 = fingerprints[-6:]
            if (last6[0] == last6[3] and last6[1] == last6[4] and last6[2] == last6[5]
                    and len(set(last6[:3])) > 1):
                return True, (
                    f"周期循环(周期=3): 检测到 Tick {evolution_ticks[-6].tick}-"
                    f"{evolution_ticks[-1].tick} 行动模式出现 ABCABC 重复"
                )

        return False, ""
