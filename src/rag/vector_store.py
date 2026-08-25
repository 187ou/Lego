"""ChromaDB 向量存储 + 混合检索

支持：
- 多格式文档的向量化存储
- 向量 + 关键词混合检索
- 按套装/文档类型过滤
- 批量导入和增量更新
"""

import os
import re
from typing import Any, Optional
from chromadb import PersistentClient
from chromadb.config import Settings
from langchain_core.documents import Document
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma


# 嵌入模型（本地运行，无需 API Key）
EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"  # 中文友好，体积小


class ManualVectorStore:
    """说明书向量存储"""

    def __init__(self, collection_name: str = "lego_manuals"):
        # 持久化存储
        persist_dir = os.path.join(os.getcwd(), "data", "chroma_db")
        os.makedirs(persist_dir, exist_ok=True)

        self.client = PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )

        # 嵌入模型
        self.embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
        )

        # Chroma 向量存储
        self.vectorstore = Chroma(
            client=self.client,
            collection_name=collection_name,
            embedding_function=self.embeddings,
        )

        # 缓存所有文档用于关键词匹配
        self._all_docs: list[Document] = []
        self._doc_ids: list[str] = []

    def add_documents(
        self,
        documents: list[Document],
        set_id: str = "",
        batch_size: int = 50,
    ) -> int:
        """
        添加文档到向量存储（支持批量）。

        Args:
            documents: 文档列表
            set_id: 套装编号（作为元数据）
            batch_size: 每批处理数量

        Returns:
            成功添加的文档数
        """
        if not documents:
            return 0

        # 添加元数据
        for doc in documents:
            doc.metadata["set_id"] = set_id

        # 分批添加（避免内存溢出）
        added = 0
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            self.vectorstore.add_documents(batch)
            self._all_docs.extend(batch)
            added += len(batch)

        print(f"[OK] 导入 {added} 个文档片段 (set: {set_id})")
        return added

    def search(
        self,
        query: str,
        set_id: str = "",
        top_k: int = 3,
        doc_type: str = "",
    ) -> list[dict]:
        """
        混合检索：向量 + 关键词。

        Args:
            query: 查询文本
            set_id: 套装编号过滤
            top_k: 返回数量
            doc_type: 文档类型过滤（pdf/image/text/docx）

        Returns:
            检索结果列表
        """
        # 构建过滤条件
        where_filter = {}
        if set_id:
            where_filter["set_id"] = set_id
        if doc_type:
            where_filter["doc_type"] = doc_type

        where = where_filter if where_filter else None

        # 1. 向量检索
        vector_results = self.vectorstore.similarity_search_with_score(
            query, k=top_k * 2, filter=where
        )

        # 2. 关键词匹配（步骤号精确匹配）
        keyword_results = self._keyword_search(query, set_id, doc_type)

        # 3. 合并去重
        seen = set()
        merged = []

        # 优先添加关键词精确匹配
        for doc, score in keyword_results:
            key = doc.page_content[:50]
            if key not in seen:
                seen.add(key)
                merged.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": 1.0,
                    "match_type": "keyword",
                })

        # 添加向量检索结果
        for doc, score in vector_results:
            key = doc.page_content[:50]
            if key not in seen:
                seen.add(key)
                merged.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": max(0.5, 1.0 - score),  # 距离转相似度
                    "match_type": "vector",
                })

        return merged[:top_k]

    def _keyword_search(
        self,
        query: str,
        set_id: str = "",
        doc_type: str = "",
    ) -> list[tuple[Document, float]]:
        """关键词匹配"""
        results = []

        # 提取步骤号
        step_match = re.search(r'步骤?\s*(\d+)|step\s*(\d+)', query, re.IGNORECASE)
        target_step = None
        if step_match:
            target_step = int(step_match.group(1) or step_match.group(2))

        for doc in self._all_docs:
            # 过滤套装
            if set_id and doc.metadata.get("set_id") != set_id:
                continue
            # 过滤文档类型
            if doc_type and doc.metadata.get("doc_type") != doc_type:
                continue

            score = 0.0

            # 步骤号精确匹配
            if target_step and doc.metadata.get("step_number") == target_step:
                score = 1.0

            # 内容包含关键词
            elif any(kw in doc.page_content for kw in query.split()):
                score = 0.7

            if score > 0:
                results.append((doc, score))

        return sorted(results, key=lambda x: x[1], reverse=True)

    def delete_by_set(self, set_id: str) -> int:
        """删除指定套装的所有文档"""
        try:
            count = self.vectorstore._collection.count()
            self.vectorstore._collection.delete(where={"set_id": set_id})
            # 更新缓存
            self._all_docs = [
                d for d in self._all_docs if d.metadata.get("set_id") != set_id
            ]
            deleted = count - self.vectorstore._collection.count()
            print(f"[OK] 删除套装 {set_id} 的 {deleted} 个文档")
            return deleted
        except Exception as e:
            print(f"[ERROR] 删除失败: {e}")
            return 0

    def get_stats(self) -> dict:
        """获取存储统计信息"""
        try:
            count = self.vectorstore._collection.count()
            return {
                "total_documents": count,
                "cached_documents": len(self._all_docs),
                "collection_name": self.vectorstore._collection.name,
            }
        except Exception:
            return {"total_documents": 0, "cached_documents": 0}

    def list_sets(self) -> list[str]:
        """列出所有已存储的套装编号"""
        sets = set()
        for doc in self._all_docs:
            set_id = doc.metadata.get("set_id", "")
            if set_id:
                sets.add(set_id)
        return sorted(sets)


# 全局单例
_store: ManualVectorStore | None = None


def get_vector_store() -> ManualVectorStore:
    """获取向量存储单例"""
    global _store
    if _store is None:
        _store = ManualVectorStore()
    return _store
