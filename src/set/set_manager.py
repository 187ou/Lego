"""套装管理器"""

import json
from typing import Optional
from src.session.redis_client import get_redis, check_redis_connection
from src.session.models import SetInfo, ProgressUpdate


# 内置示例套装数据
DEFAULT_SETS = [
    {
        "set_id": "10295",
        "name": "911 保时捷",
        "total_steps": 37,
        "total_parts": 1458,
        "current_step": 0,
        "thumbnail_url": "",
    },
    {
        "set_id": "42141",
        "name": "F1 赛车",
        "total_steps": 45,
        "total_parts": 1639,
        "current_step": 0,
        "thumbnail_url": "",
    },
    {
        "set_id": "42115",
        "name": "兰博基尼 Sián",
        "total_steps": 52,
        "total_parts": 3678,
        "current_step": 0,
        "thumbnail_url": "",
    },
    {
        "set_id": "42143",
        "name": "法拉利 Daytona SP3",
        "total_steps": 61,
        "total_parts": 3778,
        "current_step": 0,
        "thumbnail_url": "",
    },
]


class SetManager:
    """套装管理器"""

    def __init__(self):
        self._redis = None

    @property
    def r(self):
        if self._redis is None:
            self._redis = get_redis()
        return self._redis

    def is_available(self) -> bool:
        return check_redis_connection()

    def _ensure_seeded(self):
        """确保示例数据已导入"""
        try:
            if not self.r.exists("sets"):
                for s in DEFAULT_SETS:
                    self.r.hset(f"set:{s['set_id']}", mapping=s)
                self.r.set("sets", "1")
        except Exception:
            pass

    def list_sets(self) -> list[SetInfo]:
        """列出所有套装"""
        self._ensure_seeded()
        try:
            r = self.r
            set_ids = [k.split(":")[1] for k in r.keys("set:*") if k.count(":") == 1]
            sets = []
            for sid in set_ids:
                data = r.hgetall(f"set:{sid}")
                if data:
                    sets.append(SetInfo(
                        set_id=data.get("set_id", sid),
                        name=data.get("name", ""),
                        total_steps=int(data.get("total_steps", 0)),
                        total_parts=int(data.get("total_parts", 0)),
                        current_step=int(data.get("current_step", 0)),
                        thumbnail_url=data.get("thumbnail_url", ""),
                    ))
            return sets
        except Exception as e:
            print(f"[ERROR] 列出套装失败: {e}")
            return [SetInfo(**s) for s in DEFAULT_SETS]

    def get_set(self, set_id: str) -> Optional[SetInfo]:
        """获取套装详情"""
        self._ensure_seeded()
        try:
            data = self.r.hgetall(f"set:{set_id}")
            if not data:
                # 从默认数据中查找
                for s in DEFAULT_SETS:
                    if s["set_id"] == set_id:
                        return SetInfo(**s)
                return None
            return SetInfo(
                set_id=data.get("set_id", set_id),
                name=data.get("name", ""),
                total_steps=int(data.get("total_steps", 0)),
                total_parts=int(data.get("total_parts", 0)),
                current_step=int(data.get("current_step", 0)),
                thumbnail_url=data.get("thumbnail_url", ""),
            )
        except Exception as e:
            print(f"[ERROR] 获取套装失败: {e}")
            return None

    def update_progress(self, set_id: str, progress: ProgressUpdate) -> Optional[SetInfo]:
        """更新套装拼搭进度"""
        try:
            if self.r.exists(f"set:{set_id}"):
                self.r.hset(f"set:{set_id}", "current_step", str(progress.current_step))
            return self.get_set(set_id)
        except Exception as e:
            print(f"[ERROR] 更新进度失败: {e}")
            return None


# 全局单例
_manager: Optional[SetManager] = None


def get_set_manager() -> SetManager:
    """获取套装管理器单例"""
    global _manager
    if _manager is None:
        _manager = SetManager()
    return _manager
