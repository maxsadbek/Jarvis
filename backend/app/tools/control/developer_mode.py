"""Developer Mode — Coding Assistant for JARVIS.

Specialized tools for developers:
- Open VS Code with specific project
- Create new project scaffolding
- Run terminal commands
- Explain code errors
- Git operations (status, commit, log)
- Code search and navigation
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from loguru import logger

from backend.app.tools.base import BaseTool
from backend.app.models.schemas import RiskLevel


class DeveloperModeTool(BaseTool):
    """Developer assistant: VS Code, terminal, projects, git, code analysis."""

    def __init__(self) -> None:
        super().__init__()
        self._risk_level = RiskLevel.MEDIUM
        self._parameters = {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "open_vscode",
                        "create_project",
                        "run_command",
                        "git_status",
                        "git_commit",
                        "git_log",
                        "search_code",
                        "explain",
                    ],
                    "description": "Developer action to perform",
                },
                "project_path": {
                    "type": "string",
                    "description": "Path to project folder",
                },
                "project_name": {
                    "type": "string",
                    "description": "Name for new project",
                },
                "project_type": {
                    "type": "string",
                    "enum": ["python", "node", "react", "typescript", "empty"],
                    "description": "Type of project to create",
                },
                "command": {
                    "type": "string",
                    "description": "Command to run",
                },
                "message": {
                    "type": "string",
                    "description": "Commit message",
                },
                "query": {
                    "type": "string",
                    "description": "Search query for code search or explain",
                },
            },
            "required": ["action"],
        }

    @property
    def name(self) -> str:
        return "developer"

    @property
    def description(self) -> str:
        return "Developer mode: open VS Code, create projects, run commands, git operations, code search"

    async def execute(self, action: str, project_path: str = "", project_name: str = "",
                      project_type: str = "python", command: str = "", message: str = "",
                      query: str = "", **kwargs: Any) -> dict[str, Any]:
        handlers = {
            "open_vscode": self._open_vscode,
            "create_project": self._create_project,
            "run_command": self._run_cmd,
            "git_status": self._git_status,
            "git_commit": self._git_commit,
            "git_log": self._git_log,
            "search_code": self._search_code,
            "explain": self._explain,
        }

        handler = handlers.get(action)
        if not handler:
            return {"success": False, "error": f"Unknown action: {action}", "result": ""}

        return await handler(
            project_path=project_path, project_name=project_name,
            project_type=project_type, command=command,
            message=message, query=query,
        )

    async def _find_vscode(self) -> str:
        """Find VS Code executable path."""
        import shutil
        paths = [
            shutil.which("code") or "",
            shutil.which("code.cmd") or "",
            r"C:\Program Files\Microsoft VS Code\Code.exe",
            r"C:\Program Files (x86)\Microsoft VS Code\Code.exe",
            str(Path.home() / "AppData" / "Local" / "Programs" / "Microsoft VS Code" / "Code.exe"),
        ]
        for p in paths:
            if p and Path(p).exists():
                return p
        return "code"  # Fallback to PATH

    async def _open_vscode(self, project_path: str = "", **kwargs: Any) -> dict[str, Any]:
        """Open VS Code, optionally in a specific project."""
        try:
            code = await self._find_vscode()
            if project_path:
                resolved = Path(project_path).resolve()
                if resolved.exists():
                    subprocess.Popen([code, str(resolved)], shell=False)
                    return {"success": True, "result": f"Opened VS Code at {project_path}"}
                else:
                    return {"success": False, "error": f"Project not found: {project_path}", "result": ""}
            else:
                subprocess.Popen([code, "."], shell=False)
                return {"success": True, "result": "Opened VS Code"}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _create_project(self, project_name: str = "", project_type: str = "python",
                              project_path: str = "", **kwargs: Any) -> dict[str, Any]:
        """Create a new project scaffolding."""
        if not project_name:
            return {"success": False, "error": "Project name required", "result": ""}

        base = Path(project_path).resolve() if project_path else Path.cwd()
        proj_dir = base / project_name

        try:
            proj_dir.mkdir(parents=True, exist_ok=True)

            if project_type == "python":
                (proj_dir / "src").mkdir(exist_ok=True)
                (proj_dir / "tests").mkdir(exist_ok=True)
                (proj_dir / "README.md").write_text(f"# {project_name}\n\n## Description\n\n## Installation\n\n```bash\npip install -r requirements.txt\n```\n", encoding="utf-8")
                (proj_dir / "requirements.txt").write_text("# Add dependencies here\n", encoding="utf-8")
                (proj_dir / "src" / "__init__.py").write_text(f"\"\"\"{project_name} package.\"\"\"\n", encoding="utf-8")
                (proj_dir / "src" / "main.py").write_text(f"\"\"\"{project_name} - Main entry point.\"\"\"\n\n\ndef main():\n    print(\"Hello from {project_name}!\")\n\n\nif __name__ == \"__main__\":\n    main()\n", encoding="utf-8")

            elif project_type in ("node", "react", "typescript"):
                (proj_dir / "src").mkdir(exist_ok=True)
                (proj_dir / "package.json").write_text(
                    '{\n  "name": "' + project_name + '",\n  "version": "1.0.0",\n  "private": true,\n  "scripts": {\n    "start": "node src/index.js",\n    "test": "echo \\"No tests yet\\""\n  }\n}\n', encoding="utf-8")
                (proj_dir / "src" / "index.js").write_text(f"// {project_name}\nconsole.log('Hello from {project_name}!');\n", encoding="utf-8")

            else:
                (proj_dir / "README.md").write_text(f"# {project_name}\n", encoding="utf-8")

            # Initialize git
            try:
                subprocess.run(["git", "init"], cwd=str(proj_dir), capture_output=True, timeout=5)
            except Exception:
                pass

            # Open in VS Code
            try:
                code = await self._find_vscode()
                subprocess.Popen([code, str(proj_dir)], shell=False)
            except Exception:
                pass

            return {"success": True, "result": f"Created {project_type} project '{project_name}' at {proj_dir}"}

        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _run_cmd(self, command: str = "", **kwargs: Any) -> dict[str, Any]:
        """Run a terminal command and return output."""
        if not command:
            return {"success": False, "error": "Command required", "result": ""}

        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=30,
            )
            output = result.stdout or result.stderr or ""
            if len(output) > 2000:
                output = output[:2000] + "\n... [output truncated]"
            return {
                "success": result.returncode == 0,
                "result": output,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timed out after 30s", "result": ""}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _git_status(self, project_path: str = "", **kwargs: Any) -> dict[str, Any]:
        """Show git status of a project."""
        cwd = Path(project_path).resolve() if project_path else Path.cwd()
        try:
            result = subprocess.run(
                ["git", "status"], cwd=str(cwd), capture_output=True, text=True, timeout=10,
            )
            return {"success": True, "result": result.stdout or result.stderr}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _git_commit(self, message: str = "", project_path: str = "", **kwargs: Any) -> dict[str, Any]:
        """Stage all changes and create a git commit."""
        if not message:
            return {"success": False, "error": "Commit message required", "result": ""}

        cwd = Path(project_path).resolve() if project_path else Path.cwd()
        try:
            subprocess.run(["git", "add", "-A"], cwd=str(cwd), capture_output=True, timeout=10)
            result = subprocess.run(
                ["git", "commit", "-m", message], cwd=str(cwd), capture_output=True, text=True, timeout=10,
            )
            return {"success": result.returncode == 0, "result": result.stdout or result.stderr}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _git_log(self, project_path: str = "", **kwargs: Any) -> dict[str, Any]:
        """Show recent git commit history."""
        cwd = Path(project_path).resolve() if project_path else Path.cwd()
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-10"], cwd=str(cwd), capture_output=True, text=True, timeout=10,
            )
            return {"success": True, "result": result.stdout or (result.stderr if result.stderr else "No commits yet")}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _search_code(self, query: str = "", project_path: str = "", **kwargs: Any) -> dict[str, Any]:
        """Search for code patterns in a project."""
        if not query:
            return {"success": False, "error": "Search query required", "result": ""}

        import shutil
        cwd = Path(project_path).resolve() if project_path else Path.cwd()

        # Use grep on Linux/Mac, findstr on Windows
        if shutil.which("grep"):
            try:
                result = subprocess.run(
                    ["grep", "-r", "-n", "--include=*.py", "--include=*.js", "--include=*.ts",
                     "--include=*.jsx", "--include=*.tsx", "--include=*.html", "--include=*.css",
                     "-l", query, "."],
                    cwd=str(cwd), capture_output=True, text=True, timeout=15,
                )
                if result.stdout:
                    files = result.stdout.strip().split("\n")
                    output = f"Found in {len(files)} file(s):\n" + "\n".join(files[:20])
                    return {"success": True, "result": output, "count": len(files)}
                return {"success": True, "result": f"No files matching '{query}'"}
            except Exception as e:
                return {"success": False, "error": str(e), "result": ""}

        # Windows fallback using findstr
        try:
            result = subprocess.run(
                ["findstr", "/S", "/M", "/I", query, "*.py", "*.js", "*.ts", "*.jsx", "*.tsx"],
                cwd=str(cwd), capture_output=True, text=True, timeout=15,
            )
            if result.stdout:
                files = [f for f in result.stdout.strip().split("\n") if f.strip()]
                output = f"Found in {len(files)} file(s):\n" + "\n".join(files[:20])
                return {"success": True, "result": output, "count": len(files)}
            return {"success": True, "result": f"No files matching '{query}'"}
        except Exception as e:
            return {"success": False, "error": str(e), "result": ""}

    async def _explain(self, query: str = "", **kwargs: Any) -> dict[str, Any]:
        """Explain a code error or concept.
        This acts as a trigger for the AI to provide an explanation.
        """
        if not query:
            return {"success": False, "error": "What should I explain?", "result": ""}
        # This returns a prompt instruction for the AI to explain
        return {
            "success": True,
            "result": f"[EXPLAIN] {query}",
            "needs_llm": True,
        }
