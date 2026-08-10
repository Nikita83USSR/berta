# core/task_manager.py
"""
Менеджер фоновых задач BERTA.
Позволяет запускать долгие операции (Chrome, серверы и т.д.)
без блокировки основного цикла и веб-интерфейса.
"""

import threading
import time
import uuid
import subprocess
from typing import Optional, Callable, Any
from core.event_bus import bus


class Task:

    def __init__(self, name: str, description: str = ""):
        self.id = str(uuid.uuid4())[:8]
        self.name = name
        self.description = description
        self.status = "pending"          # pending | running | completed | failed | cancelled
        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None
        self.result: Any = None
        self.error: Optional[str] = None
        self.process: Optional[subprocess.Popen] = None
        self.thread: Optional[threading.Thread] = None

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "result": str(self.result)[:2000] if self.result is not None else None,
            "error": self.error,
            "pid": self.process.pid if self.process and self.process.poll() is None else None
        }


class TaskManager:

    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()

    def _emit(self, task: Task, event_type: str = "task"):
        bus.emit(event_type, task.to_dict(), source="task_manager")

    def start_background(
        self,
        name: str,
        target: Callable,
        description: str = "",
        args: tuple = (),
        kwargs: dict = None
    ) -> Task:
        """Запускает обычную Python-функцию в отдельном потоке."""
        if kwargs is None:
            kwargs = {}

        task = Task(name=name, description=description)

        def runner():
            task.status = "running"
            task.started_at = time.time()
            self._emit(task)

            try:
                result = target(*args, **kwargs)
                task.result = result
                task.status = "completed"
            except Exception as e:
                task.error = str(e)
                task.status = "failed"
                bus.emit("error", {
                    "task_id": task.id,
                    "name": task.name,
                    "error": str(e)
                }, source="task_manager")

            task.finished_at = time.time()
            self._emit(task)

        thread = threading.Thread(target=runner, daemon=True, name=f"berta-task-{task.id}")
        task.thread = thread

        with self._lock:
            self._tasks[task.id] = task

        thread.start()
        self._emit(task)
        return task

    def start_process(
        self,
        name: str,
        command: list | str,
        description: str = "",
        shell: bool = False,
        cwd: Optional[str] = None
    ) -> Task:
        """
        Запускает внешний процесс (Chrome, сервер и т.д.) через Popen.
        Не блокирует основной поток.
        """
        task = Task(name=name, description=description or str(command))

        def runner():
            task.status = "running"
            task.started_at = time.time()
            self._emit(task)

            try:
                proc = subprocess.Popen(
                    command,
                    shell=shell,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=cwd
                )
                task.process = proc

                # Ждём завершения (в фоне)
                stdout, stderr = proc.communicate()

                task.result = {
                    "returncode": proc.returncode,
                    "stdout": stdout.strip() if stdout else "",
                    "stderr": stderr.strip() if stderr else ""
                }

                if proc.returncode == 0:
                    task.status = "completed"
                else:
                    task.status = "failed"
                    task.error = stderr.strip() or f"exit code {proc.returncode}"

            except Exception as e:
                task.error = str(e)
                task.status = "failed"
                bus.emit("error", {
                    "task_id": task.id,
                    "name": task.name,
                    "error": str(e)
                }, source="task_manager")

            task.finished_at = time.time()
            self._emit(task)

        thread = threading.Thread(target=runner, daemon=True, name=f"berta-proc-{task.id}")
        task.thread = thread

        with self._lock:
            self._tasks[task.id] = task

        thread.start()
        self._emit(task)
        return task

    def start_detached_process(
        self,
        name: str,
        command: list | str,
        description: str = "",
        shell: bool = False
    ) -> Task:
        """
        Запускает процесс и сразу отпускает его (не ждёт завершения).
        Идеально для Chrome, GUI-приложений, демонов.
        """
        task = Task(name=name, description=description or str(command))
        task.status = "running"
        task.started_at = time.time()

        try:
            proc = subprocess.Popen(
                command,
                shell=shell,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True   # отвязываем от родителя
            )
            task.process = proc
            task.result = {"pid": proc.pid, "detached": True}
            # Статус оставляем running — процесс живёт своей жизнью

        except Exception as e:
            task.error = str(e)
            task.status = "failed"
            task.finished_at = time.time()

        with self._lock:
            self._tasks[task.id] = task

        self._emit(task)
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        with self._lock:
            return self._tasks.get(task_id)

    def list_tasks(self, only_active: bool = False) -> list[dict]:
        with self._lock:
            tasks = list(self._tasks.values())

        if only_active:
            tasks = [t for t in tasks if t.status in ("pending", "running")]

        # Свежие сверху
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return [t.to_dict() for t in tasks]

    def cancel(self, task_id: str) -> bool:
        """Пытается остановить задачу (если это процесс)."""
        task = self.get_task(task_id)
        if not task:
            return False

        if task.process and task.process.poll() is None:
            try:
                task.process.terminate()
                task.status = "cancelled"
                task.finished_at = time.time()
                self._emit(task)
                return True
            except Exception:
                return False
        return False


# Глобальный экземпляр
task_manager = TaskManager()
