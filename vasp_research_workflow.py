#!/usr/bin/env python3
"""
VASP科研计算工作流程脚本
VASP Scientific Computing Workflow Script
用于连接Claude Code、Kimi LLM和HPC的完整科研计算流水线
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
import yaml
from dotenv import load_dotenv

# 添加src目录到Python路径
sys.path.append('src')

from vasp_orchestrator import create_vasp_agent
from src.conversation_manager import ConversationManager
from src.hpc_automation import HPCAutomation


@dataclass
class ResearchRequest:
    """科研需求标准格式"""
    scientific_problem: str
    material_system: str
    properties_of_interest: str
    calculation_goals: str
    constraints: Optional[str] = None
    user_request: Optional[str] = None  # 原始用户请求


@dataclass
class VASPJobSpec:
    """VASP作业标准格式"""
    job_id: str
    analysis_summary: str
    calculation_plan: str
    vasp_parameters: Dict[str, Any]
    hpc_requirements: Dict[str, Any]
    estimated_runtime: str
    success_criteria: str
    incar_content: str
    kpoints_content: str
    poscar_source: str
    potcar_sequence: list
    slurm_script: str


class VASPResearchWorkflow:
    """VASP科研计算工作流程管理器"""

    def __init__(self, config_path: str = "config/workflow_config.yaml"):
        self.config = self._load_config(config_path)
        self.workflow_dir = Path("vasp_workflow_jobs")
        self.workflow_dir.mkdir(exist_ok=True)

        # 初始化代理
        self.vasp_agent = create_vasp_agent()
        self.conversation_manager = ConversationManager("config/system_prompts.yaml")

        # 初始化HPC自动化
        self.hpc_automation = HPCAutomation(config_path)

        # 工作流程状态
        self.current_job = None
        self.workflow_log = []

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """加载工作流程配置"""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    def _log_workflow(self, step: str, message: str, data: Any = None):
        """记录工作流程日志"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "step": step,
            "message": message,
            "data": data
        }
        self.workflow_log.append(log_entry)
        print(f"🔄 [{step}] {message}")

    def _save_workflow_log(self, job_id: str):
        """保存工作流程日志"""
        log_file = self.workflow_dir / f"{job_id}_workflow.json"
        with open(log_file, 'w') as f:
            json.dump(self.workflow_log, f, indent=2)

    async def step1_analyze_research_request(self, user_request: str) -> ResearchRequest:
        """步骤1: 分析科研需求"""
        self._log_workflow("step1", "开始分析科研需求", {"user_request": user_request})

        # 使用Kimi分析科研需求，生成标准格式
        analysis_prompt = f"""
请分析以下科研需求，提取关键信息并按标准格式返回：

用户需求: {user_request}

请返回JSON格式的分析结果，包含以下字段：
- scientific_problem: 科学问题的具体描述
- material_system: 材料体系（如SiC、石墨烯等）
- properties_of_interest: 关注的性质（如能带结构、力学性质等）
- calculation_goals: 计算目标（如几何优化、电子结构计算等）
- constraints: 约束条件（如计算资源限制、精度要求等）
- analysis_brief: 简要分析（50字以内）

确保分析准确，为后续VASP计算提供清晰的指导。
"""

        try:
            result = self.conversation_manager.chat(
                input_text=analysis_prompt,
                system_prompt="你是材料科学专家，擅长分析科研需求并制定计算方案。",
                temperature=0.3
            )

            if result["status"] == "success":
                # 提取JSON响应
                import re
                json_match = re.search(r'\{.*\}', result["response"], re.DOTALL)
                if json_match:
                    try:
                        analysis_data = json.loads(json_match.group())
                    except json.JSONDecodeError as e:
                        print(f"⚠️ JSON解析错误: {e}")
                        print(f"原始响应: {result['response']}")
                        # 尝试修复常见的JSON问题
                        json_str = json_match.group()
                        json_str = json_str.replace('\n', '\\n').replace('\r', '\\r')
                        analysis_data = json.loads(json_str)

                    research_request = ResearchRequest(
                        scientific_problem=analysis_data.get("scientific_problem", ""),
                        material_system=analysis_data.get("material_system", ""),
                        properties_of_interest=analysis_data.get("properties_of_interest", ""),
                        calculation_goals=analysis_data.get("calculation_goals", ""),
                        constraints=analysis_data.get("constraints"),
                        user_request=user_request
                    )

                    self._log_workflow("step1", "科研需求分析完成", analysis_data)
                    return research_request
                else:
                    raise ValueError("AI响应中未找到有效JSON")
            else:
                raise RuntimeError(f"AI分析失败: {result.get('error')}")

        except Exception as e:
            self._log_workflow("step1", f"科研需求分析失败: {e}")
            raise

    async def step2_generate_vasp_plan(self, research_request: ResearchRequest) -> VASPJobSpec:
        """步骤2: 生成VASP计算方案"""
        self._log_workflow("step2", "开始生成VASP计算方案")

        # 构建详细的VASP计算提示
        vasp_prompt = f"""
基于以下科研需求，请生成完整的VASP计算方案：

科研问题: {research_request.scientific_problem}
材料体系: {research_request.material_system}
关注性质: {research_request.properties_of_interest}
计算目标: {research_request.calculation_goals}
约束条件: {research_request.constraints or "无"}

请生成JSON格式的VASP计算方案，包含：

1. analysis_summary: 计算方案概述（100字以内）
2. calculation_plan: 详细的计算步骤和逻辑
3. vasp_parameters:
   - incar: 完整的INCAR参数设置
   - kpoints: K点设置方案
   - poscar_source: POSCAR文件来源说明
   - potcar_sequence: POTCAR元素顺序

4. hpc_requirements:
   - nodes: 节点数
   - ntasks_per_node: 每节点任务数
   - walltime: 预估计算时间
   - partition: 计算分区

5. estimated_runtime: 总预估运行时间
6. success_criteria: 计算成功的判断标准

要求：
- 参数设置要科学合理，符合材料计算最佳实践
- 考虑HPC资源效率
- 确保计算收敛性和精度
- 提供完整的技术参数

请确保输出是有效的JSON格式。
"""

        try:
            result = self.conversation_manager.chat(
                input_text=vasp_prompt,
                system_prompt="你是VASP计算专家，请生成专业、完整的VASP计算方案。",
                temperature=0.2
            )

            if result["status"] == "success":
                # 提取JSON响应
                import re
                json_match = re.search(r'\{.*\}', result["response"], re.DOTALL)
                if json_match:
                    try:
                        vasp_data = json.loads(json_match.group())
                    except json.JSONDecodeError as e:
                        print(f"⚠️ JSON解析错误: {e}")
                        print(f"原始响应片段: {result['response'][:500]}...")
                        # 尝试修复常见的JSON问题
                        json_str = json_match.group()
                        json_str = json_str.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
                        vasp_data = json.loads(json_str)

                    # 生成唯一的作业ID
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    job_id = f"{research_request.material_system}_{timestamp}"

                    # 创建VASP作业规范
                    job_spec = VASPJobSpec(
                        job_id=job_id,
                        analysis_summary=vasp_data.get("analysis_summary", ""),
                        calculation_plan=vasp_data.get("calculation_plan", ""),
                        vasp_parameters=vasp_data.get("vasp_parameters", {}),
                        hpc_requirements=vasp_data.get("hpc_requirements", {}),
                        estimated_runtime=vasp_data.get("estimated_runtime", ""),
                        success_criteria=vasp_data.get("success_criteria", ""),
                        incar_content=self._generate_incar_content(vasp_data.get("vasp_parameters", {}).get("incar", {})),
                        kpoints_content=self._generate_kpoints_content(vasp_data.get("vasp_parameters", {}).get("kpoints", {})),
                        poscar_source=vasp_data.get("vasp_parameters", {}).get("poscar_source", ""),
                        potcar_sequence=vasp_data.get("vasp_parameters", {}).get("potcar_sequence", []),
                        slurm_script=self._generate_slurm_content(job_id, vasp_data.get("hpc_requirements", {}))
                    )

                    self.current_job = job_spec
                    self._log_workflow("step2", "VASP计算方案生成完成", {"job_id": job_id})
                    return job_spec
                else:
                    raise ValueError("AI响应中未找到有效JSON")
            else:
                raise RuntimeError(f"VASP方案生成失败: {result.get('error')}")

        except Exception as e:
            self._log_workflow("step2", f"VASP计算方案生成失败: {e}")
            raise

    def _generate_incar_content(self, incar_params: Dict[str, Any]) -> str:
        """生成INCAR文件内容"""
        lines = ["VASP INCAR file", "=" * 20]
        for key, value in incar_params.items():
            lines.append(f"{key} = {value}")
        return "\n".join(lines) + "\n"

    def _generate_kpoints_content(self, kpoints_params: Dict[str, Any]) -> str:
        """生成KPOINTS文件内容"""
        if "content" in kpoints_params:
            return kpoints_params["content"]

        mode = kpoints_params.get("mode", "Monkhorst-Pack")
        if "grid" in kpoints_params:
            grid = kpoints_params["grid"]
            return f"""Automatic mesh
0
{mode}
{grid[0]} {grid[1]} {grid[2]} 0 0 0
"""
        else:
            return "KPOINTS file (content should be provided by AI)"

    def _generate_slurm_content(self, job_id: str, hpc_params: Dict[str, Any]) -> str:
        """生成Slurm脚本内容"""
        default_hpc = self.config["hpc_environment"]["default_resources"]

        nodes = hpc_params.get("nodes", default_hpc["nodes"])
        ntasks = hpc_params.get("ntasks_per_node", default_hpc["ntasks_per_node"])
        walltime = hpc_params.get("walltime", default_hpc["walltime"])
        partition = hpc_params.get("partition", default_hpc["partition"])

        return f"""#!/bin/bash
#SBATCH -p {partition}
#SBATCH -N {nodes}
#SBATCH --ntasks-per-node={ntasks}
#SBATCH -J {job_id}
#SBATCH -o vasp.out
#SBATCH -t {walltime}

module load {self.config["hpc_environment"]["vasp_module"]["name"]}
export VASP_PP_PATH={self.config["hpc_environment"]["vasp_module"]["potcar_path"]}

echo "Starting VASP calculation for {job_id}"
echo "Start time: $(date)"
echo "Job ID: $SLURM_JOB_ID"
echo "Nodes: $SLURM_JOB_NUM_NODES"
echo "Tasks: $SLURM_NTASKS"

# Build POTCAR (example - should be customized based on elements)
# cat $VASP_PP_PATH/*/POTCAR > POTCAR

mpirun -np $SLURM_NTASKS {self.config["hpc_environment"]["vasp_module"]["executable"]}

echo "VASP calculation completed"
echo "End time: $(date)"
"""

    def step3_prepare_vasp_files(self, job_spec: VASPJobSpec) -> str:
        """步骤3: 准备VASP输入文件"""
        self._log_workflow("step3", "开始准备VASP输入文件")

        # 创建作业目录
        job_dir = self.workflow_dir / job_spec.job_id
        job_dir.mkdir(exist_ok=True)

        # 生成输入文件
        files_created = {}

        # INCAR
        incar_path = job_dir / "INCAR"
        with open(incar_path, 'w') as f:
            f.write(job_spec.incar_content)
        files_created["INCAR"] = str(incar_path)

        # KPOINTS
        kpoints_path = job_dir / "KPOINTS"
        with open(kpoints_path, 'w') as f:
            f.write(job_spec.kpoints_content)
        files_created["KPOINTS"] = str(kpoints_path)

        # Slurm脚本
        slurm_path = job_dir / "run.slurm"
        with open(slurm_path, 'w') as f:
            f.write(job_spec.slurm_script)
        files_created["run.slurm"] = str(slurm_path)

        # 保存作业规范
        job_spec_path = job_dir / "job_specification.json"
        with open(job_spec_path, 'w') as f:
            json.dump(job_spec.__dict__, f, indent=2, default=str)
        files_created["job_specification"] = str(job_spec_path)

        self._log_workflow("step3", "VASP输入文件准备完成", files_created)
        return str(job_dir)

    def step4_test_hpc_connection(self) -> bool:
        """步骤4: 测试HPC连接"""
        self._log_workflow("step4", "测试HPC连接")

        success = self.hpc_automation.test_hpc_connection()
        if success:
            self._log_workflow("step4", "HPC连接测试成功")
        else:
            self._log_workflow("step4", "HPC连接测试失败")

        return success

    def step5_upload_and_submit(self, job_spec: VASPJobSpec) -> Optional[str]:
        """步骤5: 上传文件并提交作业"""
        self._log_workflow("step5", "开始上传文件并提交HPC作业")

        try:
            # 上传文件
            if not self.hpc_automation.upload_job_files(self.workflow_dir / job_spec.job_id, job_spec.job_id):
                raise Exception("文件上传失败")
            self._log_workflow("step5", "文件上传成功")

            # 提交作业
            slurm_job_id = self.hpc_automation.submit_vasp_job(job_spec.job_id)
            if not slurm_job_id:
                raise Exception("作业提交失败")

            self._log_workflow("step5", f"作业提交成功，Slurm ID: {slurm_job_id}")
            return slurm_job_id

        except Exception as e:
            self._log_workflow("step5", f"HPC作业提交失败: {e}")
            return None

    def step6_monitor_job(self, slurm_job_id: str) -> bool:
        """步骤6: 监控作业执行"""
        self._log_workflow("step6", f"开始监控作业: {slurm_job_id}")

        success = self.hpc_automation.monitor_job(slurm_job_id, check_interval=30, max_wait=300)  # 短时间测试
        if success:
            self._log_workflow("step6", "作业执行成功")
        else:
            self._log_workflow("step6", "作业执行失败或超时")

        return success

    async def run_complete_workflow(self, user_request: str) -> Dict[str, Any]:
        """运行完整的科研计算工作流程"""
        self._log_workflow("workflow_start", "开始VASP科研计算工作流程")

        try:
            # 步骤1: 分析科研需求
            research_request = await self.step1_analyze_research_request(user_request)

            # 步骤2: 生成VASP计算方案
            job_spec = await self.step2_generate_vasp_plan(research_request)

            # 步骤3: 准备VASP文件
            job_dir = self.step3_prepare_vasp_files(job_spec)

            # 步骤4: 测试HPC连接
            hpc_connection_ok = self.step4_test_hpc_connection()
            if not hpc_connection_ok:
                raise Exception("HPC连接失败，无法继续")

            # 步骤5: 上传文件并提交作业
            slurm_job_id = self.step5_upload_and_submit(job_spec)
            if not slurm_job_id:
                raise Exception("HPC作业提交失败")

            # 保存工作流程日志
            self._save_workflow_log(job_spec.job_id)

            result = {
                "status": "success",
                "job_id": job_spec.job_id,
                "slurm_job_id": slurm_job_id,
                "job_directory": job_dir,
                "research_request": research_request.__dict__,
                "job_specification": job_spec.__dict__,
                "hpc_status": "submitted",
                "next_steps": [
                    f"监控作业状态 (Slurm ID: {slurm_job_id})",
                    "等待计算完成",
                    "下载计算结果",
                    "分析计算数据"
                ]
            }

            self._log_workflow("workflow_complete", "工作流程完成，HPC作业已提交")
            return result

        except Exception as e:
            error_result = {
                "status": "error",
                "error": str(e),
                "workflow_log": self.workflow_log
            }
            self._log_workflow("workflow_error", f"工作流程失败: {e}")
            return error_result

    async def run_workflow_without_hpc(self, user_request: str) -> Dict[str, Any]:
        """运行不包含HPC提交的工作流程（仅生成文件）"""
        self._log_workflow("workflow_start", "开始VASP科研计算工作流程（仅生成文件）")

        try:
            # 步骤1: 分析科研需求
            research_request = await self.step1_analyze_research_request(user_request)

            # 步骤2: 生成VASP计算方案
            job_spec = await self.step2_generate_vasp_plan(research_request)

            # 步骤3: 准备VASP文件
            job_dir = self.step3_prepare_vasp_files(job_spec)

            # 保存工作流程日志
            self._save_workflow_log(job_spec.job_id)

            result = {
                "status": "success",
                "job_id": job_spec.job_id,
                "job_directory": job_dir,
                "research_request": research_request.__dict__,
                "job_specification": job_spec.__dict__,
                "next_steps": [
                    "检查生成的VASP输入文件",
                    "确认计算参数设置",
                    "手动准备HPC提交",
                    "使用以下命令提交作业"
                ],
                "manual_submit_commands": [
                    f"python src/hpc_automation.py test",
                    f"python src/hpc_automation.py run {job_spec.job_id}"
                ]
            }

            self._log_workflow("workflow_complete", "文件生成完成，准备手动HPC提交")
            return result

        except Exception as e:
            error_result = {
                "status": "error",
                "error": str(e),
                "workflow_log": self.workflow_log
            }
            self._log_workflow("workflow_error", f"工作流程失败: {e}")
            return error_result


# 命令行接口
async def main():
    """主函数 - 支持命令行调用"""
    if len(sys.argv) < 2:
        print("使用方法: python vasp_research_workflow.py '科研需求描述'")
        print("示例: python vasp_research_workflow.py '研究SiC的能带结构和光学性质'")
        sys.exit(1)

    user_request = " ".join(sys.argv[1:])

    # 确保环境变量已加载
    load_dotenv()

    if not os.getenv("KIMI_API_KEY"):
        print("❌ 错误: KIMI_API_KEY 环境变量未设置")
        sys.exit(1)

    print("🚀 启动VASP科研计算工作流程...")
    print(f"📋 科研需求: {user_request}")
    print("=" * 60)

    workflow = VASPResearchWorkflow()
    result = await workflow.run_complete_workflow(user_request)

    if result["status"] == "success":
        print("\n✅ 工作流程完成!")
        print(f"📁 作业目录: {result['job_directory']}")
        print(f"🆔 作业ID: {result['job_id']}")
        print("\n📋 下一步操作:")
        for i, step in enumerate(result['next_steps'], 1):
            print(f"  {i}. {step}")
    else:
        print(f"\n❌ 工作流程失败: {result['error']}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())