# Claude Code Integration Review & Enhancements

This document summarises the current Claude Code integration status, outlines
improvement opportunities, and captures the architectural updates introduced in
this iteration.

## Current strengths

- **Deterministic orchestration** – the legacy workflow already separates job
  planning, file generation, and HPC submission which maps well onto Claude
  Code’s tool calling.
- **Rich configuration** – YAML-based prompts and HPC settings make it easy to
  customise deployments across clusters.
- **Auditability** – hashing of generated files and workflow logging provide a
  traceable pipeline suitable for regulated lab environments.

## Key pain points for Claude Code

1. **Shared conversation state** – all prompts reused the same
   `ConversationManager` history which caused Claude to mix contexts between
   planning, analysis, and review phases.
2. **Single-agent bottleneck** – multi-step reasoning (analysis → planning →
   validation) depended on one large prompt, making it difficult to recover
   gracefully from partial failures.
3. **Limited configurability** – swapping Claude prompts or adding new helper
   agents required editing Python code directly.

## Enhancements delivered

1. **Sub-agent manager (`ClaudeSubagentManager`)**
   - Loads per-role prompts from `config/claude_subagents.yaml`.
   - Spawns isolated conversation sessions via `ConversationManager.spawn_child`
     so Claude can operate with clean context windows.
   - Provides helper methods for analysis, planning, and reviewer workflows.

2. **Workflow integration**
   - `VASPOrchestrator` now prefers Claude sub-agents for the initial job
     analysis before falling back to the legacy parsing prompts.
   - `VASPResearchWorkflow` consumes the same sub-agents to produce
     `ResearchRequest` and `VASPJobSpec` objects, while still supporting the
     previous Kimi-only flow as a fallback.

3. **Configurable reviewer loop**
   - Optional reviewer prompt produces a short risk checklist without blocking
     the main pipeline, allowing Claude Code to surface potential issues for
     the human operator.

## Recommended next steps

1. **Tool calling hooks** – expose lightweight Python callables (e.g. `upload`,
   `submit`, `monitor`) so Claude’s tool API can be mapped to the existing
   automation layer.
2. **Structured validation** – expand the reviewer response into machine
   readable JSON so automated gating (approve/deny) can be layered on top of the
   human review step.
3. **Fine-grained logging** – stream per-sub-agent telemetry (prompt tokens,
   response latency) to help benchmark different Claude models or temperatures.
4. **Unit tests** – create fixtures that simulate Claude responses, ensuring the
   parsing logic remains robust when prompts evolve.

With these improvements Claude Code can orchestrate the workflow as the primary
agent while remaining backwards compatible with Kimi-driven executions.
