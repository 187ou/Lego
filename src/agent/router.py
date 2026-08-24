"""意图路由：根据用户输入决定调用哪个工具"""

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel

SystemPrompt = SystemMessage

ROUTING_PROMPT = """你是 LEGO-Mate 意图路由器的分类器。
根据用户输入，判断其意图并返回对应的工具名。

可选意图：
- parse_image: 用户上传了图片，需要识别零件/颜色/步骤
- find_alternative: 用户询问某个零件的替代方案
- search_manual: 用户询问说明书某一步怎么拼
- verify_build: 用户上传成品图，请求验收
- chat: 闲聊或其他问题

只返回意图标签，不要解释。
"""


def route_intent(user_input: str, llm: BaseChatModel) -> str:
    """用 LLM 判断用户意图"""
    messages = [
        SystemPrompt(ROUTING_PROMPT),
        HumanMessage(content=user_input),
    ]
    result = llm.invoke(messages)
    intent = result.content.strip().lower()

    valid_intents = {
        "parse_image", "find_alternative",
        "search_manual", "verify_build", "chat",
    }
    return intent if intent in valid_intents else "chat"
