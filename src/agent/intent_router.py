"""意图路由器 - 三级路由架构 v2（修复版）

根据用户消息的意图类型，精确路由到不同的处理链路：

L1 快速回复（<0.2s）
  └ 问候/感谢/告别/确认/自我介绍/情绪安抚

L2 工具直调（<1s，不调 LLM）
  └ 零件替代查询 / 说明书检索 / 图片识别 / 成品验收

L3 完整 Agent（2-5s，LLM 推理）
  └ 复杂问题 / 多步推理 / 模糊需求 / 闲聊

修复内容：
- has_image 不再强制走 PARSE_IMAGE，根据文本判断
- L1 情绪检测加否定词过滤
- L2 检测加否定词过滤
- 参数提取失败时降级到 L3
- 空消息/纯符号拦截
- 指代消解（需要上下文）
- 缓存可清除
"""

import re
import threading
from typing import Optional
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache


class IntentType(Enum):
    """意图类型枚举"""
    # L1: 快速回复
    GREETING = "greeting"
    THANKS = "thanks"
    FAREWELL = "farewell"
    AFFIRM = "affirm"
    WHO_ARE_YOU = "who_are_you"
    FRUSTRATION = "frustration"

    # L2: 工具直调
    FIND_ALTERNATIVE = "find_alternative"
    SEARCH_MANUAL = "search_manual"
    PARSE_IMAGE = "parse_image"
    VERIFY_BUILD = "verify_build"

    # L3: 完整 Agent
    COMPLEX = "complex"
    CHAT = "chat"


class ResponseLevel(Enum):
    """响应级别"""
    L1_QUICK = "l1_quick"       # 快速回复
    L2_TOOL = "l2_tool"         # 工具直调
    L3_AGENT = "l3_agent"       # 完整 Agent


@dataclass
class Intent:
    """意图识别结果"""
    intent_type: IntentType
    level: ResponseLevel
    confidence: float  # 0-1
    tool_name: Optional[str] = None  # L2 需要
    tool_args: Optional[dict] = None  # L2 需要
    raw_message: str = ""
    text2api_result: Optional[dict] = None  # Text2API 结果（L3 层）


# ===== 预编译正则（模块加载时一次性编译） =====

def _compile_patterns(patterns: list[str]) -> list[re.Pattern]:
    """预编译正则模式列表"""
    return [re.compile(p, re.IGNORECASE | re.UNICODE) for p in patterns]


# ===== 否定词检测 =====

NEGATION_WORDS = frozenset([
    "不", "没", "别", "勿", "未", "非", "莫", "毋",
    "没有", "不是", "不要", "不用", "不必", "别", "并未",
    "不太", "不怎么", "谈不上",
])

NEGATION_PATTERN = re.compile(
    r"(不|没|别|勿|未|非|莫|毋|没有|不是|不要|不用|不必|不太|不怎么|谈不上)",
    re.UNICODE
)


def _has_negation_before(message: str, match_start: int, window: int = 6) -> bool:
    """
    检查匹配位置前是否有否定词。
    在 match_start 前 window 个字符内查找否定词。
    """
    prefix = message[max(0, match_start - window):match_start]
    return bool(NEGATION_PATTERN.search(prefix))


def _is_negated(message: str, patterns: list[re.Pattern]) -> bool:
    """检查消息是否匹配模式但被否定"""
    for pattern in patterns:
        match = pattern.search(message)
        if match and _has_negation_before(message, match.start()):
            return True
    return False


# ===== L2 工具直调规则 =====

# 零件替代查询
ALTERNATIVE_PATTERNS = _compile_patterns([
    r"(.*)(有)?什么替代",
    r"(.*)(可以)?代替(.*)",
    r"(.*)(的)?替代方案",
    r"(.*)(的)?替换(.*)",
    r"(.*)的替代$",
    r"缺了(.*)怎么办",
    r"没有(.*)可以用(.*)",
    r"(.*)(的)?兼容(.*)",
    r"(.*)有替代(吗)?",           # 新增: "有替代吗"
    r"(.*)能替代(.*)",            # 新增: "能替代"
    r"(.*)可以替换(.*)",          # 新增: "可以替换"
    r"find.*alternative.*for",
    r"substitute.*for",
    r"replacement.*for",
])

