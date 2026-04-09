import asyncio
import uuid
import time
import logging
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Task:
    def __init__(self, name: str, task_type: str, metadata: Dict[str, Any] = None):
        self.id = str(uuid.uuid4())
        self.name = name
        self.type = task_type
        self.status = TaskStatus.PENDING
        self.progress = 0.0  # 0.0 to 100.0
        self.message = "Initializing..."
        self.metadata = metadata or {}
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        self.result = None
        self.error = None
        self._stop_event = asyncio.Event()

    def update(self, status: TaskStatus = None, progress: float = None, message: str = None, result: Any = None, error: str = None):
        if status: self.status = status
        if progress is not None: self.progress = progress
        if message: self.message = message
        if result: self.result = result
        if error: self.error = error
        self.updated_at = datetime.now().isoformat()

    def cancel(self):
        if self.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            self.status = TaskStatus.CANCELLED
            self._stop_event.set()
            self.message = "Cancelled by user"

    def is_cancelled(self):
        return self._stop_event.is_set()

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata
        }

class TaskManager:
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self._lock = asyncio.Lock()

    async def create_task(self, name: str, task_type: str, metadata: Dict[str, Any] = None) -> Task:
        async with self._lock:
            task = Task(name, task_type, metadata)
            self.tasks[task.id] = task
            return task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def list_tasks(self, limit: int = 50) -> List[Dict]:
        return [t.to_dict() for t in sorted(self.tasks.values(), key=lambda x: x.created_at, reverse=True)[:limit]]

    async def run_task(self, task_id: str, coro_func: Callable, *args, **kwargs):
        task = self.get_task(task_id)
        if not task:
            return

        task.update(status=TaskStatus.RUNNING, message="Task started")
        try:
            # We pass the task object so the coroutine can update progress
            await coro_func(task, *args, **kwargs)
            if task.status == TaskStatus.RUNNING:
                task.update(status=TaskStatus.COMPLETED, progress=100.0, message="Task completed successfully")
        except asyncio.CancelledError:
            task.update(status=TaskStatus.CANCELLED, message="Task was cancelled")
        except Exception as e:
            logger.exception(f"Error in task {task_id}")
            task.update(status=TaskStatus.FAILED, message=f"Error: {str(e)}", error=str(e))

    async def cleanup_old_tasks(self, max_age_seconds: int = 3600 * 24):
        # NOT implemented yet, but good for production
        pass

# Singleton instance
task_manager = TaskManager()
