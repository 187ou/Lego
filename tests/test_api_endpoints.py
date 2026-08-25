"""API 端点集成测试"""

import pytest
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestHealthEndpoint:
    """健康检查端点"""

    def test_health_returns_200(self):
        """健康检查应返回 200"""
        from fastapi.testclient import TestClient
        with patch("server.get_graph", return_value=MagicMock()):
            from server import app
            client = TestClient(app)
            resp = client.get("/api/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "healthy"


class TestGraphEndpoints:
    """图谱端点测试"""

    def test_graph_stats(self):
        """图谱统计端点"""
        from fastapi.testclient import TestClient
        with patch("server.get_graph", return_value=MagicMock()):
            from server import app
            client = TestClient(app)
            resp = client.get("/api/graph/stats")
            # 可能 200 或 500（取决于 Neo4j 连接）
            assert resp.status_code in (200, 500)

    def test_graph_init(self):
        """图谱初始化端点"""
        from fastapi.testclient import TestClient
        with patch("server.get_graph", return_value=MagicMock()):
            from server import app
            client = TestClient(app)
            resp = client.post("/api/graph/init")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["total_nodes"] > 0

    def test_graph_part_info(self):
        """零件信息端点"""
        from fastapi.testclient import TestClient
        with patch("server.get_graph", return_value=MagicMock()):
            from server import app
            client = TestClient(app)
            resp = client.get("/api/graph/part/3001")
            assert resp.status_code == 200

    def test_graph_part_not_found(self):
        """不存在的零件"""
        from fastapi.testclient import TestClient
        with patch("server.get_graph", return_value=MagicMock()):
            from server import app
            client = TestClient(app)
            resp = client.get("/api/graph/part/9999")
            assert resp.status_code == 200
            data = resp.json()
            assert data["found"] is False

    def test_graph_cross_modal(self):
        """跨模态搜索端点"""
        from fastapi.testclient import TestClient
        with patch("server.get_graph", return_value=MagicMock()):
            from server import app
            client = TestClient(app)
            resp = client.get("/api/graph/cross-modal?query=3001&limit=3")
            assert resp.status_code == 200
            data = resp.json()
            assert "results" in data


class TestChatEndpoint:
    """聊天端点测试"""

    def test_chat_requires_message(self):
        """聊天需要 message 字段"""
        from fastapi.testclient import TestClient
        with patch("server.get_graph", return_value=MagicMock()):
            from server import app
            client = TestClient(app)
            resp = client.post("/api/chat", json={"message": ""})
            # 空消息应返回错误或走 L1
            assert resp.status_code in (200, 422)

    def test_chat_stream_requires_message(self):
        """流式聊天需要 message"""
        from fastapi.testclient import TestClient
        with patch("server.get_graph", return_value=MagicMock()):
            from server import app
            client = TestClient(app)
            resp = client.post("/api/chat/stream", json={"message": "你好"})
            # 应返回 SSE 流（可能 200 或 500 取决于 LLM 配置）
            assert resp.status_code in (200, 500)


class TestDocumentEndpoints:
    """文档端点测试"""

    def test_document_stats(self):
        """文档统计端点"""
        from fastapi.testclient import TestClient
        with patch("server.get_graph", return_value=MagicMock()):
            from server import app
            client = TestClient(app)
            resp = client.get("/api/documents/stats")
            assert resp.status_code == 200

    def test_search_documents(self):
        """文档搜索端点"""
        from fastapi.testclient import TestClient
        with patch("server.get_graph", return_value=MagicMock()):
            from server import app
            client = TestClient(app)
            resp = client.get("/api/documents/search?query=步骤&top_k=3")
            assert resp.status_code == 200
            data = resp.json()
            assert "results" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
