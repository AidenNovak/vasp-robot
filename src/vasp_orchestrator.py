"""
VASP-HPC Orchestrator Agent
A Claude Code agent for managing VASP calculations on HPC clusters.
"""

import os
import json
import hashlib
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import yaml
from openai import OpenAI
from src.conversation_manager import ConversationManager


@dataclass
class JobSpec:
    """VASP job specification"""
    case_id: str
    system: str
    params: Dict[str, Any]
    hpc: Dict[str, Any]
    paths: Dict[str, str]


class VASPOrchestrator:
    """Core VASP calculation orchestrator"""

    def __init__(self, config_path: str = "config/vasp_config.yaml"):
        self.config = self._load_config(config_path)
        self.local_workspace = Path(os.path.expanduser(self.config["paths"]["local_root"]))
        self.local_workspace.mkdir(parents=True, exist_ok=True)

        # 初始化对话管理器
        self.conversation_manager = ConversationManager("config/system_prompts.yaml")

        # 保持向后兼容
        self.client = self.conversation_manager.client

    # Simple methods without tool decorators for now
    def plan_vasp_jobs(self, instruction: str) -> List[Dict[str, Any]]:
        """Plan VASP calculations from natural language instruction"""
        job_specs = self.plan_jobs(instruction)
        return [self._job_spec_to_dict(job) for job in job_specs]

    def prepare_vasp_inputs(self, job_spec_data: Dict[str, Any]) -> Dict[str, str]:
        """Prepare VASP input files from job specification"""
        job_spec = self._dict_to_job_spec(job_spec_data)
        return self.prepare_inputs(job_spec)

    def generate_approval_summary_method(self, job_specs_data: List[Dict[str, Any]]) -> str:
        """Generate human-readable summary for approval"""
        job_specs = [self._dict_to_job_spec(job) for job in job_specs_data]
        return self.generate_approval_summary(job_specs)

    def _job_spec_to_dict(self, job_spec: JobSpec) -> Dict[str, Any]:
        """Convert JobSpec to dictionary"""
        return {
            "case_id": job_spec.case_id,
            "system": job_spec.system,
            "params": job_spec.params,
            "hpc": job_spec.hpc,
            "paths": job_spec.paths
        }

    def _dict_to_job_spec(self, data: Dict[str, Any]) -> JobSpec:
        """Convert dictionary to JobSpec"""
        return JobSpec(
            case_id=data["case_id"],
            system=data["system"],
            params=data["params"],
            hpc=data["hpc"],
            paths=data["paths"]
        )

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    def _hash_file(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file"""
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()

    def plan_jobs(self, instruction: str) -> List[JobSpec]:
        """Parse natural language instruction into job specifications using AI"""
        # Use Kimi AI to understand the instruction and generate job specifications
        ai_analysis = self._analyze_with_ai(instruction)

        base_params = self.config["defaults"]["incar"].copy()
        jobs = []

        # Parse AI analysis and generate job specifications
        if ai_analysis.get("material") and ai_analysis.get("calculations"):
            jobs.extend(self._create_jobs_from_ai_analysis(ai_analysis, base_params))
        else:
            # Fallback to rule-based parsing
            jobs.extend(self._fallback_parse(instruction, base_params))

        return jobs

    def _analyze_with_ai(self, instruction: str) -> Dict[str, Any]:
        """Use Kimi AI to analyze the user's instruction with conversation support"""

        try:
            # 使用配置文件中的分析提示词
            system_prompt = self.conversation_manager.config["vasp_analysis_prompt"]

            # 使用对话管理器进行API调用
            result = self.conversation_manager.chat(
                input_text=f"请解析这个VASP计算需求：{instruction}",
                system_prompt=system_prompt,
                temperature=0.3
            )

            if result["status"] == "success":
                response_text = result["response"]
                print(f"✅ AI分析完成 (耗时: {result['response_time']:.2f}s)")

                # Extract JSON from the response
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                else:
                    print("⚠️ AI回复中未找到JSON格式，使用回退方案")
                    return {}
            else:
                print(f"❌ AI分析失败: {result.get('error', '未知错误')}")
                return {}

        except Exception as e:
            print(f"AI解析失败，使用回退方案: {e}")
            return {}

    def _create_jobs_from_ai_analysis(self, analysis: Dict[str, Any], base_params: Dict[str, Any]) -> List[JobSpec]:
        """Create job specifications from AI analysis - rely entirely on LLM intelligence"""
        jobs = []
        material = analysis.get("material", "Unknown")
        calculations = analysis.get("calculations", [])

        for calc in calculations:
            calc_type = calc.get("type", "scf")
            case_id = f"{material}_{calc_type}"

            # 完全依赖LLM提供的参数，不使用任何预设值
            job_spec = JobSpec(
                case_id=case_id,
                system=material,
                params={
                    "incar": {
                        **base_params,
                        **calc.get("parameters", {})
                    },
                    # LLM应该提供完整的kpoints设置
                    "kpoints": calc.get("kpoints", {"mode": "Monkhorst-Pack", "grid": [6, 6, 6]}),
                    # LLM应该指定结构文件路径
                    "poscar_path": calc.get("poscar_path", f"templates/structures/{material}_POSCAR.txt"),
                    # LLM应该提供正确的元素列表
                    "potcar_symbols": calc.get("potcar_symbols", [material])
                },
                hpc=self.config["hpc"],
                paths={
                    "local_dir": str(self.local_workspace / case_id),
                    "remote_dir": f"{self.config['paths']['remote_root']}/{case_id}"
                }
            )
            jobs.append(job_spec)

        return jobs

    def _fallback_parse(self, instruction: str, base_params: Dict[str, Any]) -> List[JobSpec]:
        """No fallback parsing - rely entirely on LLM intelligence"""
        # 系统完全依赖LLM解析，不提供硬编码的回退方案
        # 如果LLM解析失败，返回空列表并提示用户
        print("⚠️ LLM解析未能生成有效的计算计划")
        print("💡 请尝试更详细地描述您的计算需求，例如：")
        print("   - 材料名称和结构")
        print("   - 计算类型（几何优化、自洽场、能带结构等）")
        print("   - 关键参数（截断能、k点密度、收敛标准等）")
        return []

    # 移除硬编码的k点网格生成方法
    # 所有k点设置应该由LLM根据计算需求智能生成

    def prepare_inputs(self, job_spec: JobSpec) -> Dict[str, str]:
        """Prepare VASP input files from job specification"""
        case_dir = Path(job_spec.paths["local_dir"])
        case_dir.mkdir(parents=True, exist_ok=True)

        # Generate INCAR
        incar_content = self._generate_incar(job_spec.params["incar"])
        incar_path = case_dir / "INCAR"
        with open(incar_path, 'w') as f:
            f.write(incar_content)

        # Generate KPOINTS
        kpoints_content = self._generate_kpoints(job_spec.params["kpoints"])
        kpoints_path = case_dir / "KPOINTS"
        with open(kpoints_path, 'w') as f:
            f.write(kpoints_content)

        # Generate Slurm script
        slurm_content = self._generate_slurm_script(job_spec)
        slurm_path = case_dir / "run.slurm"
        with open(slurm_path, 'w') as f:
            f.write(slurm_content)

        # Calculate hashes
        hashes = {
            "INCAR": self._hash_file(incar_path),
            "KPOINTS": self._hash_file(kpoints_path),
            "run.slurm": self._hash_file(slurm_path)
        }

        # Save hashes.json
        hashes_path = case_dir / "hashes.json"
        with open(hashes_path, 'w') as f:
            json.dump(hashes, f, indent=2)

        return hashes

    def _generate_incar(self, incar_params: Dict[str, Any]) -> str:
        """Generate INCAR file content"""
        lines = ["VASP INCAR file", "=" * 20]
        for key, value in incar_params.items():
            lines.append(f"{key} = {value}")
        return "\n".join(lines) + "\n"

    def _generate_kpoints(self, kpoints_params: Dict[str, Any]) -> str:
        """Generate KPOINTS file content from LLM-optimized parameters"""
        # 完全依赖LLM生成的kpoints参数，不提供任何硬编码内容

        if "content" in kpoints_params:
            # 如果LLM直接提供了完整的KPOINTS内容
            return kpoints_params["content"]

        # 基于LLM提供的参数生成标准格式
        mode = kpoints_params.get("mode", "Monkhorst-Pack")

        if mode == "Gamma" and "grid" in kpoints_params:
            grid = kpoints_params["grid"]
            return f"""Automatic mesh
0
Gamma
{grid[0]} {grid[1]} {grid[2]} 0 0 0
"""
        elif mode == "Monkhorst-Pack" and "grid" in kpoints_params:
            grid = kpoints_params["grid"]
            return f"""Automatic mesh
0
Monkhorst-Pack
{grid[0]} {grid[1]} {grid[2]} 0 0 0
"""
        elif mode == "Line-mode":
            # 对于能带结构计算，LLM应该提供具体的k点路径
            if "path" in kpoints_params:
                return kpoints_params["path"]
            else:
                return """Line-mode KPOINTS file (content should be provided by LLM)
40
Reciprocal
# K-point path should be generated by LLM based on material structure
"""
        else:
            # 简单的默认格式，实际参数应由LLM提供
            return """KPOINTS file generated from LLM parameters
# All k-point settings should be intelligently generated by LLM
"""

    def _generate_slurm_script(self, job_spec: JobSpec) -> str:
        """Generate Slurm batch script"""
        hpc = job_spec.hpc
        case_id = job_spec.case_id
        vasp_module = self.config["env"]["vasp_module"]
        vasp_exec = self.config["env"]["vasp_exec"]
        potcar_root = self.config["env"]["potcar_root"]

        script = f"""#!/bin/bash
#SBATCH -p {hpc['partition']}
#SBATCH -N {hpc['nodes']}
#SBATCH --ntasks-per-node={hpc['ntasks_per_node']}
#SBATCH -J {case_id}
#SBATCH -o vasp.out
#SBATCH -t {hpc['walltime_minutes']}:00:00

export OMP_NUM_THREADS=1
module load {vasp_module}
module list -t &> module_snapshot.txt

export VASP_PP_PATH={potcar_root}

# Build POTCAR for {case_id}
# POTCAR will be built based on the specific elements in the calculation
# Example for SiC: cat $VASP_PP_PATH/Si/POTCAR $VASP_PP_PATH/C/POTCAR > POTCAR

mpirun -np $SLURM_NTASKS {vasp_exec}
"""
        return script

    def generate_approval_summary(self, job_specs: List[JobSpec]) -> str:
        """Generate human-readable approval summary"""
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


def create_vasp_agent():
    """Create and configure the VASP orchestrator agent"""

    orchestrator = VASPOrchestrator()

    # Define agent system prompt
    system_prompt = "你是一个南开大学vasp助手"



if __name__ == "__main__":
    # Example usage
    agent = create_vasp_agent()
    print("VASP-HPC Orchestrator Agent initialized")
    print("Ready to process VASP calculation requests...")