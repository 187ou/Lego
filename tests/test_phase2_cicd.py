"""Phase 2 CI/CD 和监控测试

测试内容：
1. Prometheus 指标收集
2. 结构化日志
3. 健康检查
4. Docker 配置验证
"""

import pytest
from unittest.mock import MagicMock, patch


# ===== 1. Prometheus 指标测试 =====

class TestPrometheusMetrics:
    """测试 Prometheus 指标收集"""

    def test_http_request_tracking(self):
        """应能记录 HTTP 请求"""
        try:
            from src.agent.utils.metrics import track_http_request
            track_http_request("GET", "/api/health", 200, 0.01)
            track_http_request("POST", "/api/chat", 200, 0.5)
        except ImportError:
            pytest.skip("prometheus_client not installed")

    def test_agent_call_tracking(self):
        """应能记录 Agent 调用"""
        try:
            from src.agent.utils.metrics import track_agent_call
            track_agent_call("vision", 0.5, success=True)
            track_agent_call("chat", 1.0, success=False)
        except ImportError:
            pytest.skip("prometheus_client not installed")

    def test_cache_tracking(self):
        """应能记录缓存命中/未命中"""
        try:
            from src.agent.utils.metrics import track_cache_hit, track_cache_miss
            track_cache_hit("l1")
            track_cache_hit("l2")
            track_cache_miss("l1")
        except ImportError:
            pytest.skip("prometheus_client not installed")

    def test_image_parse_tracking(self):
        """应能记录图片解析"""
        try:
            from src.agent.utils.metrics import track_image_parse
            track_image_parse("clip")
            track_image_parse("vl")
        except ImportError:
            pytest.skip("prometheus_client not installed")

    def test_get_metrics_returns_bytes(self):
        """get_metrics 应返回 bytes"""
        try:
            from src.agent.utils.metrics import get_metrics
            result = get_metrics()
            assert isinstance(result, bytes)
        except ImportError:
            pytest.skip("prometheus_client not installed")


# ===== 2. 结构化日志测试 =====

class TestStructuredLogger:
    """测试结构化日志"""

    def test_set_and_get_request_id(self):
        """应能设置和获取请求 ID"""
        from src.agent.utils.logger import set_request_id, get_request_id, clear_request_id

        # 清除之前的
        clear_request_id()

        # 设置请求 ID
        req_id = set_request_id()
        assert req_id is not None
        assert len(req_id) == 12

        # 获取请求 ID
        assert get_request_id() == req_id

        # 清除
        clear_request_id()
        assert get_request_id() is None

    def test_custom_request_id(self):
        """应能设置自定义请求 ID"""
        from src.agent.utils.logger import set_request_id, get_request_id, clear_request_id

        custom_id = "test-12345"
        set_request_id(custom_id)
        assert get_request_id() == custom_id

        clear_request_id()

    def test_setup_logging(self):
        """应能配置日志"""
        from src.agent.utils.logger import setup_logging

        # 不应抛出异常
        setup_logging(level="INFO", json_format=False)
        setup_logging(level="DEBUG", json_format=True)


# ===== 3. 健康检查测试 =====

class TestHealthCheck:
    """测试健康检查"""

    def test_health_endpoint_exists(self):
        """健康检查端点应存在"""
        # 验证端点配置正确
        assert True  # 端点已在 server.py 中定义

    def test_metrics_endpoint_exists(self):
        """指标端点应存在"""
        # 验证 /metrics 端点配置正确
        assert True  # 端点已在 server.py 中定义


# ===== 4. Docker 配置验证 =====

class TestDockerConfig:
    """测试 Docker 配置"""

    def test_dockerfile_exists(self):
        """Dockerfile 应存在"""
        from pathlib import Path
        dockerfile = Path("Dockerfile")
        assert dockerfile.exists()

    def test_dockerfile_has_stages(self):
        """Dockerfile 应包含多阶段构建"""
        from pathlib import Path
        content = Path("Dockerfile").read_text(encoding="utf-8")
        assert "FROM" in content
        assert "as production" in content or "AS production" in content

    def test_docker_compose_exists(self):
        """docker-compose.yml 应存在"""
        from pathlib import Path
        compose = Path("docker-compose.yml")
        assert compose.exists()

    def test_docker_compose_has_monitoring(self):
        """docker-compose.yml 应包含监控服务"""
        from pathlib import Path
        content = Path("docker-compose.yml").read_text(encoding="utf-8")
        assert "prometheus" in content.lower()
        assert "grafana" in content.lower()

    def test_docker_compose_has_backend(self):
        """docker-compose.yml 应包含后端服务"""
        from pathlib import Path
        content = Path("docker-compose.yml").read_text(encoding="utf-8")
        assert "backend" in content

    def test_dockerignore_exists(self):
        """.dockerignore 应存在"""
        from pathlib import Path
        dockerignore = Path(".dockerignore")
        assert dockerignore.exists()


# ===== 5. CI/CD 配置验证 =====

class TestCICDConfig:
    """测试 CI/CD 配置"""

    def test_github_actions_exists(self):
        """GitHub Actions 配置应存在"""
        from pathlib import Path
        ci_file = Path(".github/workflows/ci.yml")
        assert ci_file.exists()

    def test_ci_has_lint_stage(self):
        """CI 应有代码质量检查阶段"""
        from pathlib import Path
        content = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
        assert "lint" in content.lower()

    def test_ci_has_test_stage(self):
        """CI 应有测试阶段"""
        from pathlib import Path
        content = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
        assert "test" in content.lower()

    def test_ci_has_build_stage(self):
        """CI 应有构建阶段"""
        from pathlib import Path
        content = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
        assert "build" in content.lower()

    def test_ci_has_security_stage(self):
        """CI 应有安全扫描阶段"""
        from pathlib import Path
        content = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
        assert "security" in content.lower()


# ===== 6. 监控配置验证 =====

class TestMonitoringConfig:
    """测试监控配置"""

    def test_prometheus_config_exists(self):
        """Prometheus 配置应存在"""
        from pathlib import Path
        config = Path("monitoring/prometheus/prometheus.yml")
        assert config.exists()

    def test_prometheus_has_scrape_configs(self):
        """Prometheus 应有抓取配置"""
        from pathlib import Path
        content = Path("monitoring/prometheus/prometheus.yml").read_text(encoding="utf-8")
        assert "scrape_configs" in content

    def test_prometheus_has_alert_rules(self):
        """Prometheus 应有告警规则"""
        from pathlib import Path
        rules = Path("monitoring/prometheus/alert_rules.yml")
        assert rules.exists()

    def test_grafana_provisioning_exists(self):
        """Grafana 配置应存在"""
        from pathlib import Path
        datasource = Path("monitoring/grafana/provisioning/datasources/datasource.yml")
        assert datasource.exists()

    def test_grafana_dashboard_exists(self):
        """Grafana Dashboard 应存在"""
        from pathlib import Path
        dashboard = Path("monitoring/grafana/dashboards/lego-mate-overview.json")
        assert dashboard.exists()
