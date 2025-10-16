"""VASP-HPC orchestration primitives and agent entry point."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .conversation import ConversationManager
from .settings import Settings, get_settings
from .subagents import ClaudeSubagentManager


@dataclass
class JobSpec:
    """Structured description of a single VASP job."""

    case_id: str
    system: str
    params: Dict[str, Any]
    hpc: Dict[str, Any]
    paths: Dict[str, str]


@dataclass
class PreparationArtifact:
    """Metadata produced after preparing inputs for a job."""

    job: JobSpec
    hashes: Dict[str, str]
    generated_files: Dict[str, Path]


class VASPOrchestrator:
    """Core VASP calculation orchestrator."""

    def __init__(
        self,
        config_path: str = "config/vasp_config.yaml",
        conversation_manager: Optional[ConversationManager] = None,
        subagent_config_path: Optional[str] = "config/claude_subagents.yaml",
        secrets_path: str = "config/secrets.yaml",
        settings: Optional[Settings] = None,
    ) -> None:
        self.settings: Settings = settings or get_settings(
            base_config_path=config_path,
            prompts_path="config/system_prompts.yaml",
            secrets_path=secrets_path,
        )
        self.config = self.settings.base
        self.local_workspace = Path(os.path.expanduser(self.config["paths"]["local_root"]))
        self.local_workspace.mkdir(parents=True, exist_ok=True)
        self._base_incar_defaults = self.settings.get_incar_defaults()

        # Allow dependency injection so the orchestrator can be reused in different workflows.
        self.conversation_manager = conversation_manager or ConversationManager(
            settings=self.settings
        )

        self.subagent_manager: Optional[ClaudeSubagentManager] = None
        if subagent_config_path and Path(subagent_config_path).exists():
            self.subagent_manager = ClaudeSubagentManager(
                self.conversation_manager,
                config_path=subagent_config_path,
            )

        # Maintain compatibility with legacy callers that expect an OpenAI client attribute.
        self.client = self.conversation_manager.client

    # ------------------------------------------------------------------
    # Public API helpers kept for backwards compatibility with previous
    # tool signatures. The new agent wrapper relies on the richer
    # methods below.
    # ------------------------------------------------------------------
    def plan_vasp_jobs(self, instruction: str) -> List[Dict[str, Any]]:
        job_specs = self.plan_jobs(instruction)
        return [self._job_spec_to_dict(job) for job in job_specs]

    def prepare_vasp_inputs(self, job_spec_data: Dict[str, Any]) -> Dict[str, str]:
        job_spec = self._dict_to_job_spec(job_spec_data)
        return self.prepare_inputs(job_spec).hashes

    def generate_approval_summary_method(self, job_specs_data: List[Dict[str, Any]]) -> str:
        job_specs = [self._dict_to_job_spec(job) for job in job_specs_data]
        return self.generate_approval_summary(job_specs)

    # ------------------------------------------------------------------
    # Core workflow primitives
    # ------------------------------------------------------------------
    def plan_jobs(self, instruction: str) -> List[JobSpec]:
        """Parse natural language instructions into job specifications using the LLM."""

        ai_analysis: Dict[str, Any] = {}

        if self.subagent_manager and self.subagent_manager.has_agent("analysis"):
            ai_analysis = self.subagent_manager.analyze_instruction(instruction)

        if not ai_analysis:
            ai_analysis = self._analyze_with_ai(instruction)
        base_params = self._base_incar_defaults.copy()
        jobs: List[JobSpec] = []

        if ai_analysis.get("material") and ai_analysis.get("calculations"):
            jobs.extend(self._create_jobs_from_ai_analysis(ai_analysis, base_params))
        else:
            jobs.extend(self._fallback_parse(instruction, base_params))

        return jobs

    def prepare_inputs(self, job_spec: JobSpec) -> PreparationArtifact:
        """Prepare VASP input files from a job specification."""

        case_dir = Path(job_spec.paths["local_dir"])
        case_dir.mkdir(parents=True, exist_ok=True)

        rendered_files = self._render_job_files(job_spec)
        generated_files: Dict[str, Path] = {}
        hashes: Dict[str, str] = {}

        for name, content in rendered_files.items():
            path = case_dir / name
            self._write_text_if_changed(path, content)
            generated_files[name] = path
            hashes[name] = self._hash_file(path)

        hashes_path = case_dir / "hashes.json"
        hashes_content = json.dumps(hashes, indent=2)
        self._write_text_if_changed(hashes_path, hashes_content)
        generated_files["hashes.json"] = hashes_path

        return PreparationArtifact(job=job_spec, hashes=hashes, generated_files=generated_files)

    def generate_approval_summary(self, job_specs: Iterable[JobSpec]) -> str:
        lines = ["VASP Job Submission Summary", "=" * 40, ""]

        for job in job_specs:
            lines.append(f"Case ID: {job.case_id}")
            lines.append(f"System: {job.system}")
            lines.append(f"INCAR parameters: {job.params['incar']}")
            lines.append(f"KPOINTS: {job.params['kpoints']}")
            lines.append(f"HPC resources: {job.hpc}")
            lines.append("-" * 20)

        lines.append("")
        lines.append("To approve all jobs, use: approve('all')")
        lines.append("To approve specific job, use: approve('case_id')")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _job_spec_to_dict(self, job_spec: JobSpec) -> Dict[str, Any]:
        return {
            "case_id": job_spec.case_id,
            "system": job_spec.system,
            "params": job_spec.params,
            "hpc": job_spec.hpc,
            "paths": job_spec.paths,
        }

    def _dict_to_job_spec(self, data: Dict[str, Any]) -> JobSpec:
        return JobSpec(
            case_id=data["case_id"],
            system=data["system"],
            params=data["params"],
            hpc=data["hpc"],
            paths=data["paths"],
        )

    def _hash_file(self, file_path: Path) -> str:
        with file_path.open("rb") as handle:
            try:
                return hashlib.file_digest(handle, "sha256").hexdigest()
            except AttributeError:  # pragma: no cover - Python < 3.11 fallback
                handle.seek(0)
                digest = hashlib.sha256()
                for chunk in iter(lambda: handle.read(8192), b""):
                    digest.update(chunk)
                return digest.hexdigest()

    def _write_text_if_changed(self, target: Path, content: str) -> None:
        if target.exists():
            current = target.read_text()
            if current == content:
                return
        target.write_text(content)

    def _render_job_files(self, job_spec: JobSpec) -> Dict[str, str]:
        return {
            "INCAR": self._generate_incar(job_spec.params["incar"]),
            "KPOINTS": self._generate_kpoints(job_spec.params["kpoints"]),
            "run.slurm": self._generate_slurm_script(job_spec),
        }

    def _analyze_with_ai(self, instruction: str) -> Dict[str, Any]:
        try:
            system_prompt = self.conversation_manager.config["vasp_analysis_prompt"]
            result = self.conversation_manager.chat(
                input_text=f"请解析这个VASP计算需求：{instruction}",
                system_prompt=system_prompt,
                temperature=0.3,
            )

            if result.get("status") != "success":
                print(f"❌ AI分析失败: {result.get('error', '未知错误')}")
                return {}

            response_text = result["response"]
            print(f"✅ AI分析完成 (耗时: {result['response_time']:.2f}s)")

            import re

            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            print("⚠️ AI回复中未找到JSON格式，使用回退方案")
            return {}
        except Exception as exc:  # pragma: no cover - defensive logging
            print(f"AI解析失败，使用回退方案: {exc}")
            return {}

    def _create_jobs_from_ai_analysis(
        self, analysis: Dict[str, Any], base_params: Dict[str, Any]
    ) -> List[JobSpec]:
        jobs: List[JobSpec] = []
        material = analysis.get("material", "Unknown")
        calculations = analysis.get("calculations", [])

        for calc in calculations:
            calc_type = calc.get("type", "scf")
            case_id = f"{material}_{calc_type}"

            job_spec = JobSpec(
                case_id=case_id,
                system=material,
                params={
                    "incar": {**base_params, **calc.get("parameters", {})},
                    "kpoints": calc.get(
                        "kpoints", {"mode": "Monkhorst-Pack", "grid": [6, 6, 6]}
                    ),
                    "poscar_path": calc.get(
                        "poscar_path", f"templates/structures/{material}_POSCAR.txt"
                    ),
                    "potcar_symbols": calc.get("potcar_symbols", [material]),
                },
                hpc=self.config["hpc"],
                paths={
                    "local_dir": str(self.local_workspace / case_id),
                    "remote_dir": f"{self.config['paths']['remote_root']}/{case_id}",
                },
            )
            jobs.append(job_spec)

        return jobs

    def _fallback_parse(self, instruction: str, base_params: Dict[str, Any]) -> List[JobSpec]:
        print("⚠️ LLM解析未能生成有效的计算计划")
        print("💡 请尝试更详细地描述您的计算需求，例如：")
        print("   - 材料名称和结构")
        print("   - 计算类型（几何优化、自洽场、能带结构等）")
        print("   - 关键参数（截断能、k点密度、收敛标准等）")
        return []

    def _generate_incar(self, incar_params: Dict[str, Any]) -> str:
        lines = ["VASP INCAR file", "=" * 20]
        for key, value in incar_params.items():
            lines.append(f"{key} = {value}")
        return "\n".join(lines) + "\n"

    def _generate_kpoints(self, kpoints_params: Dict[str, Any]) -> str:
        if "content" in kpoints_params:
            return kpoints_params["content"]

        mode = kpoints_params.get("mode", "Monkhorst-Pack")

        if mode == "Gamma" and "grid" in kpoints_params:
            grid = kpoints_params["grid"]
            return (
                "Automatic mesh\n0\nGamma\n"
                f"{grid[0]} {grid[1]} {grid[2]} 0 0 0"
            )
        if mode == "Monkhorst-Pack" and "grid" in kpoints_params:
            grid = kpoints_params["grid"]
            return (
                "Automatic mesh\n0\nMonkhorst-Pack\n"
                f"{grid[0]} {grid[1]} {grid[2]} 0 0 0"
            )
        if mode == "Line-mode":
            if "path" in kpoints_params:
                return kpoints_params["path"]
            return (
                "Line-mode KPOINTS file (content should be provided by LLM)\n"
                "40\n"
                "Reciprocal\n"
                "# K-point path should be generated by LLM based on material structure"
            )

        return "KPOINTS file generated from LLM parameters\n# All k-point settings should be intelligently generated by LLM"

    def _generate_slurm_script(self, job_spec: JobSpec) -> str:
        hpc = job_spec.hpc
        case_id = job_spec.case_id
        vasp_module = self.config["env"]["vasp_module"]
        vasp_exec = self.config["env"]["vasp_exec"]
        potcar_root = self.config["env"]["potcar_root"]

        return (
            "#!/bin/bash\n"
            f"#SBATCH -p {hpc['partition']}\n"
            f"#SBATCH -N {hpc['nodes']}\n"
            f"#SBATCH --ntasks-per-node={hpc['ntasks_per_node']}\n"
            f"#SBATCH -J {case_id}\n"
            "#SBATCH -o vasp.out\n"
            f"#SBATCH -t {hpc['walltime_minutes']}:00:00\n\n"
            "export OMP_NUM_THREADS=1\n"
            f"module load {vasp_module}\n"
            "module list -t &> module_snapshot.txt\n\n"
            f"export VASP_PP_PATH={potcar_root}\n\n"
            f"# Build POTCAR for {case_id}\n"
            "# POTCAR will be built based on the specific elements in the calculation\n"
            "# Example for SiC: cat $VASP_PP_PATH/Si/POTCAR $VASP_PP_PATH/C/POTCAR > POTCAR\n\n"
            f"mpirun -np $SLURM_NTASKS {vasp_exec}\n"
        )


class VaspAgent:
    """High-level asynchronous agent facade wrapping :class:`VASPOrchestrator`."""

    def __init__(self, orchestrator: VASPOrchestrator) -> None:
        self._orchestrator = orchestrator

    async def __call__(self, instruction: str) -> str:
        return await asyncio.to_thread(self._process_instruction, instruction)

    # ------------------------------------------------------------------
    # Synchronous processing pipeline executed in a worker thread.
    # ------------------------------------------------------------------
    def _process_instruction(self, instruction: str) -> str:
        jobs = self._orchestrator.plan_jobs(instruction)
        if not jobs:
            return "未能根据输入生成VASP作业计划，请提供更详细的计算需求。"

        artifacts = [self._orchestrator.prepare_inputs(job) for job in jobs]
        summary = self._orchestrator.generate_approval_summary(jobs)
        details = self._format_preparation_report(artifacts)
        return f"{summary}\n\n{details}"

    def _format_preparation_report(self, artifacts: Iterable[PreparationArtifact]) -> str:
        lines = ["Prepared job inputs:", ""]
        for artifact in artifacts:
            lines.append(f"• {artifact.job.case_id}")
            lines.append(f"   - Local dir: {artifact.job.paths['local_dir']}")
            lines.append(f"   - Remote dir: {artifact.job.paths['remote_dir']}")
            for name, digest in artifact.hashes.items():
                lines.append(f"   - {name}: {digest}")
            lines.append(
                "   - HPC: "
                f"partition={artifact.job.hpc['partition']}, "
                f"nodes={artifact.job.hpc['nodes']}, "
                f"ntasks_per_node={artifact.job.hpc['ntasks_per_node']}"
            )
            lines.append("")
        return "\n".join(lines).strip()


def create_vasp_agent(
    config_path: str = "config/vasp_config.yaml",
    *,
    secrets_path: str = "config/secrets.yaml",
    settings: Optional[Settings] = None,
) -> VaspAgent:
    """Factory that wires together the orchestrator and exposes an async agent."""

    orchestrator = VASPOrchestrator(
        config_path=config_path,
        secrets_path=secrets_path,
        settings=settings,
    )
    return VaspAgent(orchestrator)
