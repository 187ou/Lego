"""飞书 Webhook 通知模块"""

import json
import httpx
from typing import Any
from src.common.config import get_settings


def send_feishu_notification(
    title: str,
    content: str,
    color: str = "green",
) -> bool:
    """
    发送飞书 Webhook 通知

    Args:
        title: 消息标题
        content: 消息内容（支持 markdown）
        color: 标题颜色 (blue/green/red/orange/purple/indigo/grey)

    Returns:
        是否发送成功
    """
    settings = get_settings()
    if not settings.feishu_webhook_url:
        print("[WARN] FEISHU_WEBHOOK_URL 未配置，跳过通知")
        return False

    # 飞书消息卡片格式
    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title,
                },
                "template": color,
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": content,
                    },
                }
            ],
        },
    }

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(
                settings.feishu_webhook_url,
                json=card,
            )
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") == 0:
                print(f"[OK] 飞书通知发送成功: {title}")
                return True
            else:
                print(f"[ERROR] 飞书通知失败: {result}")
                return False
    except Exception as e:
        print(f"[ERROR] 飞书通知异常: {e}")
        return False


def send_build_verification_result(
    set_id: str,
    verdict: str,
    similarity: float,
    details: str,
) -> bool:
    """
    发送成品验收结果通知

    Args:
        set_id: 套装编号
        verdict: 验收结果 (pass/review/fail)
        similarity: 相似度
        details: 详细说明

    Returns:
        是否发送成功
    """
    color_map = {
        "pass": "green",
        "review": "orange",
        "fail": "red",
    }
    emoji_map = {
        "pass": "✅",
        "review": "⚠️",
        "fail": "❌",
    }

    title = f"{emoji_map.get(verdict, '📦')} LEGO-Mate 验收结果"
    content = (
        f"**套装**: {set_id}\n"
        f"**结果**: {verdict.upper()}\n"
        f"**相似度**: {similarity:.2%}\n"
        f"**详情**: {details}"
    )

    return send_feishu_notification(title, content, color_map.get(verdict, "blue"))


def send_missing_part_alert(
    set_id: str,
    part_name: str,
    color: str,
    alternatives: list[dict],
) -> bool:
    """
    发送缺件提醒通知

    Args:
        set_id: 套装编号
        part_name: 缺失零件
        color: 颜色
        alternatives: 替代方案

    Returns:
        是否发送成功
    """
    alt_text = "\n".join(
        f"- {a.get('name', 'N/A')} ({a.get('color', 'N/A')}) 匹配度: {a.get('confidence', 0):.0%}"
        for a in alternatives[:3]
    )

    title = "🔧 LEGO-Mate 缺件提醒"
    content = (
        f"**套装**: {set_id}\n"
        f"**缺失**: {color} {part_name}\n\n"
        f"**替代方案**:\n{alt_text}"
    )

    return send_feishu_notification(title, content, "orange")


# 保留向后兼容
def send_notification(title: str, content: str, **kwargs) -> bool:
    """通用通知发送"""
    return send_feishu_notification(title, content, **kwargs)
