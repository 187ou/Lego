"""Text2API 单元测试

覆盖：
- API Schema 生成
- 参数校验（正常/异常/边界）
- API 注册表
- Text2API 引擎（Mock LLM）
- 评估日志（线程安全）
"""

import threading
import time
import pytest
from unittest.mock import MagicMock, patch

from src.agent.text2api import (
    APISchema,
    APIParameter,
    APIRegistry,
    Text2APIEngine,
    EvaluationLog,
    get_evaluation_stats,
    get_evaluation_logs,
    clear_evaluation_logs,
)


# ===== Fixtures =====

@pytest.fixture
def sample_schema():
    """示例 API Schema"""
    return APISchema(
        name="find_part",
        description="查询零件替代方案",
        parameters=[
            APIParameter(name="part_name", type="string", description="零件名称", required=True),
            APIParameter(name="color", type="string", description="颜色", required=True),
            APIParameter(name="limit", type="integer", description="返回数量", required=False, default=5),
        ],
        returns="替代方案列表",
    )


@pytest.fixture
def sample_handler():
    """示例 handler"""
    def handler(part_name: str, color: str, limit: int = 5):
        return {"part_name": part_name, "color": color, "limit": limit}
    return handler


@pytest.fixture
def registry(sample_schema, sample_handler):
    """预填充的注册表"""
    reg = APIRegistry()
    reg.register(sample_schema, sample_handler)
    return reg


@pytest.fixture
def mock_llm():
    """Mock LLM"""
    return MagicMock()


@pytest.fixture(autouse=True)
def clear_logs():
    """每个测试前清空日志"""
    clear_evaluation_logs()
    yield
    clear_evaluation_logs()


# ===== 测试 API Schema =====

class TestAPISchema:
    def test_to_prompt_contains_name(self, sample_schema):
        prompt = sample_schema.to_prompt()
        assert "find_part" in prompt

    def test_to_prompt_contains_params(self, sample_schema):
        prompt = sample_schema.to_prompt()
        assert "part_name" in prompt
        assert "color" in prompt
        assert "limit" in prompt

    def test_to_prompt_shows_required(self, sample_schema):
        prompt = sample_schema.to_prompt()
        assert "必填" in prompt


# ===== 测试 API Registry =====

class TestAPIRegistry:
    def test_register_and_get(self, sample_schema, sample_handler):
        reg = APIRegistry()
        reg.register(sample_schema, sample_handler)

        assert reg.get_schema("find_part") == sample_schema
        assert reg.get_handler("find_part") == sample_handler

    def test_get_nonexistent_returns_none(self, registry):
        assert registry.get_schema("nonexistent") is None
        assert registry.get_handler("nonexistent") is None

    def test_list_apis(self, registry, sample_schema):
        apis = registry.list_apis()
        assert len(apis) == 1
        assert apis[0] == sample_schema

    def test_get_apis_prompt(self, registry):
        prompt = registry.get_apis_prompt()
        assert "find_part" in prompt


# ===== 测试参数校验 =====

