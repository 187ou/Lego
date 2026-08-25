"""LLM 驱动的知识图谱推理引擎

三种推理能力：
1. 多条件约束推理 — "有 A 无 B，找兼容 A 且替代 B 的零件"
2. 步骤链式推理   — "第 35 步和第 36 步之间可以跳过吗？"
3. 结构稳定性推理 — "这个位置放 1x2 板够稳固吗？"

工作流程：
1. 从图谱检索相关子图
2. 将子图序列化为 LLM 可理解的文本
3. LLM 推理
4. 解析结构化结果
"""

import re
from typing import Any, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

from src.kg.graph_retriever import GraphRetriever
from src.kg.schema import NodeType, RelationType


# 推理类型
REASONING_CONSTRAINT = "constraint"
REASONING_CHAIN = "chain"
REASONING_STABILITY = "stability"

# 推理系统提示
REASONING_SYSTEM_PROMPT = """你是 LEGO-Mate 知识图谱推理引擎。
你的任务是基于给定的图谱子图数据，进行复杂的逻辑推理。

推理规则：
- 严格基于图谱数据推理，不要编造不存在的信息
- 每个结论必须附带推理依据（引用图谱中的具体关系）
- 如果信息不足，明确说明缺少什么信息
- 用中文回答，简洁清晰

输出格式（JSON）：
{
  "conclusion": "推理结论",
  "confidence": 0.0-1.0,
  "reasoning_chain": ["推理步骤1", "推理步骤2", ...],
  "suggestions": ["建议1", "建议2"],
  "risks": ["风险1", "风险2"],
  "missing_info": ["缺少的信息"]
}
"""


