"""LangChain Tool 定义"""

from langchain_core.tools import tool
from src.common.config import get_settings
from src.vision.qwen_vl import parse_lego_image_mock


def _parse_lego_image_real(image_path: str) -> dict:
    """根据配置调用对应的视觉模型"""
    settings = get_settings()

    if settings.vision_provider == "dashscope":
        from src.vision.qwen_vl import parse_lego_image as parse_dashscope
        return parse_dashscope(image_path)

    if settings.vision_provider == "openai":
        from src.vision.openai_vl import parse_lego_image as parse_openai
        return parse_openai(image_path)

    if settings.vision_provider == "ollama":
        from src.vision.ollama_vl import parse_lego_image as parse_ollama
        return parse_ollama(image_path)

    raise ValueError(f"不支持的视觉 provider: {settings.vision_provider}")


@tool
def parse_lego_image(image_url: str) -> dict:
    """
    解析乐高图片，识别零件、颜色、步骤号。

    优先使用零件识别器（CLIP），不可用时回退到多模态 VL 模型。

    Args:
        image_url: 本地图片路径

    Returns:
        包含 parts, colors, step_number, confidence 的字典
        若 confidence < 0.7，needs_retry 为 True
    """
    # 1. 尝试使用零件识别器（CLIP）
    try:
        from src.vision.part_recognizer import get_part_recognizer
        recognizer = get_part_recognizer()
        results = recognizer.search_by_image(image_url, top_k=3)

        if results and results[0].similarity > 0.6:
            best = results[0]
            return {
                "parts": [{
                    "name": best.part_info.name,
                    "color": best.part_info.color,
                    "quantity": 1,
                    "part_id": best.part_info.part_id,
                }],
                "colors": [best.part_info.color] if best.part_info.color else [],
                "step_number": None,
                "confidence": best.similarity,
                "needs_retry": best.similarity < 0.7,
                "alternatives": [
                    {"name": r.part_info.name, "part_id": r.part_info.part_id, "confidence": r.similarity}
                    for r in results[1:]
                ],
                "source": "clip_recognizer",
            }
    except Exception as e:
        print(f"[WARN] 零件识别失败，回退到 VL: {e}")

    # 2. 回退到多模态 VL 模型
    settings = get_settings()
    if settings.use_real_vl:
        return _parse_lego_image_real(image_url)
    return parse_lego_image_mock(image_url)


@tool
def find_part_alternative(part_name: str, color: str) -> dict:
    """
    从 Neo4j 图谱查询零件的替代方案。

    Args:
        part_name: 零件名称（如 "3001" 或 "Brick 2x4"）
        color: 颜色

    Returns:
        替代方案列表，按匹配度排序
    """
    try:
        from src.knowledge.neo4j_client import Neo4jClient
        with Neo4jClient() as client:
            alternatives = client.find_alternatives(part_name, color)

        if not alternatives:
            return {
                "query": f"{color} {part_name}",
                "alternatives": [],
                "message": "未找到替代方案，请确认零件名称和颜色",
            }

        return {
            "query": f"{color} {part_name}",
            "alternatives": alternatives,
        }
    except Exception as e:
        # Neo4j 不可用时返回 Mock 兜底
        return {
            "query": f"{color} {part_name}",
            "alternatives": [
                {"name": "3001 Brick 2x4", "color": "Red", "confidence": 1.0},
                {"name": "3001 Brick 2x4", "color": "Dark Red", "confidence": 0.8},
            ],
            "warning": f"Neo4j 连接失败，返回 Mock 数据: {e}",
        }


@tool
def search_manual_step(set_id: str, step_number: int) -> dict:
    """
    从向量数据库检索说明书指定步骤。

    Args:
        set_id: 套装编号
        step_number: 步骤号

    Returns:
        步骤图文内容
    """
    try:
        from src.rag.vector_store import get_vector_store
        store = get_vector_store()

        # 构建查询
        query = f"步骤{step_number} step {step_number}"
        results = store.search(query, set_id=set_id, top_k=3)

        if not results:
            return {
                "set_id": set_id,
                "step_number": step_number,
                "content": f"未找到步骤 {step_number} 的内容，请确认步骤号是否正确",
                "image_url": None,
            }

        # 返回最匹配的结果
        best = results[0]
        return {
            "set_id": set_id,
            "step_number": step_number,
            "content": best["content"],
            "page_number": best["metadata"].get("page_number"),
            "image_url": None,
            "all_results": results,
        }
    except Exception as e:
        # RAG 不可用时返回 Mock 兜底
        return {
            "set_id": set_id,
            "step_number": step_number,
            "content": f"步骤{step_number}：请参考说明书第{step_number}页。详细图文请查看官方说明书。",
            "image_url": None,
            "warning": f"RAG 检索失败，返回 Mock 数据: {e}",
        }


@tool
def verify_build_result(user_image_url: str, official_image_url: str) -> dict:
    """
    使用 CLIP 对比用户成品图与官方渲染图。

    Args:
        user_image_url: 用户成品图路径
        official_image_url: 官方渲染图路径

    Returns:
        相似度评分和判定结果 (pass/review/fail)
    """
    from src.verification.clip_checker import compare_images
    return compare_images(user_image_url, official_image_url)


# 工具注册表
ALL_TOOLS = [
    parse_lego_image,
    find_part_alternative,
    search_manual_step,
    verify_build_result,
]
