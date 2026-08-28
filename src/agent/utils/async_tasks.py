"""异步任务队列

支持：
- 图片解析异步化
- 模型加载异步化
- 批量任务处理
- 任务状态追踪

使用 asyncio 实现，无需额外依赖（如 Celery）
"""

import asyncio
import time
import uuid
import logging
from typing import Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskInfo:
    """任务信息"""
    task_id: str
    task_type: str
    status: TaskStatus
    created_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Any = None
    error: Optional[str] = None
    progress: float = 0.0


class AsyncTaskManager:
    """异步任务管理器

    用法:
        manager = AsyncTaskManager()

        # 提交任务
        task_id = await manager.submit("parse_image", parse_func, image_path)

        # 查询状态
        status = await manager.get_status(task_id)

        # 获取结果
        result = await manager.get_result(task_id, timeout=30)
    """

    def __init__(self, max_workers: int = 4):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: dict[str, TaskInfo] = {}
        self._futures: dict[str, asyncio.Future] = {}

    async def submit(
        self,
        task_type: str,
        func: Callable,
        *args,
        **kwargs,
    ) -> str:
        """提交异步任务

        Args:
            task_type: 任务类型
            func: 要执行的函数
            *args, **kwargs: 函数参数

        Returns:
            task_id
        """
        task_id = str(uuid.uuid4())[:12]

        task_info = TaskInfo(
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            created_at=time.time(),
        )
        self._tasks[task_id] = task_info

        # 创建异步任务
        future = asyncio.create_task(
            self._run_task(task_id, func, *args, **kwargs)
        )
        self._futures[task_id] = future

        return task_id

    async def _run_task(
        self,
        task_id: str,
        func: Callable,
        *args,
        **kwargs,
    ):
        """执行任务"""
        task_info = self._tasks[task_id]
        task_info.status = TaskStatus.RUNNING
        task_info.started_at = time.time()

        try:
            # 在线程池中执行阻塞任务
            loop = asyncio.get_running_loop()
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = await loop.run_in_executor(
                    self._executor, func, *args, **kwargs
                )

            task_info.status = TaskStatus.COMPLETED
            task_info.result = result
            task_info.completed_at = time.time()
            task_info.progress = 1.0

            logger.info(
                f"[TASK] {task_info.task_type} 完成 ({task_id}), "
                f"耗时 {task_info.completed_at - task_info.started_at:.2f}s"
            )

        except Exception as e:
            task_info.status = TaskStatus.FAILED
            task_info.error = str(e)
            task_info.completed_at = time.time()
            logger.error(f"[TASK] {task_info.task_type} 失败 ({task_id}): {e}")

    async def get_status(self, task_id: str) -> Optional[TaskInfo]:
        """获取任务状态"""
        return self._tasks.get(task_id)

    async def get_result(
        self,
        task_id: str,
        timeout: float = 30.0,
    ) -> Any:
        """获取任务结果（等待完成）

        Args:
            task_id: 任务 ID
            timeout: 超时时间

        Returns:
            任务结果

        Raises:
            TimeoutError: 超时
            Exception: 任务执行失败
        """
        future = self._futures.get(task_id)
        if not future:
            raise ValueError(f"任务不存在: {task_id}")

        try:
            await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"任务 {task_id} 超时 ({timeout}s)")

        task_info = self._tasks[task_id]
        if task_info.status == TaskStatus.FAILED:
            raise Exception(task_info.error or "任务执行失败")

        return task_info.result

    async def cancel(self, task_id: str) -> bool:
        """取消任务"""
        future = self._futures.get(task_id)
        if future and not future.done():
            future.cancel()
            self._tasks[task_id].status = TaskStatus.CANCELLED
            return True
        return False

    def get_all_tasks(self) -> list[TaskInfo]:
        """获取所有任务"""
        return list(self._tasks.values())

    def cleanup_completed(self, max_age: float = 3600):
        """清理已完成的任务"""
        now = time.time()
        to_remove = [
            task_id for task_id, info in self._tasks.items()
            if info.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
            and info.completed_at
            and (now - info.completed_at) > max_age
        ]
        for task_id in to_remove:
            del self._tasks[task_id]
            del self._futures[task_id]

    async def submit_batch(
        self,
        task_type: str,
        func: Callable,
        args_list: list[tuple],
    ) -> list[str]:
        """批量提交任务

        Args:
            task_type: 任务类型
            func: 要执行的函数
            args_list: 参数列表，每个元素是 (args, kwargs)

        Returns:
            task_id 列表
        """
        task_ids = []
        for args, kwargs in args_list:
            task_id = await self.submit(task_type, func, *args, **kwargs)
            task_ids.append(task_id)
        return task_ids

    async def wait_batch(
        self,
        task_ids: list[str],
        timeout: float = 60.0,
    ) -> list[Any]:
        """等待批量任务完成

        Args:
            task_ids: 任务 ID 列表
            timeout: 超时时间

        Returns:
            结果列表
        """
        results = []
        for task_id in task_ids:
            try:
                result = await self.get_result(task_id, timeout=timeout)
                results.append(result)
            except Exception as e:
                results.append({"error": str(e)})
        return results


# 全局任务管理器
_task_manager: Optional[AsyncTaskManager] = None


def get_task_manager() -> AsyncTaskManager:
    """获取全局任务管理器"""
    global _task_manager
    if _task_manager is None:
        _task_manager = AsyncTaskManager(max_workers=4)
    return _task_manager
