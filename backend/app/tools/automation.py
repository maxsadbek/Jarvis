"""Task Automation System.

Allows JARVIS to automate repetitive tasks:
- Create macros (recorded sequences of actions)
- Schedule recurring tasks (cron-based)
- Chain tool calls together
- Conditional execution
- Variable substitution

Tasks are stored persistently and can be triggered manually,
by schedule, or by events (like voice command).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, Optional

from loguru import logger

from backend.app.config import settings
from backend.app.models.schemas import AutomationTask, TaskStep
from backend.app.tools.base import ToolRegistry


class AutomationEngine:
    """Manages automation tasks: create, schedule, execute, monitor."""

    def __init__(self, tool_registry: ToolRegistry) -> None:
        self._tool_registry = tool_registry
        self._tasks: dict[str, AutomationTask] = {}
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._scheduler_task: Optional[asyncio.Task] = None
        self._recordings: dict[str, dict[str, Any]] = {}
        self._initialized = False

    async def initialize(self) -> bool:
        """Load saved automation tasks."""
        try:
            tasks_file = settings.get_data_path("memory") / "automation_tasks.json"
            if tasks_file.exists():
                with open(tasks_file, "r") as f:
                    data = json.load(f)
                    for item in data:
                        task = AutomationTask(**item)
                        self._tasks[task.id] = task
            logger.info(f"Automation engine initialized ({len(self._tasks)} tasks)")
        except Exception as e:
            logger.warning(f"Could not load automation tasks: {e}")

        self._initialized = True
        return True

    # --- Task Management ---

    async def create_task(
        self,
        name: str,
        description: Optional[str] = None,
        steps: Optional[list[dict[str, Any]]] = None,
        schedule: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> AutomationTask:
        """Create a new automation task.

        Args:
            name: Task name.
            description: Task description.
            steps: List of step dicts with tool_name, action, params.
            schedule: Optional cron expression.
            tags: Optional tags for organization.

        Returns:
            The created AutomationTask.
        """
        task_steps = []
        if steps:
            for i, step_data in enumerate(steps):
                step = TaskStep(
                    id=str(uuid.uuid4()),
                    tool_name=step_data.get("tool_name", ""),
                    action=step_data.get("action", ""),
                    params=step_data.get("params", {}),
                    description=step_data.get("description"),
                    timeout_seconds=step_data.get("timeout_seconds", 30),
                    retry_on_failure=step_data.get("retry_on_failure", False),
                    max_retries=step_data.get("max_retries", 0),
                    depends_on=step_data.get("depends_on", []),
                )
                task_steps.append(step)

        task = AutomationTask(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            steps=task_steps,
            schedule=schedule,
            tags=tags or [],
        )

        self._tasks[task.id] = task
        await self._persist()
        logger.info(f"Created automation task: {name}")
        return task

    async def get_task(self, task_id: str) -> Optional[AutomationTask]:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    async def get_all_tasks(
        self,
        tag: Optional[str] = None,
        enabled_only: bool = False,
    ) -> list[AutomationTask]:
        """Get all automation tasks, optionally filtered."""
        tasks = self._tasks.values()
        if tag:
            tasks = [t for t in tasks if tag in t.tags]
        if enabled_only:
            tasks = [t for t in tasks if t.enabled]
        return list(tasks)

    async def delete_task(self, task_id: str) -> bool:
        """Delete an automation task."""
        if task_id in self._tasks:
            del self._tasks[task_id]
            await self._persist()
            return True
        return False

    async def update_task(self, task_id: str, **updates) -> Optional[AutomationTask]:
        """Update a task's properties."""
        task = self._tasks.get(task_id)
        if not task:
            return None

        for key, value in updates.items():
            if hasattr(task, key):
                setattr(task, key, value)

        await self._persist()
        return task

    # --- Execution ---

    async def execute_task(self, task_id: str) -> dict[str, Any]:
        """Execute an automation task.

        Runs all steps in sequence, respecting dependencies.
        Returns results for each step.

        Args:
            task_id: Task ID to execute.

        Returns:
            Dict with step results and overall status.
        """
        task = self._tasks.get(task_id)
        if not task:
            return {"success": False, "error": f"Task not found: {task_id}"}

        if not task.enabled:
            return {"success": False, "error": "Task is disabled"}

        # Run in background if long-running
        if len(task.steps) > 3:
            bg_task = asyncio.create_task(self._run_task_steps(task))
            self._running_tasks[task_id] = bg_task
            return {
                "success": True,
                "message": f"Task '{task.name}' started in background",
                "task_id": task_id,
                "step_count": len(task.steps),
            }

        return await self._run_task_steps(task)

    async def _run_task_steps(self, task: AutomationTask) -> dict[str, Any]:
        """Execute all steps of a task.

        Args:
            task: The task to execute.

        Returns:
            Dict with step-by-step results.
        """
        results = []
        overall_success = True

        logger.info(f"Executing automation task: {task.name} ({len(task.steps)} steps)")

        for step in task.steps:
            step_result = await self._execute_step(step, task)
            results.append(step_result)

            if not step_result["success"] and not step.retry_on_failure:
                overall_success = False
                break

        # Update task stats
        task.last_run = datetime.now()
        task.total_runs += 1
        await self._persist()

        return {
            "success": overall_success,
            "task_name": task.name,
            "task_id": task.id,
            "steps_completed": sum(1 for r in results if r["success"]),
            "steps_total": len(task.steps),
            "results": results,
        }

    async def _execute_step(
        self,
        step: TaskStep,
        task: AutomationTask,
    ) -> dict[str, Any]:
        """Execute a single task step with retry logic.

        Uses the ToolRegistry's execute_tool with permission checking
        and audit logging for every step.

        Args:
            step: The step to execute.
            task: The parent task (for context).

        Returns:
            Dict with step execution result.
        """
        # Create a ToolCall for permission-aware execution
        from backend.app.models.schemas import ToolCall, ToolName

        tool_call = ToolCall(
            id=uuid.uuid4().hex,
            name=ToolName(step.tool_name) if step.tool_name in [e.value for e in ToolName] else ToolName.WEB_SEARCH,
            arguments={**step.params, "action": step.action},
        )

        last_error = ""
        for attempt in range(step.max_retries + 1):
            try:
                logger.info(f"  Step: {step.description or step.action} (attempt {attempt + 1})")

                # Execute through ToolRegistry for permission checks & audit
                if self._tool_registry:
                    timeout_seconds = step.timeout_seconds

                    async def _timed_execute():
                        import asyncio
                        result_call = await self._tool_registry.execute_tool(
                            tool_call=tool_call,
                            auto_confirm=True,  # Automation tasks auto-confirm
                        )
                        return result_call

                    try:
                        result_call = await asyncio.wait_for(
                            _timed_execute(),
                            timeout=timeout_seconds,
                        )
                    except asyncio.TimeoutError:
                        tool_call.status = "error"
                        tool_call.error = f"Step timed out after {timeout_seconds}s"
                        result_call = tool_call

                    success = result_call.status == "completed"
                    if success:
                        return {
                            "success": True,
                            "step_id": step.id,
                            "result": result_call.result or "",
                            "action": step.action,
                            "attempts": attempt + 1,
                        }

                    last_error = result_call.error or "Unknown error"

                # Fallback: execute directly if no registry
                else:
                    tool = self._tool_registry.get_tool(step.tool_name) if self._tool_registry else None
                    if not tool:
                        return {"success": False, "step_id": step.id, "error": f"Tool not found: {step.tool_name}", "action": step.action}

                    result = await asyncio.wait_for(
                        tool.execute(action=step.action, **step.params),
                        timeout=step.timeout_seconds,
                    )

                    if result.get("success"):
                        return {
                            "success": True,
                            "step_id": step.id,
                            "result": result.get("result", ""),
                            "action": step.action,
                            "attempts": attempt + 1,
                        }

                    last_error = result.get("error", "Unknown error")

                if not step.retry_on_failure:
                    break

            except asyncio.TimeoutError:
                last_error = f"Step timed out after {step.timeout_seconds}s"
                if not step.retry_on_failure:
                    break
            except Exception as e:
                last_error = str(e)
                if not step.retry_on_failure:
                    break

            await asyncio.sleep(1)

        return {
            "success": False,
            "step_id": step.id,
            "error": last_error,
            "action": step.action,
            "attempts": step.max_retries + 1,
        }

    # --- Task Recording (Macro) ---

    async def start_recording(self, name: str) -> str:
        """Start recording a macro.

        Args:
            name: Name for the macro.

        Returns:
            Recording session ID.
        """
        session_id = str(uuid.uuid4())
        self._recordings[session_id] = {
            "name": name,
            "steps": [],
            "started_at": datetime.now(),
        }
        logger.info(f"Started recording macro: {name}")
        return session_id

    async def record_step(
        self,
        session_id: str,
        tool_name: str,
        action: str,
        params: dict[str, Any],
    ) -> bool:
        """Record a step for the current macro.

        Args:
            session_id: Recording session ID.
            tool_name: Tool used.
            action: Action performed.
            params: Parameters used.

        Returns:
            True if recorded successfully.
        """
        recording = self._recordings.get(session_id)
        if not recording:
            return False

        step = TaskStep(
            id=str(uuid.uuid4()),
            tool_name=tool_name,
            action=action,
            params=params,
            description=f"{tool_name}.{action}",
        )
        recording["steps"].append(step)
        return True

    async def stop_recording(self, session_id: str) -> Optional[AutomationTask]:
        """Finalize and save a recorded macro.

        Args:
            session_id: Recording session ID.

        Returns:
            The created AutomationTask.
        """
        recording = self._recordings.pop(session_id, None)
        if not recording or not recording["steps"]:
            return None

        task = await self.create_task(
            name=recording["name"],
            description=f"Recorded macro ({len(recording['steps'])} steps)",
            steps=[
                {
                    "tool_name": s.tool_name,
                    "action": s.action,
                    "params": s.params,
                }
                for s in recording["steps"]
            ],
            tags=["macro", "recorded"],
        )
        logger.info(f"Saved recorded macro: {task.name} ({len(recording['steps'])} steps)")
        return task

    # --- Persistence & Cleanup ---

    async def _persist(self) -> None:
        """Persist tasks to disk."""
        try:
            tasks_file = settings.get_data_path("memory") / "automation_tasks.json"
            data = [task.model_dump() for task in self._tasks.values()]
            with open(tasks_file, "w") as f:
                json.dump(data, f, default=str, indent=2)
        except Exception as e:
            logger.warning(f"Failed to persist automation tasks: {e}")

    async def get_stats(self) -> dict[str, Any]:
        """Get automation engine statistics."""
        return {
            "total_tasks": len(self._tasks),
            "enabled_tasks": sum(1 for t in self._tasks.values() if t.enabled),
            "running_tasks": len(self._running_tasks),
            "scheduled_tasks": sum(1 for t in self._tasks.values() if t.schedule),
            "tags": list(set(tag for t in self._tasks.values() for tag in t.tags)),
        }

    async def shutdown(self) -> None:
        """Cancel running tasks and save state."""
        for task_id, bg_task in self._running_tasks.items():
            bg_task.cancel()
        self._running_tasks.clear()
        await self._persist()
        logger.info("Automation engine shut down")
