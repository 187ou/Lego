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

app = FastAPI(title="LEGO-Mate API", version="2.0.0")

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


# ===== SSE 辅助函数 =====

def sse_event(event: str, data: dict) -> str:
    """生成 SSE 格式数据"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ===== 对话管理辅助 =====

def get_conv_manager():
    """获取对话管理器"""
    from src.session.conversation_manager import get_conversation_manager
    return get_conversation_manager()


def get_set_mgr():
    """获取套装管理器"""
    from src.set.set_manager import get_set_manager
    return get_set_manager()


# ===== 流式聊天 =====

async def stream_chat(request: ChatRequest) -> AsyncGenerator[str, None]:
    """流式聊天生成器"""
    conv_manager = get_conv_manager()
    messages_to_inject = []

    # 如果有 conversation_id，加载历史消息
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
        logger.info(f"📨 收到消息: {request.message[:50]}")
        graph = get_graph()
        from langchain_core.messages import HumanMessage

        # 保存用户消息
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

        # 发送思考开始事件
        yield sse_event("thinking", {"status": "started", "message": "正在分析你的问题..."})
        logger.info("🤔 开始分析问题...")

        await asyncio.sleep(0.5)

        yield sse_event("status", {"step": "routing", "message": "正在路由到对应工具..."})
        logger.info("🔀 意图路由中...")

        # 构建初始状态
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
            }
        )

        # 提取工具调用信息
        tool_calls = []
        for msg in result.get("messages", []):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for c in msg.tool_calls:
                    tool_info = {"name": c["name"], "args": c.get("args", {})}
                    tool_calls.append(tool_info)
                    yield sse_event("tool_call", tool_info)
                    logger.info(f"🔧 调用工具: {c['name']} | 参数: {c.get('args', {})}")

        if tool_calls:
            yield sse_event("tool_complete", {"tools": [t["name"] for t in tool_calls]})
            logger.info(f"✅ 工具执行完成: {[t['name'] for t in tool_calls]}")

        # 流式输出最终回复
        response_text = result.get("response", "")
        yield sse_event("generating", {"message": "正在生成回复..."})
        logger.info(f"✍️ 生成回复中... (共 {len(response_text)} 字符)")

        # 逐字发送回复
        for char in response_text:
            yield sse_event("token", {"content": char})
            await asyncio.sleep(0.01)

        # 保存 AI 回复
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

        # 发送完成事件
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
        logger.info("✅ 回复完成")

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
