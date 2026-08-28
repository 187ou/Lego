"""FastAPI 后端服务 - 支持流式输出 + 对话管理"""

import os
import shutil
import asyncio
import json
import time
import uuid
from typing import Optional, AsyncGenerator
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import logging

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="LEGO-Mate API", version="2.1.0")

# CORS 配置（允许前端访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 上传目录
UPLOAD_DIR = os.path.join(os.getcwd(), "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ===== 启动事件 =====

@app.on_event("startup")
async def startup_event():
    """服务启动时初始化知识图谱 + Text2API 引擎"""
    try:
        from src.kg.graph_builder import init_default_graph
        stats = init_default_graph()
        logger.info(f"知识图谱初始化完成: {stats}")
    except Exception as e:
        logger.warning(f"知识图谱初始化失败（可稍后手动初始化）: {e}")

    # 初始化 Text2API 引擎
    try:
        from src.agent.api_registry import init_text2api
        engine = init_text2api()
        logger.info("Text2API 引擎初始化完成")
    except Exception as e:
        logger.warning(f"Text2API 引擎初始化失败: {e}")


# ===== 数据模型 =====

class ChatRequest(BaseModel):
    message: str
    set_id: str = ""
    session_id: str = "default"
    conversation_id: str = ""  # 新增：对话ID


# ===== 初始化 LLM 和 Graph =====

_llm = None
_graph = None


def get_graph():
    """懒加载 Graph"""
    global _llm, _graph
    if _graph is None:
        from langchain_openai import ChatOpenAI
        from src.agent.graph import build_graph
        from src.common.config import get_settings

        settings = get_settings()
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY 未配置")

        logger.info(f"初始化 LLM: {settings.llm_model} @ {settings.llm_base_url}")
        _llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0.7,
            streaming=True,
        )
        _graph = build_graph(_llm)
        logger.info("Graph 初始化完成")
    return _graph


# ===== 图谱推理引擎 =====

_graph_reasoner = None


def get_graph_reasoner():
    """懒加载图谱推理引擎"""
    global _graph_reasoner, _llm
    if _graph_reasoner is None:
        # 确保 LLM 已初始化
        if _llm is None:
            get_graph()
        from src.kg.graph_reasoner import get_graph_reasoner as _get_reasoner
        _graph_reasoner = _get_reasoner(llm=_llm)
        logger.info("图谱推理引擎初始化完成")
    return _graph_reasoner


# ===== SSE 辅助函数 =====

