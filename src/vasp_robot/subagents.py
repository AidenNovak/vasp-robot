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
            "errors": [],
        }

        if result.get("status") == "success":
            response_text = result.get("response", "")

            if self.spec.expect_json:
                # Try to extract JSON, but don't fail if we can't
                parsed = self._extract_json(response_text)
                if parsed is not None:
                    output["parsed"] = parsed
                else:
                    # If JSON parsing fails, return the raw response as content
                    output["content"] = response_text
                    print("🔄 JSON parsing failed, returning raw content")
            else:
                # For non-JSON responses, return as content
                output["content"] = response_text

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
        """Extract JSON from text, handling truncated responses intelligently."""
        if not text:
            return None

        # Try to find JSON object in the text
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None

        json_str = match.group()

        # Remove common markdown formatting
        json_str = re.sub(r"```json\s*", "", json_str, flags=re.IGNORECASE)
        json_str = re.sub(r"```\s*$", "", json_str)
        json_str = json_str.strip()

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            # Handle truncated JSON responses intelligently
            print(f"🔧 Attempting to repair truncated JSON: {e}")
            return self._repair_truncated_json(json_str)

    def _repair_truncated_json(self, json_str: str) -> Optional[Any]:
        """Attempt to repair truncated JSON by completing missing structure."""

        # Find balanced braces
        brace_count = 0
        in_string = False
        escape_next = False
        end_pos = 0

        for i, char in enumerate(json_str):
            if escape_next:
                escape_next = False
                continue

            if char == '\\':
                escape_next = True
                continue

            if char == '"' and not escape_next:
                in_string = not in_string
                continue

            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_pos = i + 1
                        break

        # Extract the complete portion
        if end_pos > 0:
            try:
                truncated_json = json_str[:end_pos]
                parsed = json.loads(truncated_json)
                print("✅ Successfully parsed truncated JSON")
                return parsed
            except json.JSONDecodeError:
                pass

        # Try more aggressive repair for truncated arrays/objects
        try:
            # Find the last complete key-value pair or array element
            repaired = self._smart_json_repair(json_str)
            if repaired:
                parsed = json.loads(repaired)
                print("✅ Successfully repaired JSON structure")
                return parsed
        except Exception:
            pass

        # If repair fails, return error with partial info
        return {
            "error": "JSON response was truncated and could not be fully repaired",
            "truncated_at": len(json_str),
            "partial_preview": json_str[:300] + "..." if len(json_str) > 300 else json_str
        }

    def _smart_json_repair(self, json_str: str) -> Optional[str]:
        """Intelligently repair common JSON truncation patterns."""

        # Common truncation patterns and their fixes
        repairs = [
            # Truncated in the middle of a string
            (r'"[^"]*$', '"'),
            # Truncated after a colon (missing value)
            (r':\s*$', '": null"'),
            # Truncated in an array (missing closing bracket/brace)
            (r',\s*$', ']'),
            # Truncated after comma in object
            (r',\s*([^"}\s]+)\s*$', r': "\1"}'),
        ]

        repaired = json_str
        for pattern, replacement in repairs:
            if re.search(pattern, repaired):
                repaired = re.sub(pattern, replacement, repaired)
                break

        # Ensure balanced braces
        open_braces = repaired.count('{')
        close_braces = repaired.count('}')
        if open_braces > close_braces:
            repaired += '}' * (open_braces - close_braces)

        # Ensure balanced brackets
        open_brackets = repaired.count('[')
        close_brackets = repaired.count(']')
        if open_brackets > close_brackets:
            repaired += ']' * (open_brackets - close_brackets)

        # Remove trailing commas before closing brackets/braces
        repaired = re.sub(r',(\s*[}\]])', r'\1', repaired)

        return repaired if repaired != json_str else None


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
        """Load subagent configuration from YAML file."""
        if not self.config_path.exists():
            print(f"⚠️ Subagent config file not found: {self.config_path}")
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as handle:
                config = yaml.safe_load(handle) or {}

            loaded_count = 0
            for name, spec_data in config.get("subagents", {}).items():
                try:
                    spec = SubagentSpec(
                        name=name,
                        description=spec_data.get("description", ""),
                        system_prompt=spec_data.get("system_prompt", ""),
                        task_template=spec_data.get("task_template", ""),
                        temperature=float(spec_data.get("temperature", 0.2)),
                        expect_json=bool(spec_data.get("expect_json", True)),
                    )

                    self.subagents[name] = ClaudeSubagent(spec, self._conversation_factory)
                    loaded_count += 1
                except Exception as e:
                    print(f"⚠️ Failed to load subagent '{name}': {e}")

            print(f"✅ Loaded {loaded_count} subagents from {self.config_path}")

        except Exception as e:
            print(f"❌ Failed to load subagent config: {e}")

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

        # Try to get parsed JSON first
        parsed = result.get("parsed")
        if parsed and isinstance(parsed, dict):
            return parsed

        # If no parsed JSON, try to extract from content
        content = result.get("content")
        if content:
            print("🔄 Extracting structured data from content...")
            extracted = self._extract_json(content)
            if extracted and isinstance(extracted, dict):
                return extracted

            # If still no structured data, create basic structure from content
            return {
                "raw_content": content,
                "material_system": self._extract_material_from_content(content),
                "scientific_problem": instruction[:200],
                "properties_of_interest": [],
                "calculation_goals": [],
                "analysis_brief": content[:500] + "..." if len(content) > 500 else content
            }

        return {}

    def _extract_material_from_content(self, content: str) -> str:
        """Extract material system from content text."""
        import re

        # Common material patterns
        patterns = [
            r'(SiC|silicon\s*carbide)',
            r'(Si|silicon)',
            r'(C|carbon|graphene|diamond)',
            r'([A-Z][a-z]?\d*[A-Z]?)',  # Simple chemical formula pattern
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1)

        return "Unknown"

    def plan_vasp_work(
        self,
        instruction: str,
        analysis: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.has_agent("planner"):
            return {}

        context = {"analysis": analysis or {}}
        result = self.run("planner", instruction, context=context)

        # Try to get parsed JSON first
        parsed = result.get("parsed")
        if parsed and isinstance(parsed, dict) and "error" not in parsed:
            return parsed

        # If no parsed JSON, try to extract from content
        content = result.get("content")
        if content:
            print("🔄 Creating VASP plan from raw content...")
            return self._create_plan_from_content(content, instruction, analysis)

        # If everything failed, use fallback
        print("🔄 Using fallback planner...")
        return self._fallback_planner(instruction, analysis)

    def _create_plan_from_content(self, content: str, instruction: str, analysis: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a VASP plan from raw text content."""

        return {
            "analysis_summary": f"Generated from content for {analysis.get('material_system', 'Unknown') if analysis else 'Unknown material'}",
            "calculation_plan": "Multi-step VASP workflow based on research requirements",
            "vasp_parameters": {
                "incar": self._extract_incar_params(content),
                "kpoints": self._extract_kpoints_params(content),
                "poscar_source": f"templates/structures/{analysis.get('material_system', 'Unknown')}_POSCAR.txt" if analysis else "templates/structures/default_POSCAR.txt",
                "potcar_sequence": self._extract_elements(content, analysis)
            },
            "hpc_requirements": {
                "nodes": 2,
                "ntasks_per_node": 24,
                "walltime": 48,  # hours
                "partition": "cpu"
            },
            "estimated_runtime": "2-3 days",
            "success_criteria": "Converged SCF, complete band structure, optical properties calculated",
            "source_content": content[:1000] + "..." if len(content) > 1000 else content
        }

    def _extract_incar_params(self, content: str) -> Dict[str, Any]:
        """Extract INCAR parameters from content."""
        params = {
            "ENCUT": 520,
            "EDIFF": 1e-6,
            "ISMEAR": 0,
            "SIGMA": 0.05,
            "IBRION": 2,
            "NSW": 100,
            "ISIF": 3
        }

        # Look for specific methods in content
        if "HSE" in content or "hybrid" in content.lower():
            params["LHFCALC"] = ".TRUE."
            params["AEXX"] = 0.25
            params["HFSCREEN"] = 0.2

        if "GW" in content:
            params["ALGO"] = "GW0"
            params["NELM"] = 1

        if "optical" in content.lower() or "dielectric" in content.lower():
            params["LOPTICS"] = ".TRUE."
            params["NEDOS"] = 2000

        return params

    def _extract_kpoints_params(self, content: str) -> str:
        """Extract k-points parameters from content."""
        if "dense" in content.lower() or "converged" in content.lower():
            return "Automatic mesh\n0\nMonkhorst-Pack\n12 12 8 0 0 0"
        return "Automatic mesh\n0\nMonkhorst-Pack\n8 8 6 0 0 0"

    def _extract_elements(self, content: str, analysis: Optional[Dict[str, Any]]) -> List[str]:
        """Extract element list from content and analysis."""
        elements = []

        if analysis:
            material = analysis.get("material_system", "")
            if "SiC" in material:
                elements = ["Si", "C"]
            elif "Si" in material:
                elements = ["Si"]
            elif "C" in material:
                elements = ["C"]

        # Fallback: look for element symbols in content
        if not elements:
            import re
            element_pattern = r'\b([A-Z][a-z]?)\b'
            found_elements = re.findall(element_pattern, content)
            # Filter common words
            elements = [el for el in found_elements if el not in ["H", "He", "Be", "PBE", "HSE", "GW", "BSE"]][:5]

        return elements if elements else ["Si"]  # Default to Si

    def _fallback_planner(self, instruction: str, analysis: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Fallback planner for complex requests that cause truncation."""

        # Simplify the instruction and analysis
        simplified_instruction = instruction[:200] + "..." if len(instruction) > 200 else instruction

        # Create a simplified analysis focusing on core requirements
        simplified_analysis = {
            "material_system": analysis.get("material_system", "Unknown"),
            "scientific_problem": analysis.get("scientific_problem", "VASP calculation"),
            "calculation_goals": analysis.get("calculation_goals", ["Basic calculation"])[:3]  # Limit to 3 goals
        }

        # Try planner again with simplified input
        context = {"analysis": simplified_analysis}
        result = self.run("planner", f"Create VASP plan for: {simplified_instruction}", context=context)
        parsed = result.get("parsed")

        if parsed and isinstance(parsed, dict) and "error" not in parsed:
            print("✅ Simplified planner succeeded")
            # Add note about simplification
            parsed["planning_note"] = "Generated from simplified analysis due to request complexity"
            return parsed

        # Final fallback - return basic structure
        print("⚠️ Using minimal fallback structure")
        return {
            "error": "All planning attempts failed",
            "material_system": analysis.get("material_system", "Unknown"),
            "planning_note": "Automatic planning failed - manual parameter setup required",
            "basic_suggestion": {
                "functional": "PBE",
                "encut": 520,
                "kpoints": "6x6x6",
                "ediff": 1e-6
            }
        }

    def review_plan(self, plan: Dict[str, Any]) -> Optional[str]:
        """Review a VASP plan using the reviewer subagent."""
        if not self.has_agent("reviewer"):
            return None

        instruction = f"Review this VASP job plan for technical accuracy and completeness."
        result = self.run("reviewer", instruction=instruction, context={"plan": plan})
        if result.get("status") != "success":
            print(f"⚠️ Plan review failed: {result.get('errors', ['Unknown error'])}")
            return None

        return result.get("response")


__all__ = ["ClaudeSubagent", "ClaudeSubagentManager", "SubagentSpec"]

