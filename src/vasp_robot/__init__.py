"""Unified package exposing the VASP robot building blocks."""

from .conversation import ConversationManager
from .hpc_automation import HPCAutomation
from .hpc_interface import HPCConfig, HPCInterface
from .orchestrator import (
    JobSpec,
    PreparationArtifact,
    VASPOrchestrator,
    VaspAgent,
    create_vasp_agent,
)
from .subagents import ClaudeSubagentManager

__all__ = [
    "ConversationManager",
    "HPCAutomation",
    "HPCConfig",
    "HPCInterface",
    "JobSpec",
    "PreparationArtifact",
    "VASPOrchestrator",
    "VaspAgent",
    "create_vasp_agent",
    "ClaudeSubagentManager",
]
