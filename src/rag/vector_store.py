"""ChromaDB 向量存储 + 关键词混合检索"""

import os
import re
from typing import Any
from chromadb import PersistentClient
from chromadb.config import Settings
from langchain_core.documents import Document
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

from src.common.config import get_settings


# 嵌入模型（本地运行，无需 API Key）
EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"  # 中文友好，体积小


class ManualVectorStore:
    """说明书向量存储"""

    def __init__(self, collection_name: str = "lego_manuals"):
        settings = get_settings()
        self.collection_name = collection_name

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

    def add_documents(self, documents: list[Document], set_id: str = ""):
        """
        添加文档到向量存储

        Args:
            documents: 文档列表
            set_id: 套装编号（作为元数据）
        """
        # 添加元数据
        for doc in documents:
            doc.metadata["set_id"] = set_id

        self.vectorstore.add_documents(documents)
        self._all_docs.extend(documents)
        print(f"[OK] 导入 {len(documents)} 个文档片段 (set: {set_id})")

    def search(self, query: str, set_id: str = "", top_k: int = 3) -> list[dict]:
        """
        混合检索：向量 + 关键词

        Args:
            query: 查询文本
            set_id: 套装编号过滤
            top_k: 返回数量

        Returns:
            检索结果列表
        """
        # 1. 向量检索
        where_filter = {"set_id": set_id} if set_id else None
        vector_results = self.vectorstore.similarity_search_with_score(
            query, k=top_k * 2, filter=where_filter
        )

        # 2. 关键词匹配（步骤号精确匹配）
        keyword_results = self._keyword_search(query, set_id)

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
                    "score": 1.0,  # 关键词匹配优先级最高
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

    def _keyword_search(self, query: str, set_id: str = "") -> list[tuple[Document, float]]:
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


# 全局单例
_store: ManualVectorStore | None = None


def get_vector_store() -> ManualVectorStore:
    """获取向量存储单例"""
    global _store
    if _store is None:
        _store = ManualVectorStore()
    return _store
