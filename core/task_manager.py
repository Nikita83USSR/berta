"""Небольшой менеджер фоновых процессов BERTA."""

from dataclasses import dataclass, field
import subprocess
import threading
import time
import uuid


@dataclass
class Task:
    id: str
    name: str
    command: str
    description: str
    status: str = "running"
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    created_at: float = field(default_factory=time.time)
    process: subprocess.Popen | None = None


class TaskManager:
    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()

    def _register(self, task: Task):
        with self._lock:
            self._tasks[task.id] = task

    def start_detached_process(self, name, command, description, shell=True):
        task = Task(uuid.uuid4().hex[:8], name, command, description)
        try:
            task.process = subprocess.Popen(
                command,
                shell=shell,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception as exc:
            task.status = "failed"
            task.stderr = str(exc)
        self._register(task)
        if task.status == "running":
            threading.Thread(target=self._watch, args=(task,), daemon=True).start()
        return task

    def start_process(self, name, command, description, shell=True):
        task = Task(uuid.uuid4().hex[:8], name, command, description)
        try:
            task.process = subprocess.Popen(
                command,
                shell=shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
        except Exception as exc:
            task.status = "failed"
            task.stderr = str(exc)
        self._register(task)
        if task.status == "running":
            threading.Thread(target=self._watch, args=(task,), daemon=True).start()
        return task

    def _watch(self, task):
        try:
            out, err = task.process.communicate(timeout=None)
            task.stdout = (out or "")[-4000:]
            task.stderr = (err or "")[-4000:]
            task.returncode = task.process.returncode
            task.status = "completed" if task.returncode == 0 else "failed"
        except Exception as exc:
            task.stderr = str(exc)
            task.status = "failed"

    def list_tasks(self, only_active=False):
        with self._lock:
            values = list(self._tasks.values())
        result = []
        for task in values:
            if only_active and task.status not in {"running"}:
                continue
            result.append({
                "id": task.id,
                "name": task.name,
                "command": task.command,
                "description": task.description,
                "status": task.status,
                "returncode": task.returncode,
                "created_at": task.created_at,
            })
        return result

    def get(self, task_id):
        with self._lock:
            task = self._tasks.get(task_id)
        if not task:
            return None
        return task


# Единый экземпляр для всех инструментов.
task_manager = TaskManager()
