"""PDF 说明书加载和切片"""

from typing import Any
from pypdf import PdfReader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def load_manual_pdf(pdf_path: str, set_id: str) -> list[Document]:
    """
    加载 PDF 说明书并切片

    Args:
        pdf_path: PDF 文件路径
        set_id: 套装编号

    Returns:
        切片后的文档列表
    """
    reader = PdfReader(pdf_path)
    documents = []

    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text()
        if not text or not text.strip():
            continue

        doc = Document(
            page_content=text.strip(),
            metadata={
                "set_id": set_id,
                "page_number": page_num,
                "source": pdf_path,
            },
        )
        documents.append(doc)

    # 进一步切片（按段落）
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", "。", ". ", " "],
    )

    split_docs = splitter.split_documents(documents)

    # 重新添加元数据
    for doc in split_docs:
        doc.metadata.setdefault("set_id", set_id)

    return split_docs


def create_mock_manual(set_id: str = "10295") -> list[Document]:
    """
    创建 Mock 说明书数据（用于测试）

    Args:
        set_id: 套装编号

    Returns:
        Mock 文档列表
    """
    mock_steps = [
        # 第1-5步
        {"step": 1, "content": "步骤1：取出一块2x4红色砖，放在底板中央位置。注意砖块的方向，凸起朝上。", "page": 1},
        {"step": 2, "content": "步骤2：在2x4红色砖的左右两侧各放置一块1x2蓝色砖，形成对称结构。", "page": 1},
        {"step": 3, "content": "步骤3：取出2x4白色砖，叠放在红色砖上方，确保对齐。", "page": 2},
        {"step": 4, "content": "步骤4：在白色砖上方放置2x2红色砖，作为机翼的基座。", "page": 2},
        {"step": 5, "content": "步骤5：使用1x4黑色砖连接左右两侧，加固结构。", "page": 3},
        # 第6-10步
        {"step": 6, "content": "步骤6：取出2x3蓝色砖，放置在机身尾部，作为尾翼底座。", "page": 3},
        {"step": 7, "content": "步骤7：在尾翼底座上放置1x2白色砖，形成尾翼。", "page": 4},
        {"step": 8, "content": "步骤8：使用2x4红色砖继续向上搭建，完成机身主体。", "page": 4},
        {"step": 9, "content": "步骤9：在机身前端放置1x1透明砖，作为驾驶舱玻璃。", "page": 5},
        {"step": 10, "content": "步骤10：最后检查所有连接是否牢固，完成组装。", "page": 5},
        # 第35步（用户常问的）
        {"step": 35, "content": "步骤35：取出2x4红色砖，安装在机翼下方，作为起落架连接点。注意需要两块对称安装。", "page": 12},
        {"step": 36, "content": "步骤36：在起落架下方安装1x2黑色砖，作为轮子支架。", "page": 12},
        {"step": 37, "content": "步骤37：使用2x2蓝色砖加固机翼与机身连接处。", "page": 13},
    ]

    documents = []
    for step_info in mock_steps:
        doc = Document(
            page_content=f"[步骤{step_info['step']}] {step_info['content']}",
            metadata={
                "set_id": set_id,
                "step_number": step_info["step"],
                "page_number": step_info["page"],
                "source": "mock",
            },
        )
        documents.append(doc)

    return documents
