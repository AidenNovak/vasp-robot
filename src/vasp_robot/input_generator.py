"""
简化的VASP输入文件生成器
Simplified VASP Input File Generator

统一处理所有VASP输入文件的生成，减少重复代码
"""

from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
import json


@dataclass
class VASPInputSpec:
    """VASP输入文件规范"""
    incar: Dict[str, Any]
    kpoints: Dict[str, Any]
    poscar_source: Optional[str] = None
    potcar_symbols: Optional[list] = None


class VASPInputGenerator:
    """VASP输入文件生成器 - 简化版"""

    def __init__(self, default_incar: Optional[Dict[str, Any]] = None):
        """初始化生成器"""
        self.default_incar = default_incar or {}

    def generate_all_inputs(self, spec: VASPInputSpec, output_dir: Path) -> Dict[str, Path]:
        """
        生成所有VASP输入文件

        Args:
            spec: VASP输入规范
            output_dir: 输出目录

        Returns:
            生成的文件路径字典
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        generated_files = {}

        # 生成INCAR
        incar_path = output_dir / "INCAR"
        incar_path.write_text(self._generate_incar(spec.incar))
        generated_files["INCAR"] = incar_path

        # 生成KPOINTS
        kpoints_path = output_dir / "KPOINTS"
        kpoints_path.write_text(self._generate_kpoints(spec.kpoints))
        generated_files["KPOINTS"] = kpoints_path

        # 保存输入规范
        spec_path = output_dir / "input_spec.json"
        spec_path.write_text(json.dumps(spec.__dict__, indent=2))
        generated_files["input_spec.json"] = spec_path

        return generated_files

    def _generate_incar(self, incar_params: Dict[str, Any]) -> str:
        """生成INCAR文件内容"""
        # 合并默认参数
        merged_params = {**self.default_incar, **incar_params}

        lines = ["VASP INCAR file", "=" * 20]

        # 按重要性排序的参数
        priority_order = [
            "SYSTEM", "ENCUT", "EDIFF", "EDIFFG", "ISMEAR", "SIGMA",
            "IBRION", "NSW", "ISIF", "NELM", "NELMIN", "ALGO",
            "LCHARG", "LWAVE", "PREC"
        ]

        # 添加优先参数
        for key in priority_order:
            if key in merged_params:
                lines.append(f"{key} = {merged_params[key]}")

        # 添加其他参数
        for key, value in merged_params.items():
            if key not in priority_order:
                lines.append(f"{key} = {value}")

        return "\n".join(lines) + "\n"

    def _generate_kpoints(self, kpoints_params: Dict[str, Any]) -> str:
        """生成KPOINTS文件内容"""
        # 如果直接提供了内容
        if "content" in kpoints_params:
            return kpoints_params["content"]

        mode = kpoints_params.get("mode", "Monkhorst-Pack")
        grid = kpoints_params.get("grid", [6, 6, 6])

        if mode == "Line-mode":
            # 对于能带计算，需要提供路径
            return self._generate_kpoints_path(kpoints_params)

        # 自动网格模式
        return f"""Automatic mesh
0
{mode}
{grid[0]} {grid[1]} {grid[2]} 0 0 0
"""

    def _generate_kpoints_path(self, kpoints_params: Dict[str, Any]) -> str:
        """生成K点路径（用于能带计算）"""
        default_path = """Line-mode
40
Reciprocal
# K-point path should be provided based on material structure
"""
        return kpoints_params.get("path", default_path)

    def create_job_specification(
        self,
        material: str,
        calc_type: str,
        incar_overrides: Optional[Dict[str, Any]] = None,
        kpoints_override: Optional[Dict[str, Any]] = None
    ) -> VASPInputSpec:
        """
        创建作业规范

        Args:
            material: 材料名称
            calc_type: 计算类型 (scf, relax, band, dos)
            incar_overrides: INCAR参数覆盖
            kpoints_override: KPOINTS参数覆盖

        Returns:
            VASP输入规范
        """
        # 基础INCAR设置
        base_incar = {
            "SYSTEM": f"{material} - {calc_type}",
            "ENCUT": 520,
            "EDIFF": 1E-6,
            "ISMEAR": 0,
            "SIGMA": 0.05,
            "LCHARG": False,
            "LWAVE": False
        }

        # 根据计算类型调整参数
        if calc_type == "relax":
            base_incar.update({
                "IBRION": 2,
                "NSW": 100,
                "EDIFFG": -0.01,
                "ISIF": 3
            })
        elif calc_type == "scf":
            base_incar.update({
                "IBRION": -1,
                "NSW": 0,
                "NELM": 100
            })
        elif calc_type == "band":
            base_incar.update({
                "IBRION": -1,
                "NSW": 0,
                "ICHARG": 11
            })
        elif calc_type == "dos":
            base_incar.update({
                "IBRION": -1,
                "NSW": 0,
                "ISMEAR": -5,
                "SIGMA": 0.05,
                "NEDOS": 2000
            })

        # 应用覆盖参数
        if incar_overrides:
            base_incar.update(incar_overrides)

        # KPOINTS设置
        base_kpoints = {
            "mode": "Monkhorst-Pack",
            "grid": [6, 6, 6]
        }

        if calc_type in ["band", "dos"]:
            # 能带和DOS需要更密的k点
            base_kpoints["grid"] = [12, 12, 12]

        if calc_type == "band":
            base_kpoints = {
                "mode": "Line-mode",
                "path": None  # 需要根据结构生成
            }

        # 应用KPOINTS覆盖
        if kpoints_override:
            base_kpoints.update(kpoints_override)

        return VASPInputSpec(
            incar=base_incar,
            kpoints=base_kpoints,
            poscar_source=f"structures/{material}_POSCAR",
            potcar_symbols=[material]
        )