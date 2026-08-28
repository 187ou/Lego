"""知识图谱推理引擎（增强版 - 图算法 + LLM 混合推理）

三种推理能力：
1. 多条件约束推理 — "有 A 无 B，找兼容 A 且替代 B 的零件"（图算法：约束传播）
2. 步骤链式推理   — "第 35 步和第 36 步之间可以跳过吗？"（图算法：路径分析）
3. 结构稳定性推理 — "这个位置放 1x2 板够稳固吗？"（图算法：连接度分析）

架构：
- 图算法负责：候选生成、约束过滤、排序
- LLM 负责：最终总结、自然语言生成
"""

import re
from typing import Any, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

from src.kg.graph_retriever import GraphRetriever
from src.kg.schema import (
    NodeType, RelationType,
    calc_part_compatibility, get_part_knowledge,
)


# 推理类型
REASONING_CONSTRAINT = "constraint"
REASONING_CHAIN = "chain"
REASONING_STABILITY = "stability"

# 推理系统提示
REASONING_SYSTEM_PROMPT = """你是 LEGO-Mate 知识图谱推理引擎。
你的任务是基于给定的图谱数据和推理结果，生成友好的自然语言回复。

规则：
- 严格基于提供的数据，不要编造不存在的信息
- 用中文回答，简洁清晰
- 如果信息不足，明确说明缺少什么信息
- 给出具体的零件编号和名称
"""


