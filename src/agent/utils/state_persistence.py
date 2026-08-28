"""状态持久化 - 支持断点续传"""

import json
import time
from typing import Optional
from pathlib import Path


class StatePersistence:
    """状态持久化 - 支持断点续传

    用法:
        persistence = StatePersistence(redis_client=redis)
        persistence.save_state("session_123", state_dict, "manual_agent")
        loaded = persistence.load_state("session_123")
    """

    def __init__(self, redis_client=None, persist_dir: str = "./data/state"):
        self.redis = redis_client
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

    def save_state(self, session_id: str, state: dict, step: str):
        """保存状态快照"""
        snapshot = {
            "session_id": session_id,
            "step": step,
            "timestamp": time.time(),
            "state": state,
        }

        # 尝试 Redis
        if self.redis:
            try:
                key = f"lego_mate:state:{session_id}"
                self.redis.set(key, json.dumps(snapshot, default=str), ex=3600)
                return
            except Exception:
                pass

        # 回退到文件
        file_path = self.persist_dir / f"{session_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, default=str)

    def load_state(self, session_id: str) -> Optional[dict]:
        """加载状态快照"""
        # 尝试 Redis
        if self.redis:
            try:
                key = f"lego_mate:state:{session_id}"
                data = self.redis.get(key)
                if data:
                    return json.loads(data)
            except Exception:
                pass

        # 回退到文件
        file_path = self.persist_dir / f"{session_id}.json"
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)

        return None

    def can_resume(self, session_id: str) -> bool:
        """检查是否可以恢复"""
        state = self.load_state(session_id)
        if state:
            return (time.time() - state.get("timestamp", 0)) < 3600
        return False

    def clear_state(self, session_id: str):
        """清除状态"""
        if self.redis:
            try:
                key = f"lego_mate:state:{session_id}"
                self.redis.delete(key)
            except Exception:
                pass

        file_path = self.persist_dir / f"{session_id}.json"
        if file_path.exists():
            file_path.unlink()