# 说明书检索
MANUAL_PATTERNS = _compile_patterns([
    r"第?\s*(\d+)\s*步(.*)(怎么|如何)(拼|做|搭|装)",
    r"第?\s*(\d+)\s*步(.*)(是)?什么",
    r"第?\s*(\d+)\s*步",
    r"step\s*(\d+)",
    r"怎么拼第(\d+)步",
    r"(\d+)步(.*)怎么",
])

# 图片识别
IMAGE_PATTERNS = _compile_patterns([
    r"(这|那)(是)?(什么|哪个)零件",
    r"识别(这个|那个|图片|一下)",
    r"(这个|那个)(零件)?叫什么",
    r"what.*part.*is.*(this|that)",
    r"identify.*part",
])

# 成品验收
VERIFY_PATTERNS = _compile_patterns([
    r"(帮)?我(看|检查|验收|核对)(一?下)?(对吗|对么|对不对|正确吗|是否正确|正确么)",
    r"(检查|看)(一?下)?(对吗|对么|对不对|正确吗|正确么)",
    r"(成品|作品|拼的)(对吗|对么|对不对|正确吗)",
    r"(有没有|是不是)(拼|搭|装)错",
    r"(检查|验收).*(正确|对吗|是否正确)",  # 新增: "检查成品是否正确"
    r"(帮)?我.*(正确|对吗|是否正确)",       # 新增: "帮我看是否正确"
    r"check.*(build|correct)",
    r"is.*(this|my).*correct",
    r"verify.*build",
])

# 步骤号提取正则（预编译）
STEP_NUMBER_PATTERNS = _compile_patterns([
    r"第?\s*(\d+)\s*步",
    r"step\s*(\d+)",
    r"(\d+)步",
])

# 中文数字映射
CN_NUMBERS = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15,
    "二十": 20, "三十": 30, "四十": 40, "五十": 50,
    "六十": 60, "七十": 70, "八十": 80, "九十": 90, "一百": 100,
}

# 中文数字步骤提取
CN_STEP_PATTERN = re.compile(r"第\s*([一二三四五六七八九十百]+)\s*步", re.UNICODE)

# 零件信息提取正则（预编译）
PART_INFO_PATTERN = re.compile(r"(\d{4,5})|(\d+x\d+)", re.IGNORECASE)

# 常见颜色集合（用于快速查找）
COLORS = frozenset([
    "红", "蓝", "黄", "绿", "白", "黑", "灰", "橙", "棕", "紫", "粉", "透明",
    "深红", "浅红", "深蓝", "浅蓝",
    "red", "blue", "yellow", "green", "white", "black", "gray", "orange",
])

# 指代词（需要上下文才能解析）
REFERENCE_WORDS = frozenset(["这一步", "上一步", "下一步", "这步", "前一步", "后一步", "那一步"])


# ===== L1 规则（正则直接内联，避免导入链依赖） =====

_L1_GREETING = _compile_patterns([
    r"^(你好|您好|hi|hello|hey|嗨|哈喽|早上好|下午好|晚上好|早安|午安|晚安)[\s!！.。]*$",
    r"^(在吗|在不在|有人吗|在么)[\s?？]*$",
    r"^(man|yo|sup|bro|dude)[\s!！.。]*$",  # 英文口语问候
])

_L1_THANKS = _compile_patterns([
    r"^(谢谢|感谢|thanks|thank you|thx|多谢|谢了|辛苦了)[\s!！.。]*$",
])

_L1_FAREWELL = _compile_patterns([
    r"^(拜拜|再见|bye|goodbye|see you|晚安|下次见)[\s!！.。]*$",
])

_L1_AFFIRM = _compile_patterns([
    r"^(好的|好|嗯|哦|了解|明白|知道了|ok|okay|好的吧|行|可以)[\s!！.。]*$",
])

_L1_WHO = _compile_patterns([
    r"^(你是谁|你叫什么|介绍一下自己|你是做什么的|你能做什么|你可以做什么|你有什么功能)",
])

# L1 情绪（更严格的匹配，避免误判）
_L1_FRUSTRATION = _compile_patterns([
    r"(烦死了|烦死|好烦|真烦|太烦了)",
    r"(好难|太难了|太难了|真难|太难了)",
    r"(不会拼|不会做|不会搭|不会装)",
    r"(拼不好|做不好|搭不好)",
    r"(崩溃了|要崩溃|崩溃)",
    r"(头疼|头好疼|好头疼)",
    r"(晕了|好晕|太晕了)",
    r"(不想拼了|不想做了|不拼了|放弃了)",
    r"(救命|救救我|帮帮我)",
])

