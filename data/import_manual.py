"""
说明书数据导入脚本
运行方式：uv run python data/import_manual.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rag.pdf_loader import create_mock_manual, load_manual_pdf
from src.rag.vector_store import get_vector_store


def import_mock_data():
    """导入 Mock 说明书数据"""
    store = get_vector_store()

    # 导入 Mock 数据
    mock_docs = create_mock_manual(set_id="10295")
    store.add_documents(mock_docs, set_id="10295")
    print(f"[OK] 导入 Mock 说明书: {len(mock_docs)} 个片段")


def import_real_pdf(pdf_path: str, set_id: str):
    """导入真实 PDF 说明书"""
    if not os.path.exists(pdf_path):
        print(f"[ERROR] 文件不存在: {pdf_path}")
        return

    docs = load_manual_pdf(pdf_path, set_id)
    store = get_vector_store()
    store.add_documents(docs, set_id=set_id)
    print(f"[OK] 导入 PDF: {pdf_path} -> {len(docs)} 个片段")


if __name__ == "__main__":
    import_mock_data()
    print("\n说明书导入完成！")