class TestParameterValidation:
    def test_valid_params(self, registry, sample_schema):
        engine = Text2APIEngine(llm=MagicMock(), registry=registry)
        validated, error = engine._validate_params(
            sample_schema, {"part_name": "Brick", "color": "Red"}
        )
        assert error is None
        assert validated["part_name"] == "Brick"
        assert validated["color"] == "Red"
        assert validated["limit"] == 5  # 默认值

    def test_missing_required_param(self, registry, sample_schema):
        engine = Text2APIEngine(llm=MagicMock(), registry=registry)
        validated, error = engine._validate_params(
            sample_schema, {"part_name": "Brick"}  # 缺少 color
        )
        assert validated is None
        assert "缺少必填参数" in error
        assert "color" in error

    def test_empty_string_required_param(self, registry, sample_schema):
        engine = Text2APIEngine(llm=MagicMock(), registry=registry)
        validated, error = engine._validate_params(
            sample_schema, {"part_name": "", "color": "Red"}
        )
        assert validated is None
        assert "缺少必填参数" in error

    def test_whitespace_only_required_param(self, registry, sample_schema):
        engine = Text2APIEngine(llm=MagicMock(), registry=registry)
        validated, error = engine._validate_params(
            sample_schema, {"part_name": "   ", "color": "Red"}
        )
        assert validated is None
        assert "缺少必填参数" in error

    def test_integer_type_conversion(self, registry, sample_schema):
        engine = Text2APIEngine(llm=MagicMock(), registry=registry)
        validated, error = engine._validate_params(
            sample_schema, {"part_name": "Brick", "color": "Red", "limit": "10"}
        )
        assert error is None
        assert validated["limit"] == 10
        assert isinstance(validated["limit"], int)

    def test_integer_float_string_conversion(self, registry, sample_schema):
        engine = Text2APIEngine(llm=MagicMock(), registry=registry)
        validated, error = engine._validate_params(
            sample_schema, {"part_name": "Brick", "color": "Red", "limit": "3.14"}
        )
        assert error is None
        assert validated["limit"] == 3

    def test_integer_invalid_conversion(self, registry, sample_schema):
        engine = Text2APIEngine(llm=MagicMock(), registry=registry)
        validated, error = engine._validate_params(
            sample_schema, {"part_name": "Brick", "color": "Red", "limit": "abc"}
        )
        assert validated is None
        assert "类型错误" in error

    def test_boolean_type_conversion_true(self, registry):
        schema = APISchema(
            name="test",
            description="test",
            parameters=[APIParameter(name="flag", type="boolean", description="flag")],
        )
        engine = Text2APIEngine(llm=MagicMock(), registry=registry)
        validated, error = engine._validate_params(schema, {"flag": "true"})
        assert error is None
        assert validated["flag"] is True

    def test_boolean_type_conversion_false(self, registry):
        schema = APISchema(
            name="test",
            description="test",
            parameters=[APIParameter(name="flag", type="boolean", description="flag")],
        )
        engine = Text2APIEngine(llm=MagicMock(), registry=registry)
        validated, error = engine._validate_params(schema, {"flag": "false"})
        assert error is None
        assert validated["flag"] is False

    def test_optional_param_uses_default(self, registry, sample_schema):
        engine = Text2APIEngine(llm=MagicMock(), registry=registry)
        validated, error = engine._validate_params(
            sample_schema, {"part_name": "Brick", "color": "Red"}
        )
        assert error is None
        assert validated["limit"] == 5  # 默认值

    def test_optional_param_no_default_skipped(self, registry):
        schema = APISchema(
            name="test",
            description="test",
            parameters=[
                APIParameter(name="required_p", type="string", description="required", required=True),
                APIParameter(name="optional_p", type="string", description="optional", required=False),
            ],
        )
        engine = Text2APIEngine(llm=MagicMock(), registry=registry)
        validated, error = engine._validate_params(schema, {"required_p": "value"})
        assert error is None
        assert "optional_p" not in validated


# ===== 测试 execute =====

class TestExecute:
    def test_execute_success(self, registry, sample_handler, sample_schema):
        engine = Text2APIEngine(llm=MagicMock(), registry=registry)
        result = engine.execute("find_part", {"part_name": "Brick", "color": "Red"}, user_input="test")
        assert result["success"] is True
        assert result["result"]["part_name"] == "Brick"

    def test_execute_unregistered_api(self, registry):
        engine = Text2APIEngine(llm=MagicMock(), registry=registry)
        result = engine.execute("nonexistent", {}, user_input="test")
        assert result["success"] is False
        assert "未注册" in result["error"]

    def test_execute_validation_failure(self, registry):
        engine = Text2APIEngine(llm=MagicMock(), registry=registry)
        result = engine.execute("find_part", {"part_name": ""}, user_input="test")
        assert result["success"] is False
        assert "缺少必填参数" in result["error"]

    def test_execute_handler_exception(self, registry):
        def bad_handler(**kwargs):
            raise ValueError("handler error")

        registry.register(
            APISchema(name="bad", description="bad", parameters=[]),
            bad_handler,
        )
        engine = Text2APIEngine(llm=MagicMock(), registry=registry)
        result = engine.execute("bad", {}, user_input="test")
        # 验证失败被正确记录
        assert result["success"] is False
        assert result["api"] == "bad"
        # 验证日志记录了失败
        logs = get_evaluation_logs()
        assert len(logs) == 1
        assert logs[0].success is False


