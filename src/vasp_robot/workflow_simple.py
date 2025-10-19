"""
简化的工作流程编排器
Simplified Workflow Orchestrator

减少复杂性，提供清晰的VASP计算工作流程
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

from .input_generator import VASPInputGenerator, VASPInputSpec
from .hpc_simple import VASPHPCManager, HPCJob
from .config_manager import get_config_manager, get_api_config
from .conversation import ConversationManager


@dataclass
class WorkflowRequest:
    """工作流程请求"""
    user_input: str
    material: str = ""
    calculation_type: str = "scf"
    submit_to_hpc: bool = False
    custom_params: Optional[Dict[str, Any]] = None


@dataclass
class WorkflowResult:
    """工作流程结果"""
    status: str  # success, error
    job_id: str
    message: str
    local_dir: str
    hpc_job: Optional[HPCJob] = None
    files_created: List[str] = None
    next_steps: List[str] = None

    def __post_init__(self):
        if self.files_created is None:
            self.files_created = []
        if self.next_steps is None:
            self.next_steps = []


class SimpleVASPWorkflow:
    """简化的VASP工作流程"""

    def __init__(self, workspace_dir: str = "vasp_jobs"):
        """初始化工作流程"""
        self.workspace = Path(workspace_dir)
        self.workspace.mkdir(exist_ok=True)

        # 初始化组件
        self.config_manager = get_config_manager()
        self.input_generator = VASPInputGenerator(
            default_incar=self.config_manager.get_incar_defaults()
        )

        # 初始化对话管理器
        api_config = get_api_config("kimi")
        if api_config:
            self.conversation_manager = ConversationManager(
                settings=None,
                secrets_path="config/secrets.yaml"
            )
        else:
            self.conversation_manager = None

        # HPC管理器（按需初始化）
        self.hpc_manager: Optional[VASPHPCManager] = None

    async def run(self, request: WorkflowRequest) -> WorkflowResult:
        """
        运行VASP工作流程

        Args:
            request: 工作流程请求

        Returns:
            工作流程结果
        """
        try:
            # 1. 解析请求
            if not request.material or not request.calculation_type:
                parsed = await self._parse_request(request.user_input)
                request.material = parsed.get("material", request.material)
                request.calculation_type = parsed.get("calculation_type", request.calculation_type)

            # 2. 生成作业ID
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            job_id = f"{request.material}_{request.calculation_type}_{timestamp}"

            # 3. 准备本地工作目录
            job_dir = self.workspace / job_id
            print(f"📁 创建作业目录: {job_dir}")

            # 4. 生成VASP输入
            input_spec = self._create_input_spec(request)
            files = self.input_generator.generate_all_inputs(input_spec, job_dir)

            # 5. 提交到HPC（如果需要）
            hpc_job = None
            if request.submit_to_hpc:
                hpc_job = await self._submit_to_hpc(job_dir, job_id)

            # 6. 创建结果
            result = WorkflowResult(
                status="success",
                job_id=job_id,
                message="VASP作业准备完成",
                local_dir=str(job_dir),
                hpc_job=hpc_job,
                files_created=list(files.keys()),
                next_steps=self._get_next_steps(request.submit_to_hpc, job_id, hpc_job)
            )

            print(f"✅ 工作流程完成: {job_id}")
            return result

        except Exception as e:
            return WorkflowResult(
                status="error",
                job_id="",
                message=f"工作流程失败: {str(e)}",
                local_dir=""
            )

    async def _parse_request(self, user_input: str) -> Dict[str, str]:
        """解析用户输入"""
        # 如果没有对话管理器，使用简单解析
        if not self.conversation_manager:
            return self._simple_parse(user_input)

        # 使用AI解析
        prompt = f"""
请解析以下VASP计算需求，提取关键信息：

用户需求: {user_input}

请返回JSON格式：
{{
    "material": "材料名称或化学式",
    "calculation_type": "计算类型(scf/relax/band/dos)",
    "parameters": {{
        "encut": "截断能(eV)",
        "kpoints": "k点网格"
    }}
}}
"""

        try:
            result = self.conversation_manager.chat(
                input_text=prompt,
                system_prompt="你是VASP专家，擅长解析计算需求",
                temperature=0.3
            )

            if result["status"] == "success":
                # 提取JSON
                import re
                json_match = re.search(r'\{.*\}', result["response"], re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())

        except Exception as e:
            print(f"⚠️ AI解析失败: {e}")

        # 回退到简单解析
        return self._simple_parse(user_input)

    def _simple_parse(self, user_input: str) -> Dict[str, str]:
        """简单的规则解析"""
        user_input = user_input.lower()

        # 检测材料
        materials = ["sic", "graphene", "mos2", "bn", "graphite", "diamond"]
        material = "unknown"
        for m in materials:
            if m in user_input:
                material = m
                break

        # 检测计算类型
        calc_type = "scf"
        if any(word in user_input for word in ["optimize", "relax", "relaxation"]):
            calc_type = "relax"
        elif any(word in user_input for word in ["band", "bandstructure"]):
            calc_type = "band"
        elif any(word in user_input for word in ["dos", "density"]):
            calc_type = "dos"

        return {
            "material": material,
            "calculation_type": calc_type
        }

    def _create_input_spec(self, request: WorkflowRequest) -> VASPInputSpec:
        """创建输入规范"""
        # 使用输入生成器创建规范
        spec = self.input_generator.create_job_specification(
            material=request.material,
            calc_type=request.calculation_type,
            incar_overrides=request.custom_params.get("incar") if request.custom_params else None,
            kpoints_override=request.custom_params.get("kpoints") if request.custom_params else None
        )

        return spec

    async def _submit_to_hpc(self, job_dir: Path, job_id: str) -> Optional[HPCJob]:
        """提交到HPC"""
        if not self.hpc_manager:
            hpc_config = self.config_manager.get_hpc_config()
            self.hpc_manager = VASPHPCManager(
                connection=hpc_config,
                work_dir=hpc_config.work_dir
            )

        return self.hpc_manager.prepare_and_submit(job_dir, job_id)

    def _get_next_steps(self, submitted: bool, job_id: str, hpc_job: Optional[HPCJob]) -> List[str]:
        """获取下一步操作"""
        if submitted and hpc_job:
            return [
                f"监控HPC作业状态 (ID: {hpc_job.job_id})",
                "等待计算完成",
                "下载计算结果",
                "分析输出数据"
            ]
        else:
            return [
                "检查生成的VASP输入文件",
                "确认计算参数设置",
                "手动提交到HPC或本地运行",
                f"使用命令: cd {self.workspace}/{job_id} && vasp_std"
            ]


# 便捷函数
async def run_vasp_calculation(
    user_input: str,
    material: str = "",
    calc_type: str = "scf",
    submit_to_hpc: bool = False,
    custom_params: Optional[Dict[str, Any]] = None
) -> WorkflowResult:
    """
    运行VASP计算的便捷函数

    Args:
        user_input: 用户输入描述
        material: 材料名称
        calc_type: 计算类型
        submit_to_hpc: 是否提交到HPC
        custom_params: 自定义参数

    Returns:
        工作流程结果
    """
    workflow = SimpleVASPWorkflow()

    request = WorkflowRequest(
        user_input=user_input,
        material=material,
        calculation_type=calc_type,
        submit_to_hpc=submit_to_hpc,
        custom_params=custom_params
    )

    return await workflow.run(request)