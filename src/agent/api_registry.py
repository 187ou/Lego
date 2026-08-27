"""API 注册——将现有工具封装为标准化 API Schema 并注册到 Text2API 引擎"""

from src.agent.text2api import APISchema, APIParameter, get_registry
from src.agent.tools import (
    parse_lego_image,
    find_part_alternative,
    search_manual_step,
    verify_build_result,
)


def register_all_apis():
    """注册所有工具到 API 注册表"""
    registry = get_registry()

    # 1. 图片解析 API
    registry.register(
        schema=APISchema(
            name="parse_lego_image",
            description="解析乐高图片，识别零件、颜色、步骤号。优先使用 CLIP 零件识别器，不可用时回退到多模态 VL 模型。",
            parameters=[
                APIParameter(
                    name="image_url",
                    type="string",
                    description="本地图片路径或图片 URL",
                    required=True,
                ),
            ],
            returns="包含 parts, colors, step_number, confidence 的字典",
            examples=["用户上传零件图片", "识别这个零件是什么"],
        ),
        handler=parse_lego_image.invoke,
    )

    # 2. 零件替代查询 API
    registry.register(
        schema=APISchema(
            name="find_part_alternative",
            description="从 Neo4j 知识图谱查询零件的替代方案。支持多条件约束推理（有 A 无 B，找兼容 A 且替代 B 的零件）。",
            parameters=[
                APIParameter(
                    name="part_name",
                    type="string",
                    description="零件名称（如 'Brick 2x4'）或零件编号（如 '3001'）",
                    required=True,
                ),
                APIParameter(
                    name="color",
                    type="string",
                    description="颜色（如 'Red', 'Blue'）",
                    required=True,
                ),
            ],
            returns="替代方案列表，按匹配度排序",
            examples=["红色 2x4 砖有什么替代", "缺了 3001 怎么办"],
        ),
        handler=find_part_alternative.invoke,
    )

    # 3. 说明书检索 API
    registry.register(
        schema=APISchema(
            name="search_manual_step",
            description="从向量数据库（ChromaDB）检索说明书指定步骤的拼搭指南。支持向量/关键词混合检索。",
            parameters=[
                APIParameter(
                    name="set_id",
                    type="string",
                    description="套装编号（如 '42115'）",
                    required=True,
                ),
                APIParameter(
                    name="step_number",
                    type="integer",
                    description="步骤编号（如 35）",
                    required=True,
                ),
            ],
            returns="步骤图文内容，包含 content, page_number 等",
            examples=["第 35 步怎么拼", "step 100 是什么"],
        ),
        handler=search_manual_step.invoke,
    )

    # 4. 成品验收 API
    registry.register(
        schema=APISchema(
            name="verify_build_result",
            description="使用 CLIP 对比用户成品图与官方渲染图，返回相似度评分和判定结果（pass/review/fail）。",
            parameters=[
                APIParameter(
                    name="user_image_url",
                    type="string",
                    description="用户成品图路径",
                    required=True,
                ),
                APIParameter(
                    name="official_image_url",
                    type="string",
                    description="官方渲染图路径",
                    required=True,
                ),
            ],
            returns="相似度评分和判定结果",
            examples=["帮我看下对么", "检查成品是否正确"],
        ),
        handler=verify_build_result.invoke,
    )

    return registry


# ===== 启动时自动注册 =====

def init_text2api():
    """初始化 Text2API 引擎并注册所有 API"""
    register_all_apis()
    from src.agent.text2api import get_text2api_engine
    return get_text2api_engine()
