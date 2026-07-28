"""User Profile System.

Permanent, queryable user profile that aggregates:
- Identity information (name, contact, location)
- Active projects with context and tech stacks
- Personal context (preferences, goals, interests)
- Communication style and tone preferences

Unlike the general FactsMemory, this is a structured profile
with explicit fields that the AI can query and update directly.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from backend.app.config import settings


class UserProject:
    """Represents an active project the user is working on."""

    def __init__(
        self,
        name: str,
        description: str = "",
        tech_stack: list[str] | None = None,
        status: str = "active",
        url: str = "",
        notes: str = "",
    ) -> None:
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.tech_stack = tech_stack or []
        self.status = status  # active, paused, completed, archived
        self.url = url
        self.notes = notes
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tech_stack": self.tech_stack,
            "status": self.status,
            "url": self.url,
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserProject":
        obj = cls(
            name=data["name"],
            description=data.get("description", ""),
            tech_stack=data.get("tech_stack", []),
            status=data.get("status", "active"),
            url=data.get("url", ""),
            notes=data.get("notes", ""),
        )
        obj.id = data.get("id", obj.id)
        obj.created_at = data.get("created_at", obj.created_at)
        obj.updated_at = data.get("updated_at", obj.updated_at)
        return obj


class UserProfile:
    """Permanent user profile with structured personal information.

    This is the single source of truth for who the user is.
    The AI can query this directly rather than guessing from conversation history.
    """

    def __init__(self) -> None:
        self._profile: dict[str, Any] = {}
        self._projects: dict[str, UserProject] = {}
        self._initialized = False

    async def initialize(self) -> bool:
        """Load profile from persistent storage."""
        try:
            profile_file = settings.get_data_path("memory") / "user_profile.json"
            if profile_file.exists():
                with open(profile_file, "r") as f:
                    data = json.load(f)

                self._profile = data.get("profile", {})
                for proj_data in data.get("projects", []):
                    project = UserProject.from_dict(proj_data)
                    self._projects[project.id] = project

                logger.info(f"User profile loaded ({len(self._projects)} projects)")
            else:
                # Create default profile
                self._profile = {
                    "name": "",
                    "email": "",
                    "location": "",
                    "occupation": "",
                    "timezone": "UTC",
                    "preferred_language": "en",
                    "communication_style": "professional",  # professional, casual, technical
                    "response_length": "balanced",  # concise, balanced, detailed
                    "interests": [],
                    "goals": [],
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                }
                await self._persist()
                logger.info("New user profile created")

        except Exception as e:
            logger.warning(f"Could not load user profile: {e}")
            self._profile = {"name": ""}

        self._initialized = True
        return True

    # --- Identity ---

    async def get_identity_summary(self) -> str:
        """Get a concise summary of the user's identity for AI prompts."""
        parts = []
        if self._profile.get("name"):
            parts.append(f"Name: {self._profile['name']}")
        if self._profile.get("occupation"):
            parts.append(f"Occupation: {self._profile['occupation']}")
        if self._profile.get("location"):
            parts.append(f"Location: {self._profile['location']}")
        if self._profile.get("communication_style"):
            parts.append(f"Communication style: {self._profile['communication_style']}")
        if self._profile.get("response_length"):
            parts.append(f"Response length preference: {self._profile['response_length']}")

        return " | ".join(parts) if parts else ""

    async def get_field(self, key: str, default: Any = "") -> Any:
        """Get a profile field value."""
        return self._profile.get(key, default)

    async def set_field(self, key: str, value: Any) -> None:
        """Set a profile field value and persist."""
        self._profile[key] = value
        self._profile["updated_at"] = datetime.now().isoformat()
        await self._persist()

    async def update_identity(self, updates: dict[str, Any]) -> dict[str, Any]:
        """Update multiple profile fields at once.

        Args:
            updates: Dict of field key-value pairs.

        Returns:
            The updated profile.
        """
        self._profile.update(updates)
        self._profile["updated_at"] = datetime.now().isoformat()
        await self._persist()
        logger.info(f"User profile updated: {list(updates.keys())}")
        return self._profile

    # --- Projects ---

    async def add_project(
        self,
        name: str,
        description: str = "",
        tech_stack: list[str] | None = None,
        status: str = "active",
        url: str = "",
        notes: str = "",
    ) -> UserProject:
        """Add a new project to the user's profile.

        Args:
            name: Project name.
            description: Project description.
            tech_stack: Technologies used.
            status: Project status (active, paused, completed, archived).
            url: Project URL if applicable.
            notes: Additional notes.

        Returns:
            The created UserProject.
        """
        project = UserProject(
            name=name,
            description=description,
            tech_stack=tech_stack,
            status=status,
            url=url,
            notes=notes,
        )
        self._projects[project.id] = project
        await self._persist()
        logger.info(f"Project added: {name}")
        return project

    async def update_project(self, project_id: str, **updates) -> UserProject | None:
        """Update a project's fields."""
        project = self._projects.get(project_id)
        if not project:
            return None

        for key, value in updates.items():
            if hasattr(project, key):
                setattr(project, key, value)

        project.updated_at = datetime.now().isoformat()
        await self._persist()
        return project

    async def get_project(self, project_id: str) -> UserProject | None:
        """Get a specific project."""
        return self._projects.get(project_id)

    async def get_active_projects(self) -> list[UserProject]:
        """Get all active projects."""
        return [p for p in self._projects.values() if p.status == "active"]

    async def get_all_projects(self) -> list[UserProject]:
        """Get all projects."""
        return list(self._projects.values())

    async def delete_project(self, project_id: str) -> bool:
        """Delete a project."""
        if project_id in self._projects:
            del self._projects[project_id]
            await self._persist()
            return True
        return False

    async def get_projects_summary(self) -> str:
        """Get a formatted summary of active projects for AI prompts."""
        active = await self.get_active_projects()
        if not active:
            return ""

        lines = ["**Active Projects:**"]
        for proj in active:
            stack = ", ".join(proj.tech_stack) if proj.tech_stack else ""
            lines.append(f"• {proj.name}")
            if stack:
                lines.append(f"  Tech: {stack}")
            if proj.description:
                lines.append(f"  {proj.description[:100]}")

        return "\n".join(lines)

    # --- Interests & Goals ---

    async def add_interest(self, interest: str) -> None:
        """Add an interest to the user's profile."""
        if interest not in self._profile.get("interests", []):
            self._profile.setdefault("interests", []).append(interest)
            await self._persist()

    async def add_goal(self, goal: str) -> None:
        """Add a goal to the user's profile."""
        if goal not in self._profile.get("goals", []):
            self._profile.setdefault("goals", []).append(goal)
            await self._persist()

    async def get_interests_summary(self) -> str:
        """Get a formatted summary of user interests."""
        interests = self._profile.get("interests", [])
        goals = self._profile.get("goals", [])

        parts = []
        if interests:
            parts.append(f"Interests: {', '.join(interests)}")
        if goals:
            parts.append(f"Goals: {', '.join(goals)}")

        return " | ".join(parts) if parts else ""

    # --- Full Profile ---

    async def get_full_context(self) -> str:
        """Get the complete user profile as context for AI prompts."""
        parts = []

        identity = await self.get_identity_summary()
        if identity:
            parts.append(identity)

        projects = await self.get_projects_summary()
        if projects:
            parts.append(projects)

        interests = await self.get_interests_summary()
        if interests:
            parts.append(interests)

        return "\n".join(parts) if parts else ""

    async def get_all_raw(self) -> dict[str, Any]:
        """Get all profile data (for export/debug)."""
        return {
            "profile": self._profile,
            "projects": [p.to_dict() for p in self._projects.values()],
        }

    async def clear_profile(self) -> None:
        """Clear all profile data (privacy: right to forget)."""
        self._profile = {"name": ""}
        self._projects.clear()
        await self._persist()
        logger.info("User profile cleared")

    async def clear_project_data(self) -> None:
        """Clear only project data, keep identity."""
        self._projects.clear()
        await self._persist()

    async def get_stats(self) -> dict[str, Any]:
        """Get profile statistics."""
        return {
            "has_name": bool(self._profile.get("name")),
            "has_email": bool(self._profile.get("email")),
            "active_projects": len(await self.get_active_projects()),
            "total_projects": len(self._projects),
            "interests_count": len(self._profile.get("interests", [])),
            "goals_count": len(self._profile.get("goals", [])),
        }

    async def _persist(self) -> None:
        """Persist profile to disk."""
        try:
            profile_file = settings.get_data_path("memory") / "user_profile.json"
            data = {
                "profile": self._profile,
                "projects": [p.to_dict() for p in self._projects.values()],
            }
            with open(profile_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Failed to persist user profile: {e}")
