"""Claude Code compatible sub-agent orchestration utilities."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

import yaml

from .conversation import ConversationManager


@dataclass
class SubagentSpec:
    """Configuration for a Claude Code sub-agent."""

    name: str
    description: str
    system_prompt: str
    task_template: str
    temperature: float = 0.2
    expect_json: bool = True


class ClaudeSubagent:
    """Lightweight wrapper around :class:`ConversationManager` sessions."""

    def __init__(
        self,
        spec: SubagentSpec,
        conversation_factory: Callable[[], ConversationManager],
    ) -> None:
        self.spec = spec
        self._conversation_factory = conversation_factory

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(
        self,
        instruction: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute the sub-agent task and return structured results."""

        prompt = self._build_prompt(instruction, context)
        session = self._conversation_factory()
        result = session.chat(
            input_text=prompt,
            system_prompt=self.spec.system_prompt,
            temperature=self.spec.temperature,
        )

        output: Dict[str, Any] = {
            "status": result.get("status", "error"),
            "response": result.get("response"),
            "metadata": result,
            "parsed": None,
            "errors": [],
        }

        if result.get("status") == "success" and self.spec.expect_json:
            parsed = self._extract_json(result.get("response", ""))
            if parsed is not None:
                output["parsed"] = parsed
            else:
                output["errors"].append("Failed to parse JSON payload from Claude response")

        return output

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_prompt(
        self,
        instruction: str,
        context: Optional[Dict[str, Any]],
    ) -> str:
        variables: Dict[str, Any] = {"instruction": instruction}

        if context:
            for key, value in context.items():
                if isinstance(value, str):
                    variables[key] = value
                else:
                    variables[key] = json.dumps(value, ensure_ascii=False, indent=2)

        try:
            return self.spec.task_template.format(**variables)
        except KeyError as exc:  # pragma: no cover - defensive guard
            raise KeyError(
                f"Missing template variable {exc!s} for subagent '{self.spec.name}'"
            ) from exc

    def _extract_json(self, text: str) -> Optional[Any]:
        if not text:
            return None

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None

        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None


class ClaudeSubagentManager:
    """Manager that loads and coordinates Claude Code sub-agents."""

    def __init__(
        self,
        conversation_manager: ConversationManager,
        config_path: str = "config/claude_subagents.yaml",
        conversation_factory: Optional[Callable[[], ConversationManager]] = None,
    ) -> None:
        self._root_manager = conversation_manager
        self._conversation_factory = conversation_factory or (
            lambda: conversation_manager.spawn_child()
        )
        self.config_path = Path(config_path)
        self.subagents: Dict[str, ClaudeSubagent] = {}

        self._load_config()

    # ------------------------------------------------------------------
    # Configuration loading
    # ------------------------------------------------------------------
    def _load_config(self) -> None:
        if not self.config_path.exists():
            return

        with open(self.config_path, "r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle) or {}

        for name, spec_data in config.get("subagents", {}).items():
            spec = SubagentSpec(
                name=name,
                description=spec_data.get("description", ""),
                system_prompt=spec_data.get("system_prompt", ""),
                task_template=spec_data.get("task_template", ""),
                temperature=float(spec_data.get("temperature", 0.2)),
                expect_json=bool(spec_data.get("expect_json", True)),
            )

            self.subagents[name] = ClaudeSubagent(spec, self._conversation_factory)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------
    @property
    def is_enabled(self) -> bool:
        return bool(self.subagents)

    def available_subagents(self) -> Iterable[str]:
        return tuple(self.subagents.keys())

    def has_agent(self, name: str) -> bool:
        return name in self.subagents

    def run(
        self,
        name: str,
        instruction: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if name not in self.subagents:
            raise KeyError(f"Subagent '{name}' is not configured")

        return self.subagents[name].run(instruction, context)

    def analyze_instruction(self, instruction: str) -> Dict[str, Any]:
        if not self.has_agent("analysis"):
            return {}

        result = self.run("analysis", instruction)
        parsed = result.get("parsed")
        return parsed if isinstance(parsed, dict) else {}

    def plan_vasp_work(
        self,
        instruction: str,
        analysis: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.has_agent("planner"):
            return {}

        context = {"analysis": analysis or {}}
        result = self.run("planner", instruction, context=context)
        parsed = result.get("parsed")
        return parsed if isinstance(parsed, dict) else {}

    def review_plan(self, plan: Dict[str, Any]) -> Optional[str]:
        if not self.has_agent("reviewer"):
            return None

        result = self.run("reviewer", instruction="", context={"plan": plan})
        if result.get("status") != "success":
            return None

        return result.get("response")


__all__ = ["ClaudeSubagent", "ClaudeSubagentManager", "SubagentSpec"]