class GraphReasoner:
    """知识图谱推理引擎（图算法 + LLM 混合）"""

    def __init__(
        self,
        llm: BaseChatModel,
        retriever: Optional[GraphRetriever] = None,
    ):
        self.llm = llm
        self.retriever = retriever or get_graph_reasoner_retriever()

    def reason(
        self,
        query: str,
        reasoning_type: str = REASONING_CONSTRAINT,
        context: Optional[dict] = None,
        timeout: float = 30.0,
    ) -> dict:
        """
        通用图谱推理入口。

        Args:
            query: 用户查询
            reasoning_type: 推理类型（constraint / chain / stability）
            context: 额外上下文（如 set_id, has_parts, missing_parts 等）
            timeout: LLM 调用超时（秒）

        Returns:
            推理结果字典
        """
        import concurrent.futures

        context = context or {}

        try:
            # 1. 图算法推理（核心）
            if reasoning_type == REASONING_CONSTRAINT:
                result = self._reason_constraint(query, context)
            elif reasoning_type == REASONING_CHAIN:
                result = self._reason_chain(query, context)
            elif reasoning_type == REASONING_STABILITY:
                result = self._reason_stability(query, context)
            else:
                result = {"error": f"未知推理类型: {reasoning_type}"}

            # 2. LLM 总结（可选，失败不影响结果）
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(self._llm_summarize, query, result, timeout)
                    summary = future.result(timeout=timeout)
                    result["summary"] = summary
            except Exception:
                result["summary"] = result.get("conclusion", "推理完成")

            return result

        except Exception as e:
            return {
                "conclusion": f"推理引擎暂时不可用: {type(e).__name__}",
                "confidence": 0,
                "reasoning_chain": [],
                "suggestions": ["请稍后重试"],
                "risks": [],
                "missing_info": [],
            }

    def _reason_constraint(self, query: str, context: dict) -> dict:
        """多条件约束推理（图算法：约束传播）

        算法：
        1. 提取缺失零件
        2. 查找每个缺失零件的替代候选
        3. 约束过滤：排除不兼容的、用户已有的
        4. 多维度排序：兼容性 × 置信度 / 距离
        """
        set_id = context.get("set_id", "10295")
        has_parts = context.get("has_parts", [])
        missing_parts = context.get("missing_parts", [])

        # 从查询中提取零件号
        part_ids = re.findall(r"(?<!\d)(\d{4,5})(?!\d)", query)
        if not missing_parts:
            missing_parts = part_ids

        if not missing_parts:
            return {
                "conclusion": "请告诉我缺了什么零件",
                "confidence": 0,
                "reasoning_chain": [],
                "suggestions": ["例如：缺了红色2x4砖"],
                "risks": [],
                "missing_info": ["缺失零件列表"],
            }

        # 获取不兼容零件集合
        incompatible_set = set()
        for pid in has_parts:
            incompat = self.retriever.store.find_incompatible_parts(pid)
            for inc in incompat:
                incompatible_set.add(inc["part_id"])

        # 约束传播推理
        recommendations = []
        for missing_pid in missing_parts:
            # 查找替代候选
            candidates = self.retriever.find_part_alternatives(missing_pid, limit=10)

            # 约束过滤
            filtered = []
            for cand in candidates:
                cand_id = cand["part_id"]

                # 排除用户已有的
                if cand_id in has_parts:
                    continue

                # 排除不兼容的
                if cand_id in incompatible_set:
                    continue

                # 计算多维度兼容性
                compatibility = calc_part_compatibility(missing_pid, cand_id)
                cand["compatibility"] = compatibility
                cand["final_score"] = compatibility * cand.get("confidence", 1.0)

                filtered.append(cand)

            # 按最终得分排序
            filtered.sort(key=lambda x: x["final_score"], reverse=True)

            recommendations.append({
                "missing_part": missing_pid,
                "missing_name": self._lookup_part_name(missing_pid),
                "alternatives": filtered[:5],
                "total_candidates": len(filtered),
            })

        # 构建推理链
        reasoning_chain = []
        for rec in recommendations:
            if rec["alternatives"]:
                alt_names = ", ".join([a["name"] for a in rec["alternatives"][:3]])
                reasoning_chain.append(
                    f"{rec['missing_name']} 可用 {alt_names} 替代"
                )
            else:
                reasoning_chain.append(f"{rec['missing_name']} 暂无可用替代")

        # 计算整体置信度
        all_scores = []
        for rec in recommendations:
            for alt in rec["alternatives"]:
                all_scores.append(alt["final_score"])

        avg_confidence = sum(all_scores) / len(all_scores) if all_scores else 0

        return {
            "conclusion": f"为 {len(recommendations)} 个缺失零件找到替代方案",
            "confidence": round(avg_confidence, 2),
            "reasoning_chain": reasoning_chain,
            "recommendations": recommendations,
            "suggestions": [
                "选择兼容性得分最高的替代方案",
                "注意颜色匹配",
            ],
            "risks": [
                "替代零件可能影响外观",
            ] if recommendations else [],
            "missing_info": [],
        }

    def _reason_chain(self, query: str, context: dict) -> dict:
        """步骤链式推理（图算法：路径分析）

        算法：
        1. 提取步骤号
        2. 查找步骤间的路径
        3. 分析路径上的依赖关系
        """
        set_id = context.get("set_id", "10295")
        step_numbers = []

        for pattern in [r"第?\s*(\d+)\s*步", r"step\s*(\d+)", r"(\d+)步"]:
            matches = re.findall(pattern, query, re.IGNORECASE)
            step_numbers.extend([int(m) for m in matches])

        if len(step_numbers) < 2:
            return {
                "conclusion": "请提供至少两个步骤号",
                "confidence": 0,
                "reasoning_chain": [],
                "suggestions": ["例如：第35步和第36步之间可以跳过吗？"],
                "risks": [],
                "missing_info": ["步骤号"],
            }

        source_step = step_numbers[0]
        target_step = step_numbers[1]

        # 查找路径
        source_id = f"set_{set_id}_step_{source_step}"
        target_id = f"set_{set_id}_step_{target_step}"
        paths = self.retriever.find_path(source_id, target_id, max_depth=5)

        # 分析步骤依赖
        source_info = self.retriever.get_step_info(set_id, source_step)
        target_info = self.retriever.get_step_info(set_id, target_step)

        reasoning_chain = []
        if paths:
            reasoning_chain.append(
                f"步骤 {source_step} → 步骤 {target_step} 存在路径（长度 {len(paths[0])}）"
            )

            # 分析共享零件
            if source_info.get("found") and target_info.get("found"):
                source_parts = {p.get("part_id") for p in source_info.get("parts", [])}
                target_parts = {p.get("part_id") for p in target_info.get("parts", [])}
                shared = source_parts & target_parts

                if shared:
                    reasoning_chain.append(f"两个步骤共享零件: {', '.join(shared)}")
                    reasoning_chain.append("跳过可能影响结构稳定性")
                else:
                    reasoning_chain.append("两个步骤无共享零件，跳过风险较低")
        else:
            reasoning_chain.append(f"步骤 {source_step} → 步骤 {target_step} 无直接路径")

        return {
            "conclusion": f"步骤 {source_step} 到 {target_step} 的依赖分析完成",
            "confidence": 0.8 if paths else 0.5,
            "reasoning_chain": reasoning_chain,
            "path_exists": bool(paths),
            "suggestions": [
                "如果无共享零件，可以尝试跳过",
                "建议先完成前置步骤",
            ],
            "risks": [
                "跳过步骤可能导致后续无法安装",
            ] if paths else [],
            "missing_info": [],
        }

    def _reason_stability(self, query: str, context: dict) -> dict:
        """结构稳定性推理（图算法：连接度分析）

        算法：
        1. 提取零件号
        2. 分析零件的连接度（邻居数量）
        3. 评估结构强度
        """
        set_id = context.get("set_id", "10295")
        part_ids = re.findall(r"(?<!\d)(\d{4,5})(?!\d)", query)

        if not part_ids:
            return {
                "conclusion": "请告诉我具体零件号",
                "confidence": 0,
                "reasoning_chain": [],
                "suggestions": ["例如：这个位置放3001够稳固吗？"],
                "risks": [],
                "missing_info": ["零件号"],
            }

        analysis = []
        for part_id in part_ids:
            part_info = self.retriever.get_part_info(part_id)
            if not part_info.get("found"):
                analysis.append({
                    "part_id": part_id,
                    "found": False,
                })
                continue

            # 获取知识库中的物理知识
            knowledge = get_part_knowledge(part_id)
            physics = knowledge.get("physics", {}) if knowledge else {}
            geometry = knowledge.get("geometry", {}) if knowledge else {}

            # 连接度分析
            neighbors = self.retriever.store.get_neighbors(f"part_{part_id}", limit=20)
            connection_count = len(neighbors)

            # 稳定性评分
            strength = physics.get("strength", 0.5) if isinstance(physics, dict) else 0.5
            studs = geometry.get("studs", 0) if isinstance(geometry, dict) else 0

            # 综合稳定性得分
            stability_score = min(1.0, (strength * 0.5 + min(studs, 8) / 8 * 0.5))

            analysis.append({
                "part_id": part_id,
                "name": part_info["part"]["name"],
                "found": True,
                "strength": strength,
                "studs": studs,
                "connections": connection_count,
                "stability_score": round(stability_score, 2),
                "assessment": "稳固" if stability_score > 0.7 else "一般" if stability_score > 0.4 else "不稳固",
            })

        # 推理链
        reasoning_chain = []
        for a in analysis:
            if a.get("found"):
                reasoning_chain.append(
                    f"{a['name']}: 稳定性 {a['assessment']} (得分 {a['stability_score']})"
                )
            else:
                reasoning_chain.append(f"零件 {a['part_id']} 不在图谱中")

        avg_stability = sum(a.get("stability_score", 0) for a in analysis if a.get("found")) / \
            max(1, sum(1 for a in analysis if a.get("found")))

        return {
            "conclusion": f"分析了 {len(analysis)} 个零件的结构稳定性",
            "confidence": avg_stability,
            "reasoning_chain": reasoning_chain,
            "analysis": analysis,
            "suggestions": [
                "稳定性 < 0.5 建议加固",
                "可增加连接点提高稳定性",
            ],
            "risks": [
                "结构不稳可能导致成品倒塌",
            ] if avg_stability < 0.5 else [],
            "missing_info": [],
        }

    def _llm_summarize(self, query: str, result: dict, timeout: float) -> str:
        """LLM 生成自然语言总结"""
        # 构建简洁的上下文
        context_text = f"推理结论: {result.get('conclusion', '')}\n"
        if result.get("reasoning_chain"):
            context_text += "推理过程:\n" + "\n".join(f"- {s}" for s in result["reasoning_chain"])

        prompt = f"用户问题: {query}\n\n{context_text}\n\n请用一句话总结推理结果。"

        response = self.llm.invoke([
            SystemMessage(content=REASONING_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])

        return response.content if hasattr(response, "content") else str(response)

    @staticmethod
    def _lookup_part_name(part_id: str) -> str:
        """查找零件名称"""
        knowledge = get_part_knowledge(part_id)
        if knowledge:
            return knowledge["name"]
        return f"Part {part_id}"

    # =========================================================================
    # 便捷方法
    # =========================================================================

    def reason_constraint(
        self,
        query: str,
        has_parts: list[str] = None,
        missing_parts: list[str] = None,
        **kwargs,
    ) -> dict:
        """多条件约束推理的便捷入口"""
        context = kwargs.copy()
        context["has_parts"] = has_parts or []
        context["missing_parts"] = missing_parts or []
        return self.reason(query, REASONING_CONSTRAINT, context)

    def reason_chain(
        self,
        query: str,
        steps: list[int] = None,
        **kwargs,
    ) -> dict:
        """步骤链式推理的便捷入口"""
        context = kwargs.copy()
        context["steps"] = steps or []
        return self.reason(query, REASONING_CHAIN, context)

    def reason_stability(
        self,
        query: str,
        part_id: str = "",
        position: dict = None,
        **kwargs,
    ) -> dict:
        """结构稳定性推理的便捷入口"""
        context = kwargs.copy()
        context["part_id"] = part_id
        context["position"] = position or {}
        return self.reason(query, REASONING_STABILITY, context)


# =========================================================================
# 全局单例
# =========================================================================

_reasoner: Optional[GraphReasoner] = None


def get_graph_reasoner(
    llm: BaseChatModel = None,
    retriever: GraphRetriever = None,
) -> GraphReasoner:
    """获取图谱推理引擎单例"""
    global _reasoner
    if _reasoner is None:
        if llm is None:
            from src.common.config import get_settings
            settings = get_settings()
            if not settings.llm_api_key:
                raise ValueError("LLM_API_KEY 未配置，无法初始化 GraphReasoner")
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model=settings.llm_model,
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                temperature=0.3,
            )
        _reasoner = GraphReasoner(llm=llm, retriever=retriever)
    return _reasoner


def get_graph_reasoner_retriever() -> GraphRetriever:
    """获取供 GraphReasoner 使用的 GraphRetriever"""
    return get_graph_reasoner_retriever_singleton()


_retriever_instance: Optional[GraphRetriever] = None


def get_graph_reasoner_retriever_singleton() -> GraphRetriever:
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = GraphRetriever()
    return _retriever_instance
