"""LEGO-Mate 入口文件——对话循环"""

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from src.agent.graph import build_graph
from src.common.config import get_settings

load_dotenv()


def get_llm() -> ChatOpenAI:
    """获取推理 LLM"""
    settings = get_settings()
    if not settings.llm_api_key:
        raise ValueError("未配置 LLM_API_KEY，请在 .env 中设置")
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=0.7,
    )


def main():
    llm = get_llm()
    graph = build_graph(llm)

    print("=" * 50)
    print("🧱 LEGO-Mate 智能拼搭助手")
    print("输入 'quit' 退出")
    print("=" * 50)

    while True:
        user_input = input("\n👤 你: ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            print("再见！")
            break

        if not user_input:
            continue

        # 调用多 Agent 图（Supervisor 自动路由）
        result = graph.invoke({
            "messages": [HumanMessage(content=user_input)],
            "intent": "chat",
            "parsed_result": {},
            "set_id": "",
            "step_number": 0,
            "require_human_confirm": False,
            "response": "",
            # 多 Agent 调度字段
            "next_agent": "",
            "agent_results": {},
            "vision_result": {},
            "alternative_result": {},
            "manual_result": {},
            "verify_result": {},
            "psychology_result": {},
        })

        # 输出回复
        last_message = result["messages"][-1]
        print(f"\n🤖 LEGO-Mate: {last_message.content}")

        # 显示工具调用信息（调试用）
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            print(f"   [工具调用: {[c['name'] for c in last_message.tool_calls]}]")

        # 显示路由信息（调试用）
        routed_agent = result.get("next_agent", "unknown")
        print(f"   [路由 Agent: {routed_agent}]")


if __name__ == "__main__":
    main()
