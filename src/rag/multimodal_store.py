"""多模态向量存储

同时存储文本向量和图片向量，支持：
- 文搜文（文本语义检索）
- 图搜图（图片相似度检索）
- 文搜图（文本查图片）
- 图搜文（图片查文本）

存储结构：
- ChromaDB collection: lego_multimodal
  - 文本文档: modality=text
  - 图片文档: modality=image, image_base64=...
"""

import os
import json
import base64
from typing import Optional, Union
from io import BytesIO

from chromadb import PersistentClient
from chromadb.config import Settings
from langchain_core.documents import Document
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

from src.rag.visual_encoder import VisualEncoder, get_visual_encoder


# 文本嵌入模型
TEXT_EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"


class MultimodalVectorStore:
    """多模态向量存储"""

    def __init__(
        self,
        collection_name: str = "lego_multimodal",
        visual_model: str = "siglip",
    ):
        # 持久化存储
        persist_dir = os.path.join(os.getcwd(), "data", "chroma_multimodal")
        os.makedirs(persist_dir, exist_ok=True)

        self.client = PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )

        # 文本嵌入
        self.text_embeddings = HuggingFaceEmbeddings(
            model_name=TEXT_EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
        )

        # 视觉编码器
        self.visual_encoder = get_visual_encoder(model_name=visual_model)

        # 文本向量库
        self.text_store = Chroma(
            client=self.client,
            collection_name=f"{collection_name}_text",
            embedding_function=self.text_embeddings,
        )

        # 图片向量库（使用相同的 collection 但不同模态）
        self.image_store = Chroma(
            client=self.client,
            collection_name=f"{collection_name}_image",
            embedding_function=self.text_embeddings,  # 占位，实际用视觉编码器
        )

        # 缓存
        self._image_cache: dict[str, bytes] = {}  # doc_id → image_bytes

    def add_pages(self, pages: list, set_id: str = "") -> int:
        """
        添加多模态页面。

        Args:
            pages: MultimodalPage 列表
            set_id: 套装编号

        Returns:
            添加的文档数
        """
        added = 0

        for page in pages:
            if not page.full_image:
                continue

            # 1. 编码图片
            image_embedding = self.visual_encoder.encode_image(page.full_image)

            # 2. 生成唯一 ID
            doc_id = f"{set_id}_page_{page.page_number}"

            # 3. 存储图片数据
            self._image_cache[doc_id] = page.full_image

            # 4. 创建图片 Document
            img_b64 = base64.b64encode(page.full_image).decode("utf-8")
            img_doc = Document(
                page_content=f"[PAGE_IMAGE_{page.page_number}]",
                metadata={
                    "set_id": set_id,
                    "page_number": page.page_number,
                    "modality": "image",
                    "doc_id": doc_id,
                    "image_base64": img_b64,
                    "source": page.metadata.get("source", ""),
                },
            )

            # 5. 添加到向量库（手动指定 embedding）
            self.image_store._collection.add(
                ids=[doc_id],
                embeddings=[image_embedding],
                documents=[img_doc.page_content],
                metadatas=[img_doc.metadata],
            )

            added += 1

        return added

    def search_by_text(
        self,
        query: str,
        set_id: str = "",
        top_k: int = 3,
    ) -> list[dict]:
        """
        文本搜索（文搜图 + 文搜文）。

        Args:
            query: 查询文本
            set_id: 套装过滤
            top_k: 返回数量

        Returns:
            搜索结果
        """
        # 构建过滤条件
        where = {"set_id": set_id} if set_id else None

        # 搜索文本库
        text_results = self.text_store.similarity_search_with_score(
            query, k=top_k, filter=where
        )

        results = []
        for doc, score in text_results:
            results.append({
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": float(1.0 - score),
                "match_type": "text",
                "image": self._get_image(doc.metadata.get("doc_id", "")),
            })

        return results

    def search_by_image(
        self,
        image: Union[str, bytes],
        set_id: str = "",
        top_k: int = 3,
    ) -> list[dict]:
        """
        图片搜索（图搜文 + 图搜图）。

        Args:
            image: 图片路径或 bytes
            set_id: 套装过滤
            top_k: 返回数量

        Returns:
            搜索结果
        """
        # 编码查询图片
        query_embedding = self.visual_encoder.encode_image(image)

        # 构建过滤条件
        where = {"set_id": set_id} if set_id else None

        # 搜索图片库
        results = self.image_store._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
        )

        output = []
        if results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i]
                distance = results["distances"][0][i]

                output.append({
                    "content": results["documents"][0][i],
                    "metadata": metadata,
                    "score": float(1.0 - distance),
                    "match_type": "image",
                    "image": self._get_image(doc_id),
                })

        return output

    def cross_modal_search(
        self,
        query: str,
        image: Union[str, bytes],
        set_id: str = "",
        top_k: int = 3,
    ) -> list[dict]:
        """
        跨模态搜索（同时使用文本和图片）。

        Args:
            query: 查询文本
            image: 查询图片
            set_id: 套装过滤
            top_k: 返回数量

        Returns:
            融合后的结果
        """
        # 文搜图
        text_results = self.search_by_text(query, set_id, top_k)

        # 图搜文
        image_results = self.search_by_image(image, set_id, top_k)

        # 融合（去重 + 加权）
        seen_ids = set()
        fused = []

        for r in text_results:
            doc_id = r["metadata"].get("doc_id", "")
            if doc_id not in seen_ids:
                seen_ids.add(doc_id)
                r["fused_score"] = r["score"] * 0.5
                fused.append(r)

        for r in image_results:
            doc_id = r["metadata"].get("doc_id", "")
            if doc_id not in seen_ids:
                seen_ids.add(doc_id)
                r["fused_score"] = r["score"] * 0.5
                fused.append(r)
            else:
                # 已在文本结果中，提升分数
                for f in fused:
                    if f["metadata"].get("doc_id") == doc_id:
                        f["fused_score"] += r["score"] * 0.5
                        f["match_type"] = "cross_modal"
                        break

        # 排序
        fused.sort(key=lambda x: x.get("fused_score", x["score"]), reverse=True)

        return fused[:top_k]

    def _get_image(self, doc_id: str) -> Optional[bytes]:
        """获取图片数据"""
        return self._image_cache.get(doc_id)

    def get_stats(self) -> dict:
        """获取统计信息"""
        try:
            text_count = self.text_store._collection.count()
            image_count = self.image_store._collection.count()
            return {
                "text_documents": text_count,
                "image_documents": image_count,
                "cached_images": len(self._image_cache),
            }
        except Exception:
            return {"text_documents": 0, "image_documents": 0}


# 全局单例
_store: Optional[MultimodalVectorStore] = None


def get_multimodal_store(
    visual_model: str = "siglip",
) -> MultimodalVectorStore:
    """获取多模态存储单例"""
    global _store
    if _store is None:
        _store = MultimodalVectorStore(visual_model=visual_model)
    return _store
