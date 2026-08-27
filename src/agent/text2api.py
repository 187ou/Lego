"""Text2API 工具调用层

将工具/能力封装为标准化 API Schema，LLM 基于用户意图动态选择并编排 API 调用。
支持工具热插拔扩展——新增工具只需注册 Schema，无需修改主流程。

核心流程：
1. 用户输入 → LLM 理解意图
2. 从 API Registry 中选择最合适的 API
3. 解析参数并调用
4. 返回结果

评估日志：
- 每次调用自动记录到 evaluation_logs
- 提供 get_evaluation_stats() 统计准确率
"""

import json
import re
import time
import logging
import threading
from typing import Any, Optional
from dataclasses import dataclass, field
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

# ===== 线程锁（评估日志并发安全） =====
_evaluation_logs_lock = threading.Lock()


# ===== 评估日志 =====

@dataclass
class EvaluationLog:
    """单次调用评估日志"""
    timestamp: float
    user_input: str
    selected_api: str
    parameters: dict
    confidence: float
    success: bool
    error: str = ""
    response_time_ms: float = 0.0


# 全局评估日志存储
_evaluation_logs: list[EvaluationLog] = []


def get_evaluation_logs() -> list[EvaluationLog]:
    """获取所有评估日志"""
    return _evaluation_logs.copy()


def get_evaluation_stats() -> dict:
    """
    获取评估统计

    Returns:
        {
            "total": 总调用次数,
            "success_count": 成功次数,
            "success_rate": 成功率,
            "avg_confidence": 平均置信度,
            "avg_response_time_ms": 平均响应时间,
            "api_distribution": {api_name: 调用次数},
            "error_count": 错误次数
        }
    """
    if not _evaluation_logs:
        return {
            "total": 0,
            "success_count": 0,
            "success_rate": 0.0,
            "avg_confidence": 0.0,
            "avg_response_time_ms": 0.0,
            "api_distribution": {},
            "error_count": 0,
        }

    total = len(_evaluation_logs)
    success_count = sum(1 for log in _evaluation_logs if log.success)
    avg_confidence = sum(log.confidence for log in _evaluation_logs) / total
    avg_response_time = sum(log.response_time_ms for log in _evaluation_logs) / total

    # API 分布统计
    api_distribution = {}
    for log in _evaluation_logs:
        api_distribution[log.selected_api] = api_distribution.get(log.selected_api, 0) + 1

    return {
        "total": total,
        "success_count": success_count,
        "success_rate": success_count / total,
        "avg_confidence": round(avg_confidence, 3),
        "avg_response_time_ms": round(avg_response_time, 1),
        "api_distribution": api_distribution,
        "error_count": total - success_count,
    }


def clear_evaluation_logs():
    """清空评估日志"""
    with _evaluation_logs_lock:
        _evaluation_logs.clear()


# ===== API Schema 定义 =====

@dataclass
class APIParameter:
    """API 参数定义"""
    name: str
    type: str  # string, integer, boolean, array, object
    description: str
    required: bool = True
    default: Any = None


@dataclass
class APISchema:
    """API 标准化描述"""
    name: str
    description: str
    parameters: list[APIParameter]
    returns: str = ""
    examples: list[str] = field(default_factory=list)

    def to_prompt(self) -> str:
        """转换为 LLM 可理解的 prompt 格式"""
        params_desc = []
        for p in self.parameters:
            req_mark = "（必填）" if p.required else "（可选）"
            default_str = f"，默认: {p.default}" if p.default is not None else ""
            params_desc.append(f"    - {p.name} ({p.type}){req_mark}: {p.description}{default_str}")

        examples_str = ""
        if self.examples:
            examples_str = "\n  示例：\n" + "\n".join(f"    - {ex}" for ex in self.examples)

        return f"""### {self.name}
  描述：{self.description}
  参数：
{chr(10).join(params_desc)}
  返回：{self.returns}{examples_str}"""


# ===== API 注册表 =====