L1_RULES: list[tuple[list[re.Pattern], IntentType]] = [
    (_L1_GREETING, IntentType.GREETING),
    (_L1_THANKS, IntentType.THANKS),
    (_L1_FAREWELL, IntentType.FAREWELL),
    (_L1_AFFIRM, IntentType.AFFIRM),
    (_L1_WHO, IntentType.WHO_ARE_YOU),
    (_L1_FRUSTRATION, IntentType.FRUSTRATION),
]


# ===== 辅助函数 =====

def _match_patterns(message: str, patterns: list[re.Pattern]) -> Optional[re.Match]:
    """尝试匹配一组预编译正则模式（短路匹配，命中即返回）"""
    for pattern in patterns:
        match = pattern.search(message)
        if match:
            return match
    return None


def _match_patterns_no_negation(message: str, patterns: list[re.Pattern]) -> Optional[re.Match]:
    """匹配模式，但排除被否定的情况"""
    for pattern in patterns:
        match = pattern.search(message)
        if match:
            # 检查是否有否定词在匹配位置之前
            if not _has_negation_before(message, match.start()):
                return match
    return None


def _extract_step_number(message: str) -> Optional[int]:
    """从消息中提取步骤号（支持阿拉伯数字和中文数字）"""
    # 阿拉伯数字
    for pattern in STEP_NUMBER_PATTERNS:
        match = pattern.search(message)
        if match:
            return int(match.group(1))
    # 中文数字
    cn_match = CN_STEP_PATTERN.search(message)
    if cn_match:
        cn_num = cn_match.group(1)
        return CN_NUMBERS.get(cn_num)
    return None


def _extract_part_info(message: str) -> dict:
    """从消息中提取零件信息（颜色+名称/编号）"""
    info: dict = {"part_name": "", "color": ""}

    msg_lower = message.lower()
    # 优先匹配复合颜色（深红、浅蓝等）
    for color in ["深红", "浅红", "深蓝", "浅蓝", "透明"]:
        if color in msg_lower:
            info["color"] = color
            break
    else:
        for color in COLORS:
            if color in msg_lower:
                info["color"] = color
                break

    part_match = PART_INFO_PATTERN.search(message)
    if part_match:
        info["part_name"] = part_match.group()

    return info


def _has_reference(message: str) -> bool:
    """检查是否包含指代词（需要上下文）"""
    return any(ref in message for ref in REFERENCE_WORDS)


def _is_empty_or_symbol_only(message: str) -> bool:
    """检查是否为空消息或纯符号"""
    if not message.strip():
        return True
    # 移除所有标点/符号/emoji 后是否为空
    cleaned = re.sub(r'[\s!！.。,，?？;；:：""''（）()【】\[\]{}、\-\_\+\=\*\/\\\|@#$%^&~`😀-🙏🚀-🛿⭐✨❤️💙💚💛🧡💜🖤🤍💯✅❌⚡🔧🔍📷📖🧱🤖👤👋👌🙏💪🤔💭🎉]', '', message)
    return not cleaned.strip()


# ===== 上下文管理（用于指代消解） =====

class ConversationContext:
    """对话上下文（线程安全单例，记录最近提到的步骤号等）"""
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._last_step_number: Optional[int] = None
        self._last_set_id: str = ""

    @classmethod
    def get(cls) -> "ConversationContext":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def update_step(self, step: int):
        with self._lock:
            self._last_step_number = step

    def get_last_step(self) -> Optional[int]:
        with self._lock:
            return self._last_step_number

    def update_set(self, set_id: str):
        with self._lock:
            self._last_set_id = set_id

    def get_last_set(self) -> str:
        with self._lock:
            return self._last_set_id

    def reset(self):
        """重置上下文"""
        with self._lock:
            self._last_step_number = None
            self._last_set_id = ""


# 模块加载时立即创建实例
ConversationContext._instance = ConversationContext()


# ===== 核心路由函数 =====

@lru_cache(maxsize=256)
def _cached_classify(message: str, has_image: bool = False) -> Intent:
    """带缓存的意图分类（高频消息直接命中缓存）"""
    return _do_classify(message, has_image)