def sse_event(event: str, data: dict) -> str:
    """生成 SSE 格式数据"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ===== 工具显示名称映射 =====

TOOL_DISPLAY_NAMES = {
    "parse_lego_image": "识别零件图片",
    "find_part_alternative": "查询零件替代方案",
    "search_manual_step": "检索说明书步骤",
    "verify_build_result": "验收成品",
}


def _get_tool_display_name(tool_name: str) -> str:
    """获取工具的中文显示名称"""
    return TOOL_DISPLAY_NAMES.get(tool_name, tool_name)


# ===== 记忆管理辅助 =====

def get_conv_manager():
    """获取对话管理器（兼容旧接口）"""
    from src.session.conversation_manager import get_conversation_manager
    return get_conversation_manager()


def get_set_mgr():
    """获取套装管理器"""
    from src.set.set_manager import get_set_manager
    return get_set_manager()


def get_mem_manager():
    """获取多级记忆管理器"""
    from src.memory.manager import get_memory_manager
    return get_memory_manager()


# ===== 流式聊天 =====

async def stream_chat(request: ChatRequest) -> AsyncGenerator[str, None]:
    """流式聊天生成器（三级路由架构）"""
    conv_manager = get_conv_manager()

    # ===== 意图路由 =====
    from src.agent.intent_router import classify_intent, ResponseLevel, get_intent_description
    intent = classify_intent(request.message)
    logger.info(f"🎯 {get_intent_description(intent)}: {request.message[:40]}")

    # ===== L1: 快速回复 =====
    if intent.level == ResponseLevel.L1_QUICK:
        from src.agent.quick_response import get_quick_response
        quick_reply = get_quick_response(request.message)
        if quick_reply:
            async for event in _stream_quick_response(request, quick_reply, conv_manager):
                yield event
            return

    # ===== L2: 工具直调（不调 LLM，直接调用工具） =====
    if intent.level == ResponseLevel.L2_TOOL:
        async for event in _stream_tool_direct(request, intent, conv_manager):
            yield event
        return

    # ===== L3: 完整 Agent 链路（集成多级记忆） =====
    try:
        logger.info(f"📨 收到消息: {request.message[:50]}")
        graph = get_graph()
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

        # === 1. 获取记忆管理器 ===
        mem_manager = get_mem_manager()

        # === 2. 指代消解（L0 工作记忆） ===
        resolved_message = request.message
        if request.conversation_id:
            resolved_message = mem_manager.resolve_reference(
                conversation_id=request.conversation_id,
                message=request.message,
            )
            if resolved_message != request.message:
                logger.info(f"🔄 指代消解: '{request.message}' → '{resolved_message}'")

        # === 3. 更新 L0 工作记忆 ===
        wm = mem_manager.get_working_memory(request.conversation_id)
        wm.current_intent = intent.intent_type.value
        wm.current_set_id = request.set_id or wm.current_set_id
        wm.last_active_time = time.time()

        # === 4. 保存用户消息到 L1 短期记忆 ===
        user_msg_id = str(uuid.uuid4())[:12]
        if request.conversation_id:
            user_memory_msg = mem_manager.add_message(
                conversation_id=request.conversation_id,
                role="user",
                content=request.message,
                id=user_msg_id,
                intent=intent.intent_type.value,
            )

        # === 5. 多路检索融合（L1+L2+L3+L4） ===
        # 发送思考事件
        yield sse_event("thinking", {"status": "context", "message": "🔍 多路检索中..."})

        context = []
        try:
            from src.retrieval.unified_retriever import get_unified_retriever
            retriever = get_unified_retriever()
            context = retriever.build_context(
                query=resolved_message,
                conversation_id=request.conversation_id,
                set_id=request.set_id,
            )
        except Exception as e:
            logger.warning(f"统一检索失败，回退到记忆上下文: {e}")
            # 回退到仅记忆上下文
            if request.conversation_id and mem_manager.r:
                context = mem_manager.build_enhanced_context(
                    conversation_id=request.conversation_id,
                    user_id="default",
                )

        # 添加当前消息
        all_messages = context + [HumanMessage(content=resolved_message)]

        # === 6. 流式思考过程 ===
        yield sse_event("thinking", {"status": "started", "message": "🤔 正在理解你的问题..."})
        await asyncio.sleep(0.2)

        msg_preview = request.message[:30] + ("..." if len(request.message) > 30 else "")
        yield sse_event("thinking", {"status": "analyzing", "message": f"📋 分析问题: \"{msg_preview}\""})
        await asyncio.sleep(0.2)

        if request.set_id:
            yield sse_event("thinking", {"status": "context", "message": f"📦 当前套装: {request.set_id}"})
            await asyncio.sleep(0.15)

        if context:
            yield sse_event("thinking", {"status": "context", "message": f"💭 加载记忆上下文 ({len(context)} 条)"})
            await asyncio.sleep(0.15)

        yield sse_event("thinking", {"status": "routing", "message": "🔀 选择最佳处理方式..."})
        await asyncio.sleep(0.2)

        # === 7. 调用多 Agent 图（Supervisor 自动路由）===
        result = await asyncio.to_thread(
            graph.invoke,
            {
                "messages": all_messages,
                "intent": intent.intent_type.value,
                "parsed_result": {},
                "set_id": request.set_id,
                "step_number": wm.last_discussed_step,
                "require_human_confirm": False,
                "response": "",
                "frustration_score": wm.frustration_score,
                "retry_count": wm.retry_count,
                "last_active_time": wm.last_active_time,
                "encouragement_triggered": False,
                "encouragement_messages": [],
                # 多 Agent 调度字段
                "next_agent": "",
                "agent_results": {},
                "vision_result": {},
                "alternative_result": {},
                "manual_result": {},
                "verify_result": {},
                "psychology_result": {},
            }
        )

        # === 8. 提取工具调用信息 ===
        tool_calls = []
        for msg in result.get("messages", []):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for c in msg.tool_calls:
                    tool_info = {"name": c["name"], "args": c.get("args", {})}
                    tool_calls.append(tool_info)
                    tool_display = _get_tool_display_name(c["name"])
                    yield sse_event("thinking", {"status": "tool_call", "message": f"🔧 {tool_display}"})
                    logger.info(f"🔧 调用工具: {c['name']} | 参数: {c.get('args', {})}")
                    await asyncio.sleep(0.15)

                    # 更新 L0 工作记忆
                    if c["name"] == "search_manual_step":
                        step = c.get("args", {}).get("step_number", 0)
                        if step:
                            wm.last_discussed_step = step

        if tool_calls:
            tool_names = ", ".join([_get_tool_display_name(t["name"]) for t in tool_calls])
            yield sse_event("thinking", {"status": "tool_complete", "message": f"✅ 已完成: {tool_names}"})

        # === 9. 流式输出最终回复 ===
        response_text = result.get("response", "")
        yield sse_event("generating", {"message": "正在生成回复..."})
        logger.info(f"✍️ 生成回复中... (共 {len(response_text)} 字符)")

        for char in response_text:
            yield sse_event("token", {"content": char})
            await asyncio.sleep(0.01)

        # === 10. 保存 AI 回复到 L1 ===
        ai_msg_id = str(uuid.uuid4())[:12]
        if request.conversation_id:
            mem_manager.add_message(
                conversation_id=request.conversation_id,
                role="assistant",
                content=response_text,
                id=ai_msg_id,
                tool_calls=tool_calls,
            )

        # === 11. 更新 L0 工作记忆 ===
        new_frustration = result.get("frustration_score", 0)
        wm.frustration_score = new_frustration
        wm.retry_count = result.get("retry_count", 0)
        wm.current_set_id = request.set_id or wm.current_set_id

        # === 12. 检查是否需要生成 L2 摘要 ===
        if request.conversation_id:
            msg_count = mem_manager.get_message_count(request.conversation_id)
            if msg_count >= 10 and msg_count % 20 == 0:
                # 每 20 条消息尝试生成摘要
                try:
                    mem_manager.create_conversation_summary(request.conversation_id)
                    logger.info(f"📝 生成对话摘要 (消息数: {msg_count})")
                except Exception as e:
                    logger.warning(f"生成摘要失败: {e}")

        # === 13. 更新 L3 用户画像 ===
        if request.conversation_id and mem_manager.r:
            try:
                mem_manager.update_user_profile(
                    user_id="default",
                    conversation_id=request.conversation_id,
                )
            except Exception as e:
                logger.warning(f"更新用户画像失败: {e}")

        # === 14. 发送完成事件 ===
        yield sse_event("done", {
            "response": response_text,
            "tool_calls": tool_calls,
            "require_human_confirm": result.get("require_human_confirm", False),
            "frustration_score": new_frustration,
            "encouragement_triggered": result.get("encouragement_triggered", False),
            "encouragement_messages": result.get("encouragement_messages", []),
            "user_message_id": user_msg_id,
            "ai_message_id": ai_msg_id,
        })
        logger.info("✅ 回复完成")

    except Exception as e:
        logger.error(f"❌ Chat 错误: {e}", exc_info=True)
        yield sse_event("error", {"message": str(e)})


async def _stream_quick_response(
    request: ChatRequest,
    response_text: str,
    conv_manager,
) -> AsyncGenerator[str, None]:
    """快速回复的流式输出（模拟打字效果，但速度更快）"""
    mem_manager = get_mem_manager()

    # 发送思考事件（极短延迟）
    yield sse_event("thinking", {"status": "started", "message": "正在回复..."})
    await asyncio.sleep(0.1)

    # 保存用户消息到 L1
    user_msg_id = str(uuid.uuid4())[:12]
    if request.conversation_id:
        mem_manager.add_message(
            conversation_id=request.conversation_id,
            role="user",
            content=request.message,
            id=user_msg_id,
            intent="quick_response",
        )

    yield sse_event("generating", {"message": "正在生成回复..."})

    # 逐字发送（更快，0.005s 延迟）
    for char in response_text:
        yield sse_event("token", {"content": char})
        await asyncio.sleep(0.005)

    # 保存 AI 回复到 L1
    ai_msg_id = str(uuid.uuid4())[:12]
    if request.conversation_id:
        mem_manager.add_message(
            conversation_id=request.conversation_id,
            role="assistant",
            content=response_text,
            id=ai_msg_id,
        )

    yield sse_event("done", {
        "response": response_text,
        "tool_calls": [],
        "require_human_confirm": False,
        "frustration_score": 0,
        "encouragement_triggered": False,
        "encouragement_messages": [],
        "user_message_id": user_msg_id,
        "ai_message_id": ai_msg_id,
    })


async def _stream_tool_direct(
    request: ChatRequest,
    intent,
    conv_manager,
) -> AsyncGenerator[str, None]:
    """L2 工具直调 - 不调 LLM，直接调用对应工具"""
    from src.session.models import StoredMessage
    from src.agent.tools import (
        find_part_alternative,
        search_manual_step,
        parse_lego_image,
        verify_build_result,
    )

    tool_map = {
        "find_part_alternative": find_part_alternative,
        "search_manual_step": search_manual_step,
        "parse_lego_image": parse_lego_image,
        "verify_build_result": verify_build_result,
    }

    tool = tool_map.get(intent.tool_name)
    if not tool:
        # 工具不存在，降级到 L3
        logger.warning(f"⚠️ 工具 {intent.tool_name} 不存在，降级到 L3")
        async for event in _stream_agent_full(request, conv_manager):
            yield event
        return

    # === 流式思考过程（L2 工具直调） ===
    tool_display = _get_tool_display_name(intent.tool_name)
    yield sse_event("thinking", {"status": "started", "message": f"🤔 正在处理你的请求..."})
    await asyncio.sleep(0.15)

    msg_preview = request.message[:30] + ("..." if len(request.message) > 30 else "")
    yield sse_event("thinking", {"status": "analyzing", "message": f"📋 识别到需要: {tool_display}"})
    await asyncio.sleep(0.15)

    yield sse_event("thinking", {"status": "routing", "message": f"🔧 准备调用 {tool_display}..."})
    await asyncio.sleep(0.15)

    # 保存用户消息到 L1
    mem_manager_l2 = get_mem_manager()
    user_msg_id = str(uuid.uuid4())[:12]
    if request.conversation_id:
        mem_manager_l2.add_message(
            conversation_id=request.conversation_id,
            role="user",
            content=request.message,
            id=user_msg_id,
            intent=intent.intent_type.value,
        )

    # 发送工具调用事件
    tool_info = {"name": intent.tool_name, "args": intent.tool_args or {}}
    yield sse_event("thinking", {"status": "tool_call", "message": f"🔧 正在{tool_display}..."})
    logger.info(f"🔧 直调工具: {intent.tool_name}")

    # 执行工具
    try:
        # 补充参数
        args = dict(intent.tool_args or {})
        if intent.tool_name == "search_manual_step":
            args.setdefault("set_id", request.set_id)
        if intent.tool_name == "find_part_alternative":
            if not args.get("part_name"):
                args["part_name"] = request.message
            args.setdefault("color", "")

        result = tool.invoke(args)
        tool_result = dict(result) if result else {}

        yield sse_event("thinking", {"status": "tool_complete", "message": f"✅ {tool_display}完成"})

        # 用 LLM 友好地总结工具结果
        response_text = _format_tool_result(intent.tool_name, tool_result, request.set_id)

        yield sse_event("generating", {"message": "正在生成回复..."})

        # 流式输出
        for char in response_text:
            yield sse_event("token", {"content": char})
            await asyncio.sleep(0.005)

        # 保存 AI 回复到 L1
        ai_msg_id = str(uuid.uuid4())[:12]
        if request.conversation_id:
            mem_manager_l2.add_message(
                conversation_id=request.conversation_id,
                role="assistant",
                content=response_text,
                id=ai_msg_id,
                tool_calls=[tool_info],
            )

        # 更新 L0 工作记忆
        if request.conversation_id:
            wm = mem_manager_l2.get_working_memory(request.conversation_id)
            if intent.tool_name == "search_manual_step":
                step = args.get("step_number", 0)
                if step:
                    wm.last_discussed_step = step

        yield sse_event("done", {
            "response": response_text,
            "tool_calls": [tool_info],
            "require_human_confirm": False,
            "frustration_score": 0,
            "encouragement_triggered": False,
            "encouragement_messages": [],
            "user_message_id": user_msg_id,
            "ai_message_id": ai_msg_id,
        })
        logger.info("✅ 工具直调完成")

    except Exception as e:
        logger.error(f"❌ 工具调用失败: {e}", exc_info=True)
        yield sse_event("error", {"message": f"工具调用失败: {str(e)}"})


def _format_tool_result(tool_name: str, result: dict, set_id: str) -> str:
    """格式化工具结果为友好的回复文本"""
    if tool_name == "find_part_alternative":
        alts = result.get("alternatives", [])
        if not alts:
            return result.get("message", "未找到替代方案，请确认零件名称和颜色")
        lines = [f"找到以下替代方案：\n"]
        for i, alt in enumerate(alts[:5], 1):
            conf = alt.get("confidence", 0)
            emoji = "🟢" if conf >= 0.8 else "🟡" if conf >= 0.5 else "🔴"
            lines.append(f"{emoji} {alt.get('name', '未知')} ({alt.get('color', '未知')}) - 匹配度 {conf:.0%}")
        return "\n".join(lines)

    elif tool_name == "search_manual_step":
        content = result.get("content", "")
        page = result.get("page_number")
        step = result.get("step_number")
        if content:
            text = f"**步骤 {step}**\n\n{content}"
            if page:
                text += f"\n\n📖 参考第 {page} 页"
            return text
        return result.get("content", "未找到该步骤的内容")

    elif tool_name == "parse_lego_image":
        parts = result.get("parts", [])
        colors = result.get("colors", [])
        step = result.get("step_number")
        conf = result.get("confidence", 0)
        lines = ["识别结果：\n"]
        if parts:
            lines.append("**零件：**")
            for p in parts:
                lines.append(f"- {p.get('name', '未知')} x{p.get('quantity', 1)} ({p.get('color', '未知')})")
        if colors:
            lines.append(f"\n**颜色：** {', '.join(colors)}")
        if step:
            lines.append(f"\n**步骤：** 第 {step} 步")
        lines.append(f"\n**置信度：** {conf:.0%}")
        if result.get("needs_retry"):
            lines.append("\n⚠️ 图片不够清晰，建议重新拍摄")
        return "\n".join(lines)

    elif tool_name == "verify_build_result":
        similarity = result.get("similarity", 0)
        verdict = result.get("verdict", "unknown")
        details = result.get("details", "")
        emoji_map = {"pass": "✅", "review": "⚠️", "fail": "❌"}
        emoji = emoji_map.get(verdict, "❓")
        return f"{emoji} 验收结果\n\n相似度：{similarity:.0%}\n\n{details}"

    return str(result)


async def _stream_agent_full(request: ChatRequest, conv_manager) -> AsyncGenerator[str, None]:
    """L3 完整 Agent 链路（降级入口）"""
    # 复用原有的完整 Agent 逻辑
    messages_to_inject = []
    if request.conversation_id and conv_manager.is_available():
        conv_data = conv_manager.get_conversation(request.conversation_id)
        if conv_data:
            from langchain_core.messages import HumanMessage, AIMessage
            for msg in conv_data["messages"]:
                if msg.role == "user":
                    messages_to_inject.append(HumanMessage(content=msg.content))
                elif msg.role == "assistant":
                    messages_to_inject.append(AIMessage(content=msg.content))

    try:
        graph = get_graph()
        from langchain_core.messages import HumanMessage

        user_msg_id = str(uuid.uuid4())[:12]
        if request.conversation_id and conv_manager.is_available():
            from src.session.models import StoredMessage
            conv_manager.add_message(
                request.conversation_id,
                StoredMessage(
                    id=user_msg_id,
                    role="user",
                    content=request.message,
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
                )
            )

        yield sse_event("thinking", {"status": "started", "message": "正在分析你的问题..."})
        await asyncio.sleep(0.5)
        yield sse_event("status", {"step": "routing", "message": "正在深度推理..."})

        all_messages = messages_to_inject + [HumanMessage(content=request.message)]
        result = await asyncio.to_thread(
            graph.invoke,
            {
                "messages": all_messages,
                "intent": "chat",
                "parsed_result": {},
                "set_id": request.set_id,
                "step_number": 0,
                "require_human_confirm": False,
                "response": "",
                "frustration_score": 0,
                "retry_count": 0,
                "last_active_time": time.time(),
                "encouragement_triggered": False,
                "encouragement_messages": [],
                # 多 Agent 调度字段
                "next_agent": "",
                "agent_results": {},
                "vision_result": {},
                "alternative_result": {},
                "manual_result": {},
                "verify_result": {},
                "psychology_result": {},
            }
        )

        tool_calls = []
        for msg in result.get("messages", []):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for c in msg.tool_calls:
                    tool_info = {"name": c["name"], "args": c.get("args", {})}
                    tool_calls.append(tool_info)
                    yield sse_event("tool_call", tool_info)

        if tool_calls:
            yield sse_event("tool_complete", {"tools": [t["name"] for t in tool_calls]})

        response_text = result.get("response", "")
        yield sse_event("generating", {"message": "正在生成回复..."})

        for char in response_text:
            yield sse_event("token", {"content": char})
            await asyncio.sleep(0.01)

        ai_msg_id = str(uuid.uuid4())[:12]
        if request.conversation_id and conv_manager.is_available():
            from src.session.models import StoredMessage
            conv_manager.add_message(
                request.conversation_id,
                StoredMessage(
                    id=ai_msg_id,
                    role="assistant",
                    content=response_text,
                    tool_calls=tool_calls,
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
                )
            )

        yield sse_event("done", {
            "response": response_text,
            "tool_calls": tool_calls,
            "require_human_confirm": result.get("require_human_confirm", False),
            "frustration_score": result.get("frustration_score", 0),
            "encouragement_triggered": result.get("encouragement_triggered", False),
            "encouragement_messages": result.get("encouragement_messages", []),
            "user_message_id": user_msg_id,
            "ai_message_id": ai_msg_id,
        })

    except Exception as e:
        logger.error(f"❌ Chat 错误: {e}", exc_info=True)
        yield sse_event("error", {"message": str(e)})


# ===== API 端点 =====

@app.get("/")
async def root():
    return {"status": "ok", "service": "LEGO-Mate API", "version": "2.0.0"}


@app.get("/api/health")
async def health():
    """健康检查"""
    conv_manager = get_conv_manager()
    set_mgr = get_set_mgr()
    return {
        "status": "healthy",
        "redis": conv_manager.is_available(),
        "timestamp": time.time(),
    }


# ===== 聊天端点 =====

@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """流式聊天（SSE）"""
    return StreamingResponse(
        stream_chat(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """文本聊天（非流式，备用）"""
    try:
        logger.info(f"📨 收到消息: {request.message[:50]}")
        graph = get_graph()
        from langchain_core.messages import HumanMessage

        result = graph.invoke(
            {
                "messages": [HumanMessage(content=request.message)],
                "intent": "chat",
                "parsed_result": {},
                "set_id": request.set_id,
                "step_number": 0,
                "require_human_confirm": False,
                "response": "",
                "frustration_score": 0,
                "retry_count": 0,
                "last_active_time": time.time(),
                "encouragement_triggered": False,
                "encouragement_messages": [],
                # 多 Agent 调度字段
                "next_agent": "",
                "agent_results": {},
                "vision_result": {},
                "alternative_result": {},
                "manual_result": {},
                "verify_result": {},
                "psychology_result": {},
            }
        )

        tool_calls = []
        for msg in result.get("messages", []):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                tool_calls.extend([
                    {"name": c["name"], "args": c.get("args", {})}
                    for c in msg.tool_calls
                ])

        response_text = result.get("response", "")
        logger.info(f"✅ 回复: {response_text[:100]}...")

        return {
            "response": response_text,
            "tool_calls": tool_calls,
            "require_human_confirm": result.get("require_human_confirm", False),
        }
    except Exception as e:
        logger.error(f"❌ Chat 错误: {e}", exc_info=True)
        return {"response": f"错误: {str(e)}", "tool_calls": [], "require_human_confirm": False}


@app.post("/api/chat/image")
async def chat_with_image(
    image: UploadFile = File(...),
    message: str = Form(""),
    set_id: str = Form(""),
    conversation_id: str = Form(""),
):
    """带图片的聊天"""
    try:
        image_path = os.path.join(UPLOAD_DIR, image.filename)
        with open(image_path, "wb") as f:
            shutil.copyfileobj(image.file, f)

        from src.agent.tools import parse_lego_image
        parse_result = parse_lego_image.invoke({"image_url": image_path})

        prompt = message or "请帮我分析这张图片"
        full_prompt = f"{prompt}\n\n[图片解析结果]\n{parse_result}"

        graph = get_graph()
        from langchain_core.messages import HumanMessage

        result = await asyncio.to_thread(
            graph.invoke,
            {
                "messages": [HumanMessage(content=full_prompt)],
                "intent": "parse_image",
                "parsed_result": parse_result,
                "set_id": set_id,
                "step_number": parse_result.get("step_number", 0),
                "require_human_confirm": False,
                "response": "",
                "frustration_score": 0,
                "retry_count": 0,
                "last_active_time": time.time(),
                "encouragement_triggered": False,
                "encouragement_messages": [],
            }
        )

        response_text = result.get("response", "")

        # 保存消息
        conv_manager = get_conv_manager()
        if conversation_id and conv_manager.is_available():
            from src.session.models import StoredMessage
            conv_manager.add_message(
                conversation_id,
                StoredMessage(
                    id=str(uuid.uuid4())[:12],
                    role="user",
                    content=message or "请分析这张图片",
                    image_url=f"/uploads/{image.filename}",
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
                )
            )
            conv_manager.add_message(
                conversation_id,
                StoredMessage(
                    id=str(uuid.uuid4())[:12],
                    role="assistant",
                    content=response_text,
                    tool_calls=[{"name": "parse_lego_image", "args": {"image_url": image.filename}}],
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
                )
            )

        return {
            "response": response_text,
            "tool_calls": [{"name": "parse_lego_image", "args": {"image_url": image.filename}}],
            "image_url": f"/uploads/{image.filename}",
        }
    except Exception as e:
        logger.error(f"❌ Image chat 错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/uploads/{filename}")
async def get_upload(filename: str):
    """获取上传的图片"""
    from fastapi.responses import FileResponse
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(file_path)


# ===== Text2API 端点 =====

@app.post("/api/text2api")
async def text2api_call(request: dict):
    """
    Text2API 调用端点——LLM 动态选择并执行 API

    Request: {"message": "用户输入", "set_id": "可选"}
    Response: {"success": bool, "api": str, "result": ..., "confidence": float}
    """
    message = request.get("message", "")
    if not message:
        raise HTTPException(status_code=400, detail="message 不能为空")

    try:
        from src.agent.api_registry import get_registry
        from src.agent.text2api import get_text2api_engine

        engine = get_text2api_engine()
        result = engine.run(message)
        return result
    except Exception as e:
        logger.error(f"❌ Text2API 错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/text2api/apis")
async def list_text2api_apis():
    """列出所有已注册的 API"""
    try:
        from src.agent.api_registry import get_registry
        registry = get_registry()
        apis = registry.list_apis()
        return {
            "apis": [
                {
                    "name": api.name,
                    "description": api.description,
                    "parameters": [
                        {"name": p.name, "type": p.type, "required": p.required}
                        for p in api.parameters
                    ],
                }
                for api in apis
            ],
            "count": len(apis),
        }
    except Exception as e:
        logger.error(f"❌ 列出 API 错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/text2api/stats")
async def get_text2api_stats():
    """获取 Text2API 评估统计"""
    try:
        from src.agent.text2api import get_evaluation_stats
        return get_evaluation_stats()
    except Exception as e:
        logger.error(f"❌ 获取统计错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/text2api/logs")
async def clear_text2api_logs():
    """清空评估日志"""
    try:
        from src.agent.text2api import clear_evaluation_logs
        clear_evaluation_logs()
        return {"message": "评估日志已清空"}
    except Exception as e:
        logger.error(f"❌ 清空日志错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ===== 对话管理端点 =====

@app.get("/api/conversations")
async def list_conversations():
    """列出所有对话"""
    conv_manager = get_conv_manager()
    if not conv_manager.is_available():
        return {"conversations": [], "redis_available": False}
    return {
        "conversations": conv_manager.list_conversations(),
        "redis_available": True,
    }


@app.post("/api/conversations")
async def create_conversation(data: dict):
    """创建新对话"""
    conv_manager = get_conv_manager()
    if not conv_manager.is_available():
        raise HTTPException(status_code=503, detail="Redis 不可用")

    from src.session.models import ConversationCreate
    create_data = ConversationCreate(
        set_id=data.get("set_id", ""),
        title=data.get("title", ""),
    )
    meta = conv_manager.create_conversation(create_data)
    return {"conversation": meta}


@app.get("/api/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    """获取对话详情"""
    conv_manager = get_conv_manager()
    if not conv_manager.is_available():
        raise HTTPException(status_code=503, detail="Redis 不可用")

    data = conv_manager.get_conversation(conv_id)
    if not data:
        raise HTTPException(status_code=404, detail="对话不存在")
    return {
        "meta": data["meta"],
        "messages": data["messages"],
    }


@app.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    """删除对话"""
    conv_manager = get_conv_manager()
    if not conv_manager.is_available():
        raise HTTPException(status_code=503, detail="Redis 不可用")

    success = conv_manager.delete_conversation(conv_id)
    if not success:
        raise HTTPException(status_code=500, detail="删除失败")
    return {"success": True}


@app.patch("/api/conversations/{conv_id}")
async def update_conversation(conv_id: str, data: dict):
    """更新对话"""
    conv_manager = get_conv_manager()
    if not conv_manager.is_available():
        raise HTTPException(status_code=503, detail="Redis 不可用")

    from src.session.models import ConversationUpdate
    update_data = ConversationUpdate(
        title=data.get("title"),
        set_id=data.get("set_id"),
    )
    meta = conv_manager.update_conversation(conv_id, update_data)
    if not meta:
        raise HTTPException(status_code=404, detail="对话不存在")
    return {"conversation": meta}


@app.patch("/api/conversations/{conv_id}/messages/{message_id}")
async def update_message_feedback(conv_id: str, message_id: str, data: dict):
    """更新消息反馈"""
    conv_manager = get_conv_manager()
    if not conv_manager.is_available():
        raise HTTPException(status_code=503, detail="Redis 不可用")

    feedback = data.get("feedback")
    success = conv_manager.update_message_feedback(conv_id, message_id, feedback)
    return {"success": success}


# ===== 套装管理端点 =====

@app.get("/api/sets")
async def list_sets():
    """列出所有套装"""
    set_mgr = get_set_mgr()
    return {"sets": set_mgr.list_sets()}


@app.get("/api/sets/{set_id}")
async def get_set(set_id: str):
    """获取套装详情"""
    set_mgr = get_set_mgr()
    data = set_mgr.get_set(set_id)
    if not data:
        raise HTTPException(status_code=404, detail="套装不存在")
    return {"set": data}


@app.post("/api/sets/{set_id}/progress")
async def update_progress(set_id: str, data: dict):
    """更新套装拼搭进度"""
    set_mgr = get_set_mgr()
    from src.session.models import ProgressUpdate
    progress = ProgressUpdate(current_step=data.get("current_step", 0))
    result = set_mgr.update_progress(set_id, progress)
    if not result:
        raise HTTPException(status_code=404, detail="套装不存在")
    return {"set": result}


# ===== 记忆管理端点 =====

@app.get("/api/memory/status")
async def memory_status():
    """获取记忆系统状态"""
    mem_manager = get_mem_manager()
    return {
        "redis_available": mem_manager.r is not None,
        "cache_info": mem_manager._get_cache_info_safe(),
    }


@app.get("/api/memory/conversations/{conv_id}/summary")
async def get_conversation_summary(conv_id: str):
    """获取对话摘要"""
    mem_manager = get_mem_manager()
    summary = mem_manager.get_conversation_summary(conv_id)
    if not summary:
        # 尝试生成摘要
        summary = mem_manager.create_conversation_summary(conv_id)
    if not summary:
        raise HTTPException(status_code=404, detail="摘要不存在")
    return {"summary": summary}


@app.get("/api/memory/conversations/{conv_id}/messages")
async def get_conversation_messages(
    conv_id: str,
    limit: Optional[int] = None,
    offset: int = 0,
):
    """获取对话消息（支持分页）"""
    mem_manager = get_mem_manager()
    messages = mem_manager.get_messages(conv_id, limit=limit, offset=offset)
    total = mem_manager.get_message_count(conv_id)
    return {
        "messages": [m.model_dump() for m in messages],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/memory/sets/{set_id}/summaries")
async def get_set_summaries(set_id: str, limit: int = 5):
    """获取套装相关的历史摘要"""
    mem_manager = get_mem_manager()
    summaries = mem_manager.get_set_summaries(set_id, limit=limit)
    return {"summaries": [s.model_dump() for s in summaries]}


@app.get("/api/memory/user/profile")
async def get_user_profile(user_id: str = "default"):
    """获取用户画像"""
    mem_manager = get_mem_manager()
    profile = mem_manager.get_user_profile(user_id)
    return {"profile": profile}


@app.post("/api/memory/conversations/{conv_id}/summary")
async def generate_summary(conv_id: str):
    """手动生成对话摘要"""
    mem_manager = get_mem_manager()
    summary = mem_manager.create_conversation_summary(conv_id)
    if not summary:
        raise HTTPException(status_code=400, detail="消息数不足，无法生成摘要")
    return {"summary": summary}


@app.delete("/api/memory/cache")
async def clear_memory_cache():
    """清除路由缓存"""
    mem_manager = get_mem_manager()
    mem_manager.clear_cache()
    return {"success": True}


@app.get("/api/memory/conversations/{conv_id}/context")
async def get_conversation_context(conv_id: str):
    """获取构建好的 LLM 上下文（调试用）"""
    mem_manager = get_mem_manager()
    context = mem_manager.build_enhanced_context(conv_id)
    return {"context": context, "message_count": len(context)}


# ===== 文档上传/向量库管理端点 =====

# 文档上传目录
DOCUMENT_DIR = os.path.join(os.getcwd(), "data", "documents")
os.makedirs(DOCUMENT_DIR, exist_ok=True)

# 支持的文件扩展名
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".webp", ".txt", ".md", ".docx"}


@app.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    set_id: str = Form(""),
):
    """
    上传文档到向量数据库。

    支持格式：PDF, PNG, JPG, BMP, WEBP, TXT, MD, DOCX
    """
    # 检查文件扩展名
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}。支持的格式: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # 保存文件
    file_path = os.path.join(DOCUMENT_DIR, file.filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        # 解析文档
        from src.rag.document_loader import load_document
        documents = load_document(file_path, set_id=set_id)

        if not documents:
            raise HTTPException(status_code=400, detail="文档解析失败，未提取到文本内容")

        # 向量化并存储
        from src.rag.vector_store import get_vector_store
        store = get_vector_store()
        added = store.add_documents(documents, set_id=set_id)

        return {
            "success": True,
            "filename": file.filename,
            "set_id": set_id,
            "documents_added": added,
            "message": f"成功导入 {added} 个文档片段",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"文档上传失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"文档处理失败: {str(e)}")


@app.post("/api/documents/import-mock")
async def import_mock_data():
    """导入 Mock 说明书数据（用于测试）"""
    from src.rag.pdf_loader import create_mock_manual
    from src.rag.vector_store import get_vector_store

    store = get_vector_store()
    documents = create_mock_manual(set_id="10295")
    added = store.add_documents(documents, set_id="10295")

    return {
        "success": True,
        "documents_added": added,
        "message": f"成功导入 {added} 个 Mock 文档",
    }


@app.get("/api/documents/stats")
async def document_stats():
    """获取向量数据库统计信息"""
    from src.rag.vector_store import get_vector_store
    store = get_vector_store()
    stats = store.get_stats()
    stats["sets"] = store.list_sets()
    return stats


@app.delete("/api/documents/set/{set_id}")
async def delete_set_documents(set_id: str):
    """删除指定套装的所有文档"""
    from src.rag.vector_store import get_vector_store
    store = get_vector_store()
    deleted = store.delete_by_set(set_id)
    return {"success": True, "deleted": deleted}


@app.get("/api/documents/search")
async def search_documents(
    query: str,
    set_id: str = "",
    top_k: int = 3,
    doc_type: str = "",
):
    """
    搜索文档。

    Args:
        query: 查询文本
        set_id: 套装编号过滤
        top_k: 返回数量
        doc_type: 文档类型过滤（pdf/image/text/docx）
    """
    from src.rag.vector_store import get_vector_store
    store = get_vector_store()
    results = store.search(query, set_id=set_id, top_k=top_k, doc_type=doc_type)
    return {"results": results, "query": query}


# ===== 多模态检索端点 =====

@app.post("/api/multimodal/upload-pdf")
async def upload_pdf_multimodal(
    file: UploadFile = File(...),
    set_id: str = Form(""),
):
    """
    上传 PDF 说明书（多模态处理）。

    处理流程：
    1. PDF → 渲染为图片（每页）
    2. 视觉编码器编码
    3. 文本提取（用于关键词检索）
    4. 存储到多模态向量库
    """
    # 检查文件扩展名
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="只支持 PDF 文件")

    # 保存文件
    pdf_dir = os.path.join(os.getcwd(), "data", "pdfs")
    os.makedirs(pdf_dir, exist_ok=True)
    file_path = os.path.join(pdf_dir, file.filename)

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        # 1. 多模态解析
        from src.rag.multimodal_parser import get_multimodal_parser
        parser = get_multimodal_parser(dpi=200)
        pages = parser.parse_pdf(file_path, set_id=set_id)

        if not pages:
            raise HTTPException(status_code=400, detail="PDF 解析失败")

        # 2. 向量化并存储
        from src.rag.multimodal_store import get_multimodal_store
        store = get_multimodal_store()
        added = store.add_pages(pages, set_id=set_id)

        return {
            "success": True,
            "filename": file.filename,
            "set_id": set_id,
            "pages_processed": len(pages),
            "documents_added": added,
            "message": f"成功处理 {len(pages)} 页，添加 {added} 个多模态文档",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"多模态 PDF 处理失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


@app.post("/api/multimodal/search-by-image")
async def search_by_image(
    image: UploadFile = File(...),
    set_id: str = Form(""),
    top_k: int = 3,
):
    """
    以图搜文：上传零件/步骤图片，返回匹配的说明书页面。
    """
    try:
        # 读取图片
        image_data = await image.read()

        # 搜索
        from src.rag.multimodal_store import get_multimodal_store
        store = get_multimodal_store()
        results = store.search_by_image(image_data, set_id=set_id, top_k=top_k)

        return {
            "results": results,
            "query_type": "image",
            "top_k": top_k,
        }
    except Exception as e:
        logger.error(f"图片搜索失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@app.get("/api/multimodal/search")
async def multimodal_search(
    query: str = "",
    set_id: str = "",
    top_k: int = 3,
):
    """
    文本搜索（文搜图）。
    """
    try:
        from src.rag.multimodal_store import get_multimodal_store
        store = get_multimodal_store()
        results = store.search_by_text(query, set_id=set_id, top_k=top_k)

        return {
            "results": results,
            "query": query,
            "query_type": "text",
        }
    except Exception as e:
        logger.error(f"文本搜索失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@app.get("/api/multimodal/stats")
async def multimodal_stats():
    """获取多模态存储统计"""
    from src.rag.multimodal_store import get_multimodal_store
    store = get_multimodal_store()
    return store.get_stats()


# ===== 零件识别端点 =====

@app.post("/api/parts/recognize")
async def recognize_part(
    image: UploadFile = File(...),
    top_k: int = 5,
):
    """
    零件识别：上传零件图片 → 返回最相似的零件信息。
    """
    try:
        image_data = await image.read()

        from src.vision.part_recognizer import get_part_recognizer
        recognizer = get_part_recognizer()
        results = recognizer.search_by_image(image_data, top_k=top_k)

        return {
            "results": [
                {
                    "part_id": r.part_info.part_id,
                    "name": r.part_info.name,
                    "color": r.part_info.color,
                    "category": r.part_info.category,
                    "similarity": r.similarity,
                }
                for r in results
            ],
            "query_type": "image",
        }
    except Exception as e:
        logger.error(f"零件识别失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"识别失败: {str(e)}")


@app.get("/api/parts/search-by-description")
async def search_parts_by_description(
    query: str,
    top_k: int = 5,
):
    """
    以文搜图：描述零件 → 返回匹配的零件。
    """
    try:
        from src.vision.part_recognizer import get_part_recognizer
        recognizer = get_part_recognizer()
        results = recognizer.search_by_description(query, top_k=top_k)

        return {
            "results": [
                {
                    "part_id": r.part_info.part_id,
                    "name": r.part_info.name,
                    "color": r.part_info.color,
                    "category": r.part_info.category,
                    "similarity": r.similarity,
                }
                for r in results
            ],
            "query": query,
            "query_type": "text",
        }
    except Exception as e:
        logger.error(f"零件搜索失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@app.post("/api/parts/verify")
async def verify_part(
    image: UploadFile = File(...),
    expected_part_id: str = Form(""),
):
    """
    零件验证：对比用户图片与参考图片。
    """
    try:
        image_data = await image.read()

        from src.vision.part_recognizer import get_part_recognizer
        recognizer = get_part_recognizer()
        result = recognizer.verify_part(image_data, expected_part_id)

        return result
    except Exception as e:
        logger.error(f"零件验证失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"验证失败: {str(e)}")


@app.post("/api/parts/import-common")
async def import_common_parts():
    """导入常见零件到数据库"""
    try:
        from src.vision.part_database import build_default_database
        recognizer = build_default_database()
        stats = recognizer.get_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        logger.error(f"导入零件失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


@app.get("/api/parts/stats")
async def part_stats():
    """获取零件数据库统计"""
    from src.vision.part_recognizer import get_part_recognizer
    recognizer = get_part_recognizer()
    return recognizer.get_stats()


# ===== AI 模型生成端点 =====

class GenerateModelRequest(BaseModel):
    description: str
    base_width: int = 16
    base_length: int = 16
    max_attempts: int = 3


@app.post("/api/builder3d/generate")
async def generate_3d_model(request: GenerateModelRequest):
    """
    AI 生成 3D 积木模型。

    流程：LLM 生成 → 物理验证 → 自动修正 → 返回 BuildModel
    """
    try:
        from src.builder3d.pipeline import get_pipeline
        pipeline = get_pipeline()
        model = pipeline.generate(
            description=request.description,
            base_width=request.base_width,
            base_length=request.base_length,
            max_attempts=request.max_attempts,
        )
        return {"success": True, "model": model}
    except Exception as e:
        logger.error(f"AI 模型生成失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


# ===== 知识图谱端点 =====

@app.get("/api/graph/stats")
async def graph_stats():
    """获取知识图谱统计"""
    from src.kg.graph_retriever import get_graph_retriever
    retriever = get_graph_retriever()
    return retriever.get_stats()


@app.get("/api/graph/part/{part_id}")
async def get_part_info(part_id: str):
    """获取零件信息"""
    from src.kg.graph_retriever import get_graph_retriever
    retriever = get_graph_retriever()
    return retriever.get_part_info(part_id)


@app.get("/api/graph/part/{part_id}/alternatives")
async def get_part_alternatives(part_id: str, limit: int = 5):
    """获取零件替代方案"""
    from src.kg.graph_retriever import get_graph_retriever
    retriever = get_graph_retriever()
    return {"alternatives": retriever.find_part_alternatives(part_id, limit=limit)}


@app.get("/api/graph/set/{set_id}/step/{step_number}")
async def get_step_info(set_id: str, step_number: int):
    """获取步骤信息"""
    from src.kg.graph_retriever import get_graph_retriever
    retriever = get_graph_retriever()
    return retriever.get_step_info(set_id, step_number)


@app.get("/api/graph/set/{set_id}")
async def get_set_overview(set_id: str):
    """获取套装概览"""
    from src.kg.graph_retriever import get_graph_retriever
    retriever = get_graph_retriever()
    return retriever.get_set_overview(set_id)


@app.post("/api/graph/build-from-manual")
async def build_graph_from_manual(
    file: UploadFile = File(...),
    set_id: str = Form(""),
):
    """
    从说明书构建知识图谱。

    处理流程：
    1. PDF → 多模态解析
    2. 实体抽取（零件/步骤/颜色）
    3. 构建图谱
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="只支持 PDF 文件")

    # 保存文件
    pdf_dir = os.path.join(os.getcwd(), "data", "pdfs")
    os.makedirs(pdf_dir, exist_ok=True)
    file_path = os.path.join(pdf_dir, file.filename)

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        # 1. 多模态解析
        from src.rag.multimodal_parser import get_multimodal_parser
        parser = get_multimodal_parser(dpi=150)
        pages = parser.parse_pdf(file_path, set_id=set_id)

        # 2. 构建图谱
        from src.kg.graph_builder import GraphBuilder
        builder = GraphBuilder()
        stats = builder.build_from_manual(pages, set_id)

        return {
            "success": True,
            "pages_processed": len(pages),
            **stats,
        }
    except Exception as e:
        logger.error(f"构建图谱失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"构建失败: {str(e)}")


@app.delete("/api/graph/clear")
async def clear_graph():
    """清除图谱数据"""
    from src.kg.graph_store import get_graph_store
    store = get_graph_store()
    store.clear_all()
    return {"success": True}


@app.post("/api/graph/init")
async def init_graph():
    """
    手动触发知识图谱初始化。
    从 Mock 说明书 + 常见零件数据库构建完整图谱。
    """
    try:
        from src.kg.graph_builder import init_default_graph
        stats = init_default_graph()
        return {"success": True, **stats}
    except Exception as e:
        logger.error(f"图谱初始化失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"初始化失败: {str(e)}")


class GraphReasonRequest(BaseModel):
    query: str
    set_id: str = "10295"
    reasoning_type: str = ""  # 为空则自动判断


@app.post("/api/graph/reason")
async def graph_reason(request: GraphReasonRequest):
    """
    图谱深度推理。

    支持三种推理：
    - constraint: 多条件约束推理（有 A 无 B，找兼容 A 且替代 B 的零件）
    - chain: 步骤链式推理（第 35 步和第 36 步能跳过吗？）
    - stability: 结构稳定性推理（这个位置放 1x2 板够稳固吗？）
    """
    try:
        reasoner = get_graph_reasoner()

        # 自动判断推理类型
        reasoning_type = request.reasoning_type
        if not reasoning_type:
            import re
            part_ids = re.findall(r"(?<!\d)(\d{4,5})(?!\d)", request.query)
            has_alt = any(kw in request.query for kw in ["替代", "替换", "代替", "缺", "没有", "可以", "兼容"])
            if len(part_ids) >= 2 and has_alt:
                from src.kg.graph_reasoner import REASONING_CONSTRAINT
                reasoning_type = REASONING_CONSTRAINT
            elif re.search(r"(跳过|省略|之间|顺序|先后)", request.query):
                from src.kg.graph_reasoner import REASONING_CHAIN
                reasoning_type = REASONING_CHAIN
            elif re.search(r"(稳固|牢固|稳定|结实|够|撑得住)", request.query):
                from src.kg.graph_reasoner import REASONING_STABILITY
                reasoning_type = REASONING_STABILITY
            else:
                from src.kg.graph_reasoner import REASONING_CONSTRAINT
                reasoning_type = REASONING_CONSTRAINT

        result = reasoner.reason(
            query=request.query,
            reasoning_type=reasoning_type,
            context={"set_id": request.set_id},
        )

        return {
            "success": True,
            "query": request.query,
            "reasoning_type": reasoning_type,
            "result": result,
        }
    except Exception as e:
        logger.error(f"图谱推理失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"推理失败: {str(e)}")


@app.get("/api/graph/cross-modal")
async def graph_cross_modal(
    query: str,
    set_id: str = "10295",
    limit: int = 5,
):
    """
    图谱跨模态搜索（文本→图片）。
    从文本中提取零件号，查找图谱中关联的图片节点。
    """
    try:
        from src.kg.graph_retriever import get_graph_retriever
        retriever = get_graph_retriever()
        results = retriever.cross_modal_search(query, modality="text", limit=limit)
        return {"results": results, "query": query}
    except Exception as e:
        logger.error(f"跨模态搜索失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


# ===== 统一检索端点 =====

@app.post("/api/retrieve")
async def unified_retrieve(
    query: str = Form(""),
    conversation_id: str = Form(""),
    set_id: str = Form(""),
    top_k: int = Form(10),
):
    """
    统一检索：多路检索 + 融合。

    检索源：
    - L1 短期记忆（对话历史）
    - L2 中期记忆（对话摘要）
    - L3 长期记忆（用户画像）
    - L4 向量检索（语义搜索）
    - L4 图谱检索（关系推理）
    """
    try:
        from src.retrieval.unified_retriever import get_unified_retriever
        retriever = get_unified_retriever()

        results = retriever.retrieve(
            query=query,
            conversation_id=conversation_id,
            set_id=set_id,
            top_k=top_k,
        )

        return {
            "results": [
                {
                    "content": r.content,
                    "source": r.source,
                    "score": r.score,
                    "fused_score": r.fused_score,
                    "metadata": r.metadata,
                }
                for r in results
            ],
            "query": query,
            "total": len(results),
        }
    except Exception as e:
        logger.error(f"统一检索失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"检索失败: {str(e)}")


@app.post("/api/retrieve/context")
async def retrieve_context(
    query: str = Form(""),
    conversation_id: str = Form(""),
    set_id: str = Form(""),
):
    """
    检索 + 构建 LLM 上下文。
    """
    try:
        from src.retrieval.unified_retriever import get_unified_retriever
        retriever = get_unified_retriever()

        context = retriever.build_context(
            query=query,
            conversation_id=conversation_id,
            set_id=set_id,
        )

        return {
            "context": context,
            "message_count": len(context),
        }
    except Exception as e:
        logger.error(f"上下文构建失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"构建失败: {str(e)}")


# ===== 3D 拼装端点 =====


@app.get("/api/builder3d/set/{set_id}")
async def get_build_model(set_id: str, set_name: str = "", total_steps: int = 30):
    """
    获取套装的 3D 拼装模型数据。

    返回包含所有步骤和积木信息的完整模型，
    前端用此数据渲染 3D 拼装动画。
    """
    try:
        from src.builder3d.data_generator import get_build_model
        model = get_build_model(set_id, set_name, total_steps)
        return model
    except Exception as e:
        logger.error(f"获取拼装模型失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取拼装模型失败: {str(e)}")


@app.post("/api/builder3d/clear-cache")
async def clear_builder_cache():
    """清除拼装模型缓存"""
    from src.builder3d.data_generator import clear_cache
    clear_cache()
    return {"success": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
