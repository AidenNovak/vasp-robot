#!/usr/bin/env python3
"""
VASP简化工作流程示例
Simplified VASP Workflow Example

展示如何使用简化后的VASP Robot模块
"""

import asyncio
from pathlib import Path
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vasp_robot.workflow_simple import run_vasp_calculation
from vasp_robot.config_manager import get_config, get_hpc_config
from vasp_robot.errors import handle_errors, ErrorCategory, ConfigError


async def main():
    """主函数示例"""
    print("🚀 VASP简化工作流程示例")
    print("=" * 50)

    # 1. 简单的SCF计算
    print("\n1️⃣ 运行简单的SCF计算")
    result = await run_vasp_calculation(
        user_input="计算SiC的自洽场能量",
        material="SiC",
        calc_type="scf",
        submit_to_hpc=False
    )

    if result.status == "success":
        print(f"✅ 作业创建成功: {result.job_id}")
        print(f"📁 本地目录: {result.local_dir}")
        print(f"📄 生成文件: {', '.join(result.files_created)}")
    else:
        print(f"❌ 失败: {result.message}")

    # 2. 带自定义参数的结构优化
    print("\n2️⃣ 带自定义参数的结构优化")
    custom_params = {
        "incar": {
            "ENCUT": 600,
            "EDIFFG": -0.005,
            "NSW": 200
        },
        "kpoints": {
            "grid": [8, 8, 8]
        }
    }

    result = await run_vasp_calculation(
        user_input="优化石墨烯的几何结构",
        material="graphene",
        calc_type="relax",
        submit_to_hpc=False,
        custom_params=custom_params
    )

    if result.status == "success":
        print(f"✅ 作业创建成功: {result.job_id}")

    # 3. 提交到HPC（如果配置了）
    print("\n3️⃣ 提交到HPC计算")
    try:
        hpc_config = get_hpc_config()
        print(f"HPC主机: {hpc_config.host}@{hpc_config.user}")

        result = await run_vasp_calculation(
            user_input="计算MoS2的能带结构",
            material="MoS2",
            calc_type="band",
            submit_to_hpc=True
        )

        if result.status == "success" and result.hpc_job:
            print(f"✅ HPC作业提交成功 (ID: {result.hpc_job.job_id})")
        else:
            print("⚠️ 未提交到HPC")

    except Exception as e:
        print(f"⚠️ HPC配置或提交失败: {e}")

    print("\n" + "=" * 50)
    print("✨ 示例完成")


@handle_errors(category=ErrorCategory.CONFIG, reraise=False)
def check_configuration():
    """检查配置示例"""
    print("\n🔍 检查配置...")

    # 检查基本配置
    incar_defaults = get_config("base.defaults.incar", {})
    if incar_defaults:
        print(f"✅ 找到INCAR默认参数: {list(incar_defaults.keys())[:3]}...")
    else:
        print("⚠️ 未找到INCAR默认参数")

    # 检查HPC配置
    try:
        hpc_config = get_hpc_config()
        print(f"✅ HPC配置: {hpc_config.host}:{hpc_config.port}")
    except ConfigError as e:
        print(f"⚠️ HPC配置错误: {e}")

    # 检查API配置
    from vasp_robot.config_manager import get_api_config
    api_config = get_api_config("kimi")
    if api_config:
        print("✅ Kimi API配置已找到")
    else:
        print("⚠️ 未找到Kimi API配置")


def demo_error_handling():
    """错误处理示例"""
    print("\n🛡️ 错误处理示例")

    from vasp_robot.errors import (
        ValidationError,
        validate_input,
        handle_errors,
        safe_execute
    )

    # 输入验证示例
    @validate_input({
        "material": {"type": str, "choices": ["SiC", "Graphene", "MoS2"]},
        "encut": {"type": int, "validator": lambda x: x > 0}
    })
    def validate_calculation(material: str, encut: int = 520):
        print(f"✅ 验证通过: {material}, ENCUT={encut}")

    # 测试验证
    try:
        validate_calculation(material="SiC", encut=520)
        validate_calculation(material="Invalid", encut=520)  # 会失败
    except ValidationError as e:
        print(f"❌ 验证失败: {e}")

    # 安全执行示例
    def risky_operation():
        raise ValueError("模拟错误")

    result = safe_execute(risky_operation, default="安全值")
    print(f"安全执行结果: {result}")


if __name__ == "__main__":
    # 检查配置
    check_configuration()

    # 错误处理示例
    demo_error_handling()

    # 运行主工作流程
    asyncio.run(main())