def _do_classify(message: str, has_image: bool = False) -> Intent:
    """执行意图分类（无缓存版本）"""
    msg = message.strip()

    # ===== 0. 空消息/纯符号拦截 =====
    if _is_empty_or_symbol_only(msg):
        return Intent(
            intent_type=IntentType.COMPLEX,
            level=ResponseLevel.L3_AGENT,
            confidence=0.5,
            raw_message=msg,
        )

    # ===== 1. 检查是否包含指代词（需要上下文） =====
    if _has_reference(msg):
        ctx = ConversationContext.get()
        last_step = ctx.get_last_step()
        if last_step:
            # 有上下文，替换指代
            if "这一步" in msg or "这步" in msg or "那一步" in msg:
                if "怎么拼" in msg or "如何" in msg:
                    return Intent(
                        intent_type=IntentType.SEARCH_MANUAL,
                        level=ResponseLevel.L2_TOOL,
                        confidence=0.8,
                        tool_name="search_manual_step",
                        tool_args={"step_number": last_step},
                        raw_message=msg,
                    )
            if "上一步" in msg or "前一步" in msg:
                prev_step = max(1, last_step - 1)
                return Intent(
                    intent_type=IntentType.SEARCH_MANUAL,
                    level=ResponseLevel.L2_TOOL,
                    confidence=0.8,
                    tool_name="search_manual_step",
                    tool_args={"step_number": prev_step},
                    raw_message=msg,
                )
            if "下一步" in msg or "后一步" in msg:
                next_step = last_step + 1
                return Intent(
                    intent_type=IntentType.SEARCH_MANUAL,
                    level=ResponseLevel.L2_TOOL,
                    confidence=0.8,
                    tool_name="search_manual_step",
                    tool_args={"step_number": next_step},
                    raw_message=msg,
                )
        # 有指代但无上下文 → 走 L3 让 LLM 处理
        return Intent(
            intent_type=IntentType.COMPLEX,
            level=ResponseLevel.L3_AGENT,
            confidence=0.6,
            raw_message=msg,
        )

    # ===== 2. L1: 快速回复（最高优先级，带否定检测） =====
    for patterns, intent_type in L1_RULES:
        match = _match_patterns(msg, patterns)
        if match:
            # 检查是否被否定（主要针对情绪类）
            if intent_type == IntentType.FRUSTRATION:
                if _has_negation_before(msg, match.start()):
                    continue  # 被否定，跳过
            return Intent(
                intent_type=intent_type,
                level=ResponseLevel.L1_QUICK,
                confidence=0.95,
                raw_message=msg,
            )

    # ===== 3. L2: 工具直调（带否定检测） =====

    # 图片识别（has_image 不再强制走 PARSE，根据文本判断）
    if has_image:
        # 带图片时，根据文本判断意图
        if _match_patterns(msg, VERIFY_PATTERNS):
            return Intent(
                intent_type=IntentType.VERIFY_BUILD,
                level=ResponseLevel.L2_TOOL,
                confidence=0.9,
                tool_name="verify_build_result",
                tool_args={},
                raw_message=msg,
            )
        if _match_patterns(msg, IMAGE_PATTERNS):
            return Intent(
                intent_type=IntentType.PARSE_IMAGE,
                level=ResponseLevel.L2_TOOL,
                confidence=0.9,
                tool_name="parse_lego_image",
                tool_args={"image_url": ""},
                raw_message=msg,
            )
        # 带图片但无明确指令 → 默认识别零件
        if not msg or len(msg) < 5:
            return Intent(
                intent_type=IntentType.PARSE_IMAGE,
                level=ResponseLevel.L2_TOOL,
                confidence=0.85,
                tool_name="parse_lego_image",
                tool_args={"image_url": ""},
                raw_message=msg,
            )

    # 无图片时的文本匹配
    if not has_image:
        if _match_patterns_no_negation(msg, IMAGE_PATTERNS):
            return Intent(
                intent_type=IntentType.PARSE_IMAGE,
                level=ResponseLevel.L2_TOOL,
                confidence=0.9,
                tool_name="parse_lego_image",
                tool_args={"image_url": ""},
                raw_message=msg,
            )

    # 成品验收（带否定检测）
    if _match_patterns_no_negation(msg, VERIFY_PATTERNS):
        return Intent(
            intent_type=IntentType.VERIFY_BUILD,
            level=ResponseLevel.L2_TOOL,
            confidence=0.85,
            tool_name="verify_build_result",
            tool_args={},
            raw_message=msg,
        )

    # 零件替代查询（带否定检测 + 参数校验）
    if _match_patterns_no_negation(msg, ALTERNATIVE_PATTERNS):
        part_info = _extract_part_info(msg)
        # 参数为空时降级到 L3
        if not part_info["part_name"] and not part_info["color"]:
            return Intent(
                intent_type=IntentType.COMPLEX,
                level=ResponseLevel.L3_AGENT,
                confidence=0.7,
                raw_message=msg,
            )
        return Intent(
            intent_type=IntentType.FIND_ALTERNATIVE,
            level=ResponseLevel.L2_TOOL,
            confidence=0.8,
            tool_name="find_part_alternative",
            tool_args=part_info,
            raw_message=msg,
        )

    # 说明书检索（带否定检测 + 参数校验）
    step = _extract_step_number(msg)
    if step is not None:
        # 检查是否被否定
        manual_match = _match_patterns(msg, MANUAL_PATTERNS)
        if manual_match and not _has_negation_before(msg, manual_match.start()):
            # 步骤号合理性检查
            if 1 <= step <= 999:
                # 更新上下文
                ConversationContext.get().update_step(step)
                return Intent(
                    intent_type=IntentType.SEARCH_MANUAL,
                    level=ResponseLevel.L2_TOOL,
                    confidence=0.85,
                    tool_name="search_manual_step",
                    tool_args={"step_number": step},
                    raw_message=msg,
                )

    # ===== 4. L3: Text2API 尝试 → 完整 Agent（兜底） =====

    # 4.1 先用 Text2API 尝试理解用户意图并选择 API
    try:
        from src.agent.text2api import get_text2api_engine
        from src.agent.api_registry import get_registry

        registry = get_registry()
        if registry.list_apis():  # 确保有注册的 API
            engine = get_text2api_engine()
            text2api_result = engine.run(msg)

            if text2api_result.get("success") and text2api_result.get("confidence", 0) > 0.7:
                # Text2API 成功，映射 api_name 到 IntentType
                api_name = text2api_result.get("api", "")
                api_to_intent = {
                    "parse_lego_image": IntentType.PARSE_IMAGE,
                    "find_part_alternative": IntentType.FIND_ALTERNATIVE,
                    "search_manual_step": IntentType.SEARCH_MANUAL,
                    "verify_build_result": IntentType.VERIFY_BUILD,
                }
                intent_type = api_to_intent.get(api_name, IntentType.COMPLEX)
                return Intent(
                    intent_type=intent_type,
                    level=ResponseLevel.L2_TOOL,
                    confidence=text2api_result.get("confidence", 0.7),
                    tool_name=api_name,
                    tool_args=text2api_result.get("parameters", {}),
                    raw_message=msg,
                    text2api_result=text2api_result,
                )
    except Exception:
        # Text2API 失败，继续走 fallback
        pass

    # 4.2 fallback 到完整 Agent
    return Intent(
        intent_type=IntentType.COMPLEX,
        level=ResponseLevel.L3_AGENT,
        confidence=0.7,
        raw_message=msg,
    )