class APIRegistry:
    """API 注册表——所有工具注册到这里"""

    def __init__(self):
        self._schemas: dict[str, APISchema] = {}
        self._handlers: dict[str, callable] = {}

    def register(self, schema: APISchema, handler: callable):
        """注册一个 API"""
        self._schemas[schema.name] = schema
        self._handlers[schema.name] = handler

    def get_schema(self, name: str) -> Optional[APISchema]:
        return self._schemas.get(name)

    def get_handler(self, name: str) -> Optional[callable]:
        return self._handlers.get(name)

    def list_apis(self) -> list[APISchema]:
        return list(self._schemas.values())

    def get_apis_prompt(self) -> str:
        """生成所有 API 的 prompt 描述"""
        return "\n\n".join(schema.to_prompt() for schema in self._schemas.values())


# ===== 全局注册表实例 =

_registry = APIRegistry()


def get_registry() -> APIRegistry:
    """获取全局 API 注册表"""
    return _registry


# ===== Text2API 引擎 =====

# LLM 选择 API 的 system prompt
SELECT_API_PROMPT = """你是 LEGO-Mate 的 API 路由器。
根据用户输入，从可用 API 中选择最合适的一个，并提取参数。

只返回 JSON，不要解释：
```json
{
  "api": "api_name",
  "parameters": {
    "param1": "value1",
    "param2": "value2"
  },
  "confidence": 0.95
}
```

如果无法确定 API，返回：
```json
{
  "api": "unknown",
  "parameters": {},
  "confidence": 0.0
}
```
"""


