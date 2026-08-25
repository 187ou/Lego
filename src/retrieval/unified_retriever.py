"""统一检索器

将来自 L1-L4 所有层级的检索结果融合为统一的输出。

检索源：
- L1 短期记忆：对话历史（Redis）
- L2 中期记忆：对话摘要（Redis）
- L3 长期记忆：用户画像（Redis）
- L4 向量检索：语义搜索（ChromaDB）
- L4 图谱检索：关系推理（Neo4j）
- L4 跨模态检索：文本↔图片
"""

from typing import Optional

from src.retrieval.fusion_strategy import (
    RetrievalResult,
    FusionStrategy,
    FusionConfig,
)
from src.retrieval.context_builder import ContextBuilder, ContextConfig


class UnifiedRetriever:
    """统一检索器"""

    def __init__(
        self,
        fusion_config: Optional[FusionConfig] = None,
        context_config: Optional[ContextConfig] = None,
    ):
        self.fusion_strategy = FusionStrategy(config=fusion_config or FusionConfig())
        self.context_builder = ContextBuilder(config=context_config or ContextConfig())

    def retrieve(
        self,
        query: str,
        conversation_id: str = "",
        set_id: str = "",
        image: bytes = None,
        top_k: int = 10,
    ) -> list[RetrievalResult]:
        """
        多路检索 + 融合。

        Args:
            query: 查询文本
            conversation_id: 对话 ID
            set_id: 套装编号
            image: 查询图片（可选）
            top_k: 返回数量

        Returns:
            融合后的检索结果
        """
        results_by_source = {}

        # L1-L3: 记忆检索
        memory_results = self._retrieve_from_memory(query, conversation_id)
        if memory_results:
            results_by_source["memory"] = memory_results

        # L4: 向量检索
        vector_results = self._retrieve_from_vector_store(query, set_id)
        if vector_results:
            results_by_source["vector"] = vector_results

        # L4: 图谱检索
        graph_results = self._retrieve_from_graph(query, set_id)
        if graph_results:
            results_by_source["graph"] = graph_results

        # L4: 跨模态检索
        if image:
            cross_modal_results = self._retrieve_cross_modal(query, image, set_id)
            if cross_modal_results:
                results_by_source["cross_modal"] = cross_modal_results

        # 融合
        fused = self.fusion_strategy.fuse(results_by_source)

        return fused[:top_k]

    def build_context(
        self,
        query: str,
        conversation_id: str = "",
        set_id: str = "",
        image: bytes = None,
    ) -> list[dict]:
        """
        检索 + 融合 + 构建 LLM 上下文。

        Args:
            query: 查询文本
            conversation_id: 对话 ID
            set_id: 套装编号
            image: 查询图片

        Returns:
            LLM 消息列表
        """
        # 检索
        results = self.retrieve(query, conversation_id, set_id, image)

        # 获取用户画像
        user_profile = self._get_user_profile()

        # 获取对话摘要
        summary = self._get_conversation_summary(conversation_id)

        # 构建上下文
        context = self.context_builder.build(
            fused_results=results,
            user_query=query,
            user_profile=user_profile,
            conversation_summary=summary,
        )

        return context

    def _retrieve_from_memory(
        self, query: str, conversation_id: str
    ) -> list[RetrievalResult]:
        """从记忆系统检索"""
        results = []

        try:
            from src.memory.manager import get_memory_manager
            mem_manager = get_memory_manager()

            if conversation_id and mem_manager.r:
                # 获取最近消息
                messages = mem_manager.get_messages(conversation_id, limit=10)

                for msg in messages:
                    results.append(RetrievalResult(
                        content=msg.content,
                        source="memory",
                        score=0.7,  # 记忆的基础分数
                        metadata={
                            "role": msg.role,
                            "timestamp": msg.timestamp,
                            "intent": msg.intent,
                        },
                        doc_id=msg.id,
                    ))
        except Exception as e:
            print(f"[WARN] 记忆检索失败: {e}")

        return results

    def _retrieve_from_vector_store(
        self, query: str, set_id: str
    ) -> list[RetrievalResult]:
        """从向量库检索"""
        results = []

        try:
            from src.rag.vector_store import get_vector_store
            store = get_vector_store()

            search_results = store.search(query, set_id=set_id, top_k=5)

            for r in search_results:
                results.append(RetrievalResult(
                    content=r["content"],
                    source="vector",
                    score=r.get("score", 0.5),
                    metadata=r.get("metadata", {}),
                    doc_id=r.get("metadata", {}).get("page_number", ""),
                ))
        except Exception as e:
            print(f"[WARN] 向量检索失败: {e}")

        return results

    def _retrieve_from_graph(self, query: str, set_id: str) -> list[RetrievalResult]:
        """从知识图谱检索"""
        results = []

        try:
            from src.kg.graph_retriever import get_graph_retriever
            retriever = get_graph_retriever()

            # 提取查询中的零件号
            import re
            part_ids = re.findall(r"(?<!\d)(\d{4,5})(?!\d)", query)

            for part_id in part_ids:
                # 获取零件信息
                part_info = retriever.get_part_info(part_id)
                if part_info.get("found"):
                    results.append(RetrievalResult(
                        content=f"零件 {part_id}: {part_info['part']['name']}",
                        source="graph",
                        score=0.8,
                        metadata={"part_id": part_id, **part_info},
                        doc_id=f"part_{part_id}",
                    ))

                # 获取替代方案
                alternatives = retriever.find_part_alternatives(part_id, limit=3)
                for alt in alternatives:
                    results.append(RetrievalResult(
                        content=f"替代方案: {alt['name']} ({alt['part_id']})",
                        source="graph",
                        score=0.6 / (alt.get("distance", 1)),
                        metadata={"alternative": alt},
                        doc_id=f"part_{alt['part_id']}",
                    ))

            # 提取步骤号
            step_match = re.search(r"第?\s*(\d+)\s*步", query)
            if step_match:
                step_number = int(step_match.group(1))
                step_info = retriever.get_step_info(set_id, step_number)
                if step_info.get("found"):
                    content = f"步骤 {step_number}: {step_info['step']['description']}"
                    if step_info.get("parts"):
                        parts_str = ", ".join([p.get("name", "") for p in step_info["parts"]])
                        content += f"\n使用零件: {parts_str}"

                    results.append(RetrievalResult(
                        content=content,
                        source="graph",
                        score=0.9,
                        metadata={"step": step_info},
                        doc_id=f"set_{set_id}_step_{step_number}",
                    ))
        except Exception as e:
            print(f"[WARN] 图谱检索失败: {e}")

        return results

    def _retrieve_cross_modal(
        self, query: str, image: bytes, set_id: str
    ) -> list[RetrievalResult]:
        """跨模态检索"""
        results = []

        try:
            from src.rag.multimodal_store import get_multimodal_store
            store = get_multimodal_store()

            # 图搜文
            image_results = store.search_by_image(image, set_id=set_id, top_k=3)

            for r in image_results:
                results.append(RetrievalResult(
                    content=r.get("content", ""),
                    source="cross_modal",
                    score=r.get("score", 0.5),
                    metadata=r.get("metadata", {}),
                    doc_id=r.get("metadata", {}).get("doc_id", ""),
                ))
        except Exception as e:
            print(f"[WARN] 跨模态检索失败: {e}")

        return results

    def _get_user_profile(self) -> Optional[dict]:
        """获取用户画像"""
        try:
            from src.memory.manager import get_memory_manager
            mem_manager = get_memory_manager()
            profile = mem_manager.get_user_profile("default")
            return profile.model_dump()
        except Exception:
            return None

    def _get_conversation_summary(self, conversation_id: str) -> str:
        """获取对话摘要"""
        try:
            from src.memory.manager import get_memory_manager
            mem_manager = get_memory_manager()
            summary = mem_manager.get_conversation_summary(conversation_id)
            if summary:
                return summary.summary
        except Exception:
            pass
        return ""


# 全局单例
_retriever: Optional[UnifiedRetriever] = None


def get_unified_retriever() -> UnifiedRetriever:
    """获取统一检索器单例"""
    global _retriever
    if _retriever is None:
        _retriever = UnifiedRetriever()
    return _retriever