def classify_intent(message: str, has_image: bool = False) -> Intent:
    """
    意图分类器 - 确定消息应该走哪级处理链路。

    性能优化：
    - 使用 LRU 缓存（256 条高频消息）
    - 所有正则预编译
    - 短路匹配（命中即返回）

    Args:
        message: 用户消息
        has_image: 是否附带图片

    Returns:
        Intent 对象
    """
    return _cached_classify(message.strip().lower(), has_image)


def get_intent_description(intent: Intent) -> str:
    """获取意图的描述（用于日志）"""
    level_names = {
        ResponseLevel.L1_QUICK: "⚡L1快速",
        ResponseLevel.L2_TOOL: "🔧L2工具",
        ResponseLevel.L3_AGENT: "🤖L3推理",
    }
    return f"{level_names.get(intent.level, '?')} | {intent.intent_type.value} | 置信度{intent.confidence:.0%}"


def get_cache_info() -> dict:
    """获取缓存统计信息"""
    cache = _cached_classify.cache_info()
    return {
        "hits": cache.hits,
        "misses": cache.misses,
        "maxsize": cache.maxsize,
        "currsize": cache.currsize,
        "hit_rate": cache.hits / (cache.hits + cache.misses) if (cache.hits + cache.misses) > 0 else 0,
    }


def clear_cache():
    """清除路由缓存（路由规则变更后调用）"""
    _cached_classify.cache_clear()
    ConversationContext.get().reset()