# ===== 测试评估日志 =====

class TestEvaluationLogs:
    def test_log_success(self, registry):
        engine = Text2APIEngine(llm=MagicMock(), registry=registry)
        engine.execute("find_part", {"part_name": "Brick", "color": "Red"}, user_input="test")

        logs = get_evaluation_logs()
        assert len(logs) == 1
        assert logs[0].success is True
        assert logs[0].selected_api == "find_part"

    def test_log_failure(self, registry):
        engine = Text2APIEngine(llm=MagicMock(), registry=registry)
        engine.execute("nonexistent", {}, user_input="test")

        logs = get_evaluation_logs()
        assert len(logs) == 1
        assert logs[0].success is False

    def test_stats_calculation(self, registry):
        engine = Text2APIEngine(llm=MagicMock(), registry=registry)
        # 3 次成功
        for _ in range(3):
            engine.execute("find_part", {"part_name": "B", "color": "R"}, user_input="t")
        # 1 次失败
        engine.execute("nonexistent", {}, user_input="t")

        stats = get_evaluation_stats()
        assert stats["total"] == 4
        assert stats["success_count"] == 3
        assert stats["success_rate"] == 0.75
        assert stats["error_count"] == 1

    def test_stats_empty_logs(self):
        stats = get_evaluation_stats()
        assert stats["total"] == 0
        assert stats["success_rate"] == 0.0

    def test_clear_logs(self, registry):
        engine = Text2APIEngine(llm=MagicMock(), registry=registry)
        engine.execute("find_part", {"part_name": "B", "color": "R"}, user_input="t")
        assert len(get_evaluation_logs()) == 1

        clear_evaluation_logs()
        assert len(get_evaluation_logs()) == 0

    def test_concurrent_logging(self, registry):
        """并发写入日志（线程安全测试）"""
        engine = Text2APIEngine(llm=MagicMock(), registry=registry)
        errors = []

        def log_call():
            try:
                for _ in range(10):
                    engine.execute("find_part", {"part_name": "B", "color": "R"}, user_input="t")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=log_call) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(get_evaluation_logs()) == 50  # 5 threads * 10 calls


# ===== 测试 select_api 边界 =====

class TestSelectAPIBoundary:
    def test_empty_input(self, registry):
        engine = Text2APIEngine(llm=MagicMock(), registry=registry)
        result = engine.select_api("")
        assert result["api"] == "unknown"

    def test_whitespace_input(self, registry):
        engine = Text2APIEngine(llm=MagicMock(), registry=registry)
        result = engine.select_api("   ")
        assert result["api"] == "unknown"

    def test_none_input(self, registry):
        engine = Text2APIEngine(llm=MagicMock(), registry=registry)
        result = engine.select_api(None)
        assert result["api"] == "unknown"


# ===== 测试 _parse_response =====

class TestParseResponse:
    def test_valid_json(self, registry):
        engine = Text2APIEngine(llm=MagicMock(), registry=registry)
        result = engine._parse_response('{"api": "find_part", "parameters": {}, "confidence": 0.9}')
        assert result["api"] == "find_part"
        assert result["confidence"] == 0.9

    def test_json_in_code_block(self, registry):
        engine = Text2APIEngine(llm=MagicMock(), registry=registry)
        raw = '```json\n{"api": "find_part", "parameters": {}, "confidence": 0.9}\n```'
        result = engine._parse_response(raw)
        assert result["api"] == "find_part"

    def test_invalid_json(self, registry):
        engine = Text2APIEngine(llm=MagicMock(), registry=registry)
        result = engine._parse_response("not json at all")
        assert result["api"] == "unknown"
        assert "error" in result

    def test_empty_string(self, registry):
        engine = Text2APIEngine(llm=MagicMock(), registry=registry)
        result = engine._parse_response("")
        assert result["api"] == "unknown"

    def test_nested_json(self, registry):
        engine = Text2APIEngine(llm=MagicMock(), registry=registry)
        raw = '```json\n{"api": "find_part", "parameters": {"part_name": "Brick"}, "confidence": 0.95}\n```'
        result = engine._parse_response(raw)
        assert result["api"] == "find_part"
        assert result["parameters"]["part_name"] == "Brick"