class Text2APIEngine:
    """Text2API 引擎——LLM 动态选择并调用 API"""

    def __init__(self, llm: BaseChatModel, registry: APIRegistry = None):
        self.llm = llm
        self.registry = registry or get_registry()

    def select_api(self, user_input: str) -> dict:
        """
        LLM 根据用户输入选择最合适的 API

        Returns:
            {"api": str, "parameters": dict, "confidence": float}
        """
        # 边界：空输入检查
        if not user_input or not user_input.strip():
            return {"api": "unknown", "parameters": {}, "confidence": 0.0, "error": "用户输入为空"}

        apis_prompt = self.registry.get_apis_prompt()
        messages = [
            SystemMessage(content=SELECT_API_PROMPT + "\n\n## 可用 API\n" + apis_prompt),
            HumanMessage(content=f"用户输入：{user_input}"),
        ]
        try:
            response = self.llm.invoke(messages)
            raw = response.content if hasattr(response, "content") else str(response)
            # 边界：LLM 返回空内容
            if not raw or not raw.strip():
                return {"api": "unknown", "parameters": {}, "confidence": 0.0, "error": "LLM 返回空内容"}
            return self._parse_response(raw)
        except Exception as e:
            return {"api": "unknown", "parameters": {}, "confidence": 0.0, "error": str(e)}

    def execute(self, api_name: str, parameters: dict, user_input: str = "") -> dict:
        """
        执行指定 API（含参数校验 + 评估日志）

        Args:
            api_name: API 名称
            parameters: 调用参数
            user_input: 原始用户输入（用于日志）

        Returns:
            API 执行结果
        """
        start_time = time.time()

        # 1. 检查 API 是否注册
        handler = self.registry.get_handler(api_name)
        if handler is None:
            result = {"error": f"API '{api_name}' 未注册", "success": False}
            self._log_evaluation(user_input, api_name, parameters, 0.0, False,
                                 result["error"], time.time() - start_time)
            return result

        # 2. 参数校验
        schema = self.registry.get_schema(api_name)
        if schema:
            validated, error = self._validate_params(schema, parameters)
            if not validated:
                result = {"error": error, "success": False, "api": api_name}
                self._log_evaluation(user_input, api_name, parameters, 0.0, False,
                                     error, time.time() - start_time)
                return result
            parameters = validated  # 使用校验后的参数（可能包含类型转换）

        # 3. 执行 API
        try:
            result = handler(**parameters)
            self._log_evaluation(user_input, api_name, parameters, 1.0, True, "",
                                 time.time() - start_time)
            return {"result": result, "success": True, "api": api_name}
        except Exception as e:
            result = {"error": str(e), "success": False, "api": api_name}
            self._log_evaluation(user_input, api_name, parameters, 1.0, False,
                                 str(e), time.time() - start_time)
            return result

    def _validate_params(self, schema: APISchema, parameters: dict) -> tuple:
        """
        校验并转换参数

        Returns:
            (validated_params, None) 校验通过
            (None, error_message) 校验失败
        """
        validated = {}

        for param in schema.parameters:
            value = parameters.get(param.name)

            # 边界：参数不存在 或 为空字符串
            if value is None or (isinstance(value, str) and value.strip() == ""):
                if param.required:
                    return None, f"缺少必填参数: {param.name}"
                # 可选参数：使用默认值或跳过
                if param.default is not None:
                    validated[param.name] = param.default
                continue

            # 类型转换
            try:
                if param.type == "integer":
                    # 边界：浮点数字符串 "3.14" → 3
                    validated[param.name] = int(float(value))
                elif param.type == "number":
                    validated[param.name] = float(value)
                elif param.type == "boolean":
                    if isinstance(value, str):
                        validated[param.name] = value.lower() in ("true", "1", "yes")
                    else:
                        validated[param.name] = bool(value)
                elif param.type == "string":
                    validated[param.name] = str(value)
                else:
                    validated[param.name] = value  # 其他类型不转换
            except (ValueError, TypeError):
                return None, f"参数 {param.name} 类型错误: 期望 {param.type}，得到 '{value}'"

        return validated, None

    def run(self, user_input: str) -> dict:
        """
        完整流程：选择 API → 执行（含日志） → 返回结果

        Returns:
            {
                "success": bool,
                "api": str,
                "result": Any,
                "confidence": float,
                "error": str (if failed)
            }
        """
        # 1. 选择 API
        selection = self.select_api(user_input)
        api_name = selection.get("api", "unknown")
        parameters = selection.get("parameters", {})
        confidence = selection.get("confidence", 0.0)

        if api_name == "unknown" or confidence < 0.5:
            return {
                "success": False,
                "api": api_name,
                "confidence": confidence,
                "error": "无法确定合适的 API",
            }

        # 2. 执行 API（execute 内部记录日志）
        result = self.execute(api_name, parameters, user_input=user_input)
        result["confidence"] = confidence
        return result

    def _log_evaluation(self, user_input: str, api_name: str, parameters: dict,
                        confidence: float, success: bool, error: str, elapsed: float):
        """记录评估日志（线程安全）"""
        log = EvaluationLog(
            timestamp=time.time(),
            user_input=user_input,
            selected_api=api_name,
            parameters=parameters,
            confidence=confidence,
            success=success,
            error=error,
            response_time_ms=round(elapsed * 1000, 1),
        )
        # 线程安全写入
        with _evaluation_logs_lock:
            _evaluation_logs.append(log)

        # 同时输出到 logger
        status = "SUCCESS" if success else "FAILED"
        logger.info(
            f"[Text2API] {status} | api={api_name} | confidence={confidence:.2f} | "
            f"time={log.response_time_ms:.1f}ms | input={user_input[:50]}"
        )

    def _parse_response(self, raw: str) -> dict:
        """解析 LLM 返回的 JSON"""
        # 尝试直接解析
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # 尝试提取 JSON 块
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试提取裸 JSON
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        return {"api": "unknown", "parameters": {}, "confidence": 0.0, "error": "解析失败"}


# ===== 便捷函数 =====

def get_text2api_engine(llm: BaseChatModel = None) -> Text2APIEngine:
    """获取 Text2API 引擎（懒加载 LLM）"""
    if llm is None:
        from langchain_openai import ChatOpenAI
        from src.common.config import get_settings
        settings = get_settings()
        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0.3,  # 低温度提高路由稳定性
        )
    return Text2APIEngine(llm=llm)