class GraphReasoner:
    """LLM 驱动的知识图谱推理引擎"""

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
            context: 额外上下文（如 set_id, current_step 等）
            timeout: LLM 调用超时（秒）

        Returns:
            推理结果字典
        """
        import concurrent.futures

        context = context or {}

        # 1. 从图谱检索相关子图
        subgraph = self._retrieve_subgraph(query, reasoning_type, context)

        # 2. 数据质量预检
        quality_warning = self._check_subgraph_quality(subgraph, query)
        if quality_warning:
            return {
                "conclusion": quality_warning,
                "confidence": 0,
                "reasoning_chain": [],
                "suggestions": ["请确认零件编号是否正确", "或联系管理员完善图谱数据"],
                "risks": [],
                "missing_info": [],
                "subgraph_summary": subgraph.get("summary", ""),
            }

        # 3. 构建推理 prompt
        prompt = self._build_reasoning_prompt(query, reasoning_type, subgraph, context)

        # 4. LLM 推理（带超时）
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self.llm.invoke, prompt)
                response = future.result(timeout=timeout)
            raw_text = response.content if hasattr(response, "content") else str(response)
            return self._parse_reasoning_result(raw_text, subgraph)
        except concurrent.futures.TimeoutError:
            return {
                "conclusion": f"推理超时（{timeout}s），请简化查询或稍后重试",
                "confidence": 0,
                "reasoning_chain": [],
                "suggestions": ["尝试更简单的查询"],
                "risks": [],
                "missing_info": [],
                "subgraph_summary": subgraph.get("summary", ""),
            }
        except Exception as e:
            return {
                "conclusion": f"推理引擎暂时不可用: {type(e).__name__}",
                "confidence": 0,
                "reasoning_chain": [],
                "suggestions": ["请稍后重试", "或直接询问具体零件的替代方案"],
                "risks": [],
                "missing_info": [],
                "subgraph_summary": subgraph.get("summary", ""),
            }

    def _check_subgraph_quality(self, subgraph: dict, query: str) -> str:
        """
        子图数据质量预检。
        返回空字符串表示质量通过，否则返回警告信息。
        """
        # 空图谱
        if not subgraph["nodes"]:
            return "图谱中暂无相关数据，无法进行推理"

        # 查询中有零件号但子图无 Part 节点
        import re
        part_ids_in_query = re.findall(r"(?<!\d)(\d{4,5})(?!\d)", query)
        part_ids_in_graph = [
            n["id"].replace("part_", "") for n in subgraph["nodes"]
            if n.get("type") == "Part"
        ]
        if part_ids_in_query and not part_ids_in_graph:
            return f"零件 {part_ids_in_query[0]} 不在图谱中，无法推理"

        return ""

    def _retrieve_subgraph(
        self,
        query: str,
        reasoning_type: str,
        context: dict,
    ) -> dict:
        """
        根据查询和推理类型，从图谱检索相关子图。
        """
        subgraph = {"nodes": [], "relations": [], "summary": ""}

        set_id = context.get("set_id", "10295")

        # 提取零件号
        part_ids = re.findall(r"(?<!\d)(\d{4,5})(?!\d)", query)
        # 提取步骤号
        step_numbers = []
        for pattern in [r"第?\s*(\d+)\s*步", r"step\s*(\d+)", r"(\d+)步"]:
            matches = re.findall(pattern, query, re.IGNORECASE)
            step_numbers.extend([int(m) for m in matches])

        nodes_info = []
        relations_info = []

        if reasoning_type == REASONING_CONSTRAINT:
            # 约束推理：查找所有提及零件的替代链
            for part_id in part_ids:
                part_info = self.retriever.get_part_info(part_id)
                if part_info.get("found"):
                    part_data = {
                        "id": f"part_{part_id}",
                        "name": part_info["part"]["name"],
                        "type": "Part",
                        "properties": part_info["part"].get("properties", {}),
                        "colors": part_info.get("colors", []),
                        "categories": part_info.get("categories", []),
                    }
                    # 解析尺寸（从名称中提取）
                    size = self._parse_size_from_name(part_info["part"]["name"])
                    if size:
                        part_data["size"] = {"width": size[0], "length": size[1]}
                    nodes_info.append(part_data)

                    # 查找替代方案
                    alternatives = self.retriever.find_part_alternatives(part_id, limit=5)
                    for alt in alternatives:
                        nodes_info.append({
                            "id": f"part_{alt['part_id']}",
                            "name": alt["name"],
                            "type": "Part",
                            "distance": alt.get("distance", 1),
                        })
                        relations_info.append({
                            "from": f"part_{part_id}",
                            "to": f"part_{alt['part_id']}",
                            "relation": "CAN_REPLACE",
                            "distance": alt.get("distance", 1),
                        })

        elif reasoning_type == REASONING_CHAIN:
            # 链式推理：查找步骤链和依赖关系
            for step_num in step_numbers:
                step_info = self.retriever.get_step_info(set_id, step_num)
                if step_info.get("found"):
                    nodes_info.append({
                        "id": f"set_{set_id}_step_{step_num}",
                        "name": f"步骤 {step_num}",
                        "type": "Step",
                        "description": step_info["step"].get("description", ""),
                        "parts": [
                            {"part_id": p.get("part_id", ""), "name": p.get("name", "")}
                            for p in step_info.get("parts", [])
                        ],
                    })

            # 查找步骤间的路径
            if len(step_numbers) >= 2:
                source = f"set_{set_id}_step_{step_numbers[0]}"
                target = f"set_{set_id}_step_{step_numbers[1]}"
                paths = self.retriever.find_path(source, target, max_depth=4)
                if paths:
                    relations_info.append({
                        "from": source,
                        "to": target,
                        "relation": "PATH_FOUND",
                        "path_length": len(paths[0]),
                    })

        elif reasoning_type == REASONING_STABILITY:
            # 稳定性推理：查找零件的连接关系
            for part_id in part_ids:
                part_info = self.retriever.get_part_info(part_id)
                if part_info.get("found"):
                    nodes_info.append({
                        "id": f"part_{part_id}",
                        "name": part_info["part"]["name"],
                        "type": "Part",
                        "properties": part_info["part"].get("properties", {}),
                        "colors": part_info.get("colors", []),
                    })

            # 如果有步骤号，查找该步骤的完整上下文
            if step_numbers:
                for step_num in step_numbers:
                    step_info = self.retriever.get_step_info(set_id, step_num)
                    if step_info.get("found"):
                        nodes_info.append({
                            "id": f"set_{set_id}_step_{step_num}",
                            "name": f"步骤 {step_num}",
                            "type": "Step",
                            "description": step_info["step"].get("description", ""),
                            "parts": [
                                {"part_id": p.get("part_id", ""), "name": p.get("name", "")}
                                for p in step_info.get("parts", [])
                            ],
                        })

        subgraph["nodes"] = self._deduplicate_nodes(nodes_info)
        subgraph["relations"] = relations_info
        subgraph["summary"] = self._summarize_subgraph(subgraph)

        return subgraph

    def _build_reasoning_prompt(
        self,
        query: str,
        reasoning_type: str,
        subgraph: dict,
        context: dict,
    ) -> list:
        """构建推理 prompt"""
        set_id = context.get("set_id", "10295")

        type_descriptions = {
            REASONING_CONSTRAINT: "多条件约束推理 — 用户缺少某些零件，需要找到满足约束的替代方案",
            REASONING_CHAIN: "步骤链式推理 — 分析步骤间的依赖关系，判断是否可以跳过或调整顺序",
            REASONING_STABILITY: "结构稳定性推理 — 评估某个位置的零件是否稳固，是否需要加固",
        }

        subgraph_text = self._serialize_subgraph(subgraph)

        user_prompt = f"""## 推理任务
