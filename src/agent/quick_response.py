"""快速回复模块 - 简单消息不走 LLM，直接返回预设回复"""

import re
import random
from typing import Optional


# ===== 快速回复规则 =====

# 问候语
GREETING_PATTERNS = [
    r"^(你好|您好|hi|hello|hey|嗨|哈喽|早上好|下午好|晚上好|早安|午安|晚安)[\s!！.。]*$",
    r"^(在吗|在不在|有人吗|在么)[\s?？]*$",
    r"^(man|yo|sup|bro|dude|guy|guys)[\s!！.。]*$",  # 新增：英文口语问候
    r"^(ok|okay|好的|好|嗯|哦|了解|明白|知道了)[\s!！.。]*$",  # 新增：确认/肯定
]

GREETING_RESPONSES = [
    "你好！我是 LEGO-Mate 🧱，有什么可以帮你的吗？\n\n你可以：\n1. 上传零件图片让我识别\n2. 问我「红色2x4砖有什么替代方案」\n3. 问我「第35步怎么拼」\n4. 上传成品图让我验收",
    "嗨！准备好拼乐高了吗？🧱\n\n试试问我：\n- 「第35步怎么拼？」\n- 「红色2x4砖有替代吗？」\n- 或者直接上传一张零件图片！",
    "你好呀！我是你的乐高拼搭助手 🤖\n\n我可以帮你：\n🔍 识别零件 | 🔧 查找替代 | 📖 说明书检索 | ✅ 成品验收",
]

# 感谢语
THANKS_PATTERNS = [
    r"^(谢谢|感谢|thanks|thank you|thx|多谢|谢了|辛苦了)[\s!！.。]*$",
]

THANKS_RESPONSES = [
    "不客气！有问题随时找我 😊",
    "不用谢！祝你拼搭愉快 🧱",
    "随时为你服务！继续拼搭吧～",
]

# 告别语
FAREWELL_PATTERNS = [
    r"^(拜拜|再见|bye|goodbye|see you|晚安|下次见)[\s!！.。]*$",
]

FAREWELL_RESPONSES = [
    "再见！祝你拼搭顺利 🧱👋",
    "拜拜！有问题随时回来找我～",
    "下次见！期待你的成品 ✨",
]

# 确认/肯定
AFFIRM_PATTERNS = [
    r"^(好的|好|嗯|哦|了解|明白|知道了|ok|okay|好的吧|行|可以)[\s!！.。]*$",
]

AFFIRM_RESPONSES = [
    "好的！有什么需要随时说 😊",
    "收到！还有什么可以帮你的？",
    "嗯嗯，继续吧～",
]

# 自我介绍请求
WHO_PATTERNS = [
    r"^(你是谁|你叫什么|介绍一下自己|你是做什么的|你能做什么|你可以做什么|你有什么功能)",
]

WHO_RESPONSES = [
    "我是 **LEGO-Mate** 🧱，你的智能拼搭助手！\n\n我可以帮你：\n1. 🔍 **识别零件** — 上传图片，我告诉你是什么零件\n2. 🔧 **查找替代** — 缺件时推荐替代方案\n3. 📖 **说明书检索** — 输入步骤号，返回图文\n4. ✅ **成品验收** — 对比官方模型，检查是否正确\n\n试试上传一张零件图片吧！",
]

# 情绪安抚（简短版）
FRUSTRATION_PATTERNS = [
    r"(烦|难|不会|拼不好|好难|太难了|崩溃|头疼|晕)",
]

FRUSTRATION_RESPONSES = [
    "别急，我来帮你！🤔\n\n你可以：\n- 告诉我卡在哪一步，我帮你查说明书\n- 上传图片，我帮你识别零件\n- 告诉我缺什么零件，我找替代方案",
    "拼乐高遇到困难很正常！我来帮你解决 💪\n\n试试：\n- 「第X步怎么拼？」\n- 上传零件图片让我识别\n- 「XX零件有替代吗？」",
    "深呼吸～我来帮你拆解一下 🧱\n\n告诉我：\n1. 你现在拼到哪一步了？\n2. 哪个部分卡住了？\n\n我会一步步带你解决！",
]


def get_quick_response(message: str) -> Optional[str]:
    """
    检查消息是否匹配快速回复规则。
    匹配则返回预设回复，不匹配则返回 None（走完整 LLM 链路）。
    """
    msg = message.strip().lower()

    # 空消息
    if not msg:
        return None

    # 按优先级匹配
    for patterns, responses in [
        (GREETING_PATTERNS, GREETING_RESPONSES),
        (THANKS_PATTERNS, THANKS_RESPONSES),
        (FAREWELL_PATTERNS, FAREWELL_RESPONSES),
        (AFFIRM_PATTERNS, AFFIRM_RESPONSES),
        (WHO_PATTERNS, WHO_RESPONSES),
        (FRUSTRATION_PATTERNS, FRUSTRATION_RESPONSES),
    ]:
        for pattern in patterns:
            if re.search(pattern, msg, re.IGNORECASE | re.UNICODE):
                return random.choice(responses)

    return None
