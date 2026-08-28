"""输出解析器 - 容错解析 LLM 输出"""

import json
import re
from typing import Any, Optional, Type

from pydantic import BaseModel, ValidationError


class OutputParser:
    """输出解析器 - 容错解析 LLM 输出"""

    @staticmethod
    def parse_json(text: str) -> Optional[dict]:
        """容错 JSON 解析

        支持:
        1. 标准 JSON
        2. Markdown 代码块中的 JSON
        3. 带前缀/后缀文本的 JSON
        """
        if not text:
            return None

        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 提取 JSON 块
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 提取裸 JSON
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        return None

    @staticmethod
    def parse_with_validation(text: str, model: Type[BaseModel]) -> Optional[BaseModel]:
        """带校验的解析"""
        data = OutputParser.parse_json(text)
        if data is None:
            return None
        try:
            return model(**data)
        except ValidationError:
            return None

    @staticmethod
    def safe_extract(text: str, field: str, default: Any = None) -> Any:
        """安全提取字段"""
        data = OutputParser.parse_json(text)
        if data and isinstance(data, dict):
            return data.get(field, default)
        return default