类型: {type_descriptions.get(reasoning_type, reasoning_type)}
用户查询: {query}
当前套装: {set_id}

## 相关图谱子图
{subgraph_text}

请基于以上图谱数据进行推理，输出 JSON 格式结果。"""

        return [
            SystemMessage(content=REASONING_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]

    def _serialize_subgraph(self, subgraph: dict) -> str:
        """将子图序列化为 LLM 可读文本"""
        lines = []

        if not subgraph["nodes"]:
            return "（图谱中暂无相关数据，请基于通用乐高知识推理）"

        lines.append("### 节点")
        for node in subgraph["nodes"]:
            desc = f"- [{node['type']}] {node['id']}: {node['name']}"
            if node.get("properties"):
                desc += f" | 属性: {node['properties']}"
            if node.get("description"):
                desc += f" | 描述: {node['description'][:100]}"
            if node.get("parts"):
                parts_str = ", ".join([f"{p['part_id']}({p['name']})" for p in node["parts"]])
                desc += f" | 使用零件: {parts_str}"
            lines.append(desc)

        if subgraph["relations"]:
            lines.append("\n### 关系")
            for rel in subgraph["relations"]:
                lines.append(f"- {rel['from']} --[{rel['relation']}]--> {rel['to']}")

        return "\n".join(lines)

    def _summarize_subgraph(self, subgraph: dict) -> str:
        """生成子图摘要"""
        node_count = len(subgraph["nodes"])
        rel_count = len(subgraph["relations"])
        return f"子图包含 {node_count} 个节点, {rel_count} 条关系"

    def _parse_reasoning_result(self, raw_text: str, subgraph: dict) -> dict:
        """解析 LLM 返回的推理结果"""
        import json

        # 尝试提取 JSON
        try:
            # 先尝试直接解析
            result = json.loads(raw_text)
        except json.JSONDecodeError:
            # 尝试从 markdown 代码块提取
            json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw_text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    result = self._fallback_parse(raw_text)
            else:
                result = self._fallback_parse(raw_text)

        result["subgraph_summary"] = subgraph.get("summary", "")
        return result

    def _fallback_parse(self, raw_text: str) -> dict:
        """LLM 返回非 JSON 时的降级解析"""
        return {
            "conclusion": raw_text.strip(),
            "confidence": 0.5,
            "reasoning_chain": [],
            "suggestions": [],
            "risks": [],
            "missing_info": [],
        }

    @staticmethod
    def _parse_size_from_name(name: str) -> tuple[int, int] | None:
        """从零件名称解析尺寸（如 'Brick 2x4' → (2, 4)）"""
        match = re.search(r"(\d+)\s*[x×]\s*(\d+)", name)
        if match:
            return (int(match.group(1)), int(match.group(2)))
        return None

    def _deduplicate_nodes(self, nodes: list[dict]) -> list[dict]:
        """去重"""
        seen = set()
        unique = []
        for node in nodes:
            nid = node.get("id", "")
            if nid and nid not in seen:
                seen.add(nid)
                unique.append(node)
        return unique

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
        """
        多条件约束推理的便捷入口。

        Args:
            query: 用户查询
            has_parts: 用户已有的零件列表
            missing_parts: 用户缺少的零件列表
        """
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
    """
    获取图谱推理引擎单例。

    首次调用需要传入 llm，后续调用可省略。
    """
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
