#!/usr/bin/env python3
"""
优化的VASP数据结构类型系统
基于子代理专家建议，提供类型安全的数据结构
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union, Tuple, Literal
from enum import Enum
from pathlib import Path
import re
from datetime import datetime

# =============================================================================
# 枚举类型定义
# =============================================================================

class CalculationType(Enum):
    """VASP计算类型枚举"""
    GEOMETRY_OPTIMIZATION = "geometry_optimization"
    SELF_CONSISTENT_FIELD = "self_consistent_field"
    BAND_STRUCTURE = "band_structure"
    DENSITY_OF_STATES = "density_of_states"
    SURFACE_RELAXATION = "surface_relaxation"
    HYBRID_FUNCTIONAL = "hybrid_functional"

class JobState(Enum):
    """HPC作业状态枚举"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUSPENDED = "SUSPENDED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"
    PREEMPTED = "PREEMPTED"

class SmearingMethod(Enum):
    """Smearing方法枚举"""
    GAUSSIAN = "gaussian"
    FERMI_DIRAC = "fermi-dirac"
    METHFESEL_PAXTON = "methfessel-paxton"
    TETRAHEDRON = "tetrahedron"
    GAUSSIAN_SPLINE = "gaussian-spline"

# =============================================================================
# 值对象 - 不可变的数据容器
# =============================================================================

@dataclass(frozen=True)
class ConvergenceCriteria:
    """收敛标准值对象"""
    energy_threshold: float = field(metadata={"description": "能量收敛阈值 (eV)"})
    force_threshold: float = field(metadata={"description": "力收敛阈值 (eV/Å)"})
    stress_threshold: float = field(metadata={"description": "应力收敛阈值 (kBar)"})
    electronic_steps: int = field(default=200, metadata={"description": "最大电子步数"})
    ionic_steps: int = field(default=100, metadata={"description": "最大离子步数"})

    def __post_init__(self):
        # 验证收敛标准的合理性
        if self.energy_threshold <= 0:
            raise ValueError("能量收敛阈值必须为正数")
        if self.force_threshold <= 0:
            raise ValueError("力收敛阈值必须为正数")
        if self.stress_threshold < 0:
            raise ValueError("应力阈值不能为负数")
        if self.electronic_steps <= 0:
            raise ValueError("电子步数必须为正数")
        if self.ionic_steps <= 0:
            raise ValueError("离子步数必须为正数")

@dataclass(frozen=True)
class KPointsConfig:
    """K点配置值对象"""
    mode: Literal["Monkhorst-Pack", "Gamma", "Line-mode", "Reciprocal"]
    grid: Optional[Tuple[int, int, int]] = None
    shift: Optional[Tuple[float, float, float]] = (0.0, 0.0, 0.0)
    density_factor: float = 1.0

    def __post_init__(self):
        if self.mode in ["Monkhorst-Pack", "Gamma"] and self.grid is None:
            raise ValueError(f"{self.mode}模式需要指定k点网格")
        if self.grid and any(g <= 0 for g in self.grid):
            raise ValueError("k点网格必须为正数")

@dataclass(frozen=True)
class VASPElectronicConfig:
    """VASP电子结构配置"""
    smearing_method: SmearingMethod
    smearing_width: float = 0.05
    energy_cutoff: float = 600.0
    nedos: int = 2000
    is_spin_polarized: bool = False
    ncore: int = 4
    kpar: int = 1

    def __post_init__(self):
        if self.smearing_width <= 0:
            raise ValueError("Smearing宽度必须为正数")
        if self.energy_cutoff <= 0:
            raise ValueError("能量截断必须为正数")
        if self.nedos <= 0:
            raise ValueError("NEDOS必须为正数")

@dataclass(frozen=True)
class SurfaceConfig:
    """表面配置值对象"""
    miller_indices: Tuple[int, int, int]
    layers: int
    vacuum_thickness: float
    dipole_correction: bool = True
    dipole_direction: Literal[1, 2, 3] = 3
    termination_elements: Optional[List[str]] = None

    def __post_init__(self):
        if any(index == 0 for index in self.miller_indices):
            raise ValueError("米勒指数不能为0")
        if self.layers <= 0:
            raise ValueError("表面层数必须为正数")
        if self.vacuum_thickness <= 10:
            raise ValueError("真空层厚度应≥10Å")

# =============================================================================
# 领域模型 - 核心业务概念
# =============================================================================

@dataclass
class MaterialSystem:
    """材料系统领域模型"""
    name: str
    chemical_formula: str
    elements: List[str]
    crystal_structure: str
    lattice_parameters: Dict[str, float]

    def __post_init__(self):
        if not self.name or not self.name.strip():
            raise ValueError("材料名称不能为空")
        if not self.elements:
            raise ValueError("必须包含至少一个元素")
        if len(self.elements) != len(set(self.elements)):
            raise ValueError("元素列表不能重复")

@dataclass
class VASPCalculation:
    """VASP计算领域模型"""
    calculation_id: str
    calculation_type: CalculationType
    material_system: MaterialSystem
    electronic_config: VASPElectronicConfig
    kpoints_config: KPointsConfig
    convergence_criteria: ConvergenceCriteria
    surface_config: Optional[SurfaceConfig] = None
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        # 验证计算ID格式
        if not re.match(r'^[a-zA-Z0-9_-]+$', self.calculation_id):
            raise ValueError("计算ID格式无效")

@dataclass
class HPCResources:
    """HPC资源配置领域模型"""
    partition: str
    nodes: int
    ntasks_per_node: int
    walltime_minutes: int
    memory_per_node_gb: Optional[float] = None

    def __post_init__(self):
        if self.nodes <= 0:
            raise ValueError("节点数必须为正数")
        if self.ntasks_per_node <= 0:
            raise ValueError("每节点任务数必须为正数")
        if self.walltime_minutes <= 0:
            raise ValueError("运行时间必须为正数")

@dataclass
class HPCJob:
    """HPC作业领域模型"""
    job_id: str
    calculation: VASPCalculation
    resources: HPCResources
    status: JobState
    submit_time: datetime
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    exit_code: Optional[int] = None

    def __post_init__(self):
        # 验证作业ID格式（Slurm通常是数字）
        if not self.job_id.isdigit():
            raise ValueError("HPC作业ID必须为数字")
        # 验证时间逻辑
        if self.start_time and self.start_time < self.submit_time:
            raise ValueError("开始时间不能早于提交时间")
        if self.end_time and self.start_time and self.end_time < self.start_time:
            raise ValueError("结束时间不能早于开始时间")

    @property
    def is_completed(self) -> bool:
        """检查作业是否已完成"""
        return self.status in {JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED, JobState.TIMEOUT}

    @property
    def duration(self) -> Optional[float]:
        """获取作业运行时长（秒）"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

# =============================================================================
# 聚合根 - 管理相关对象的完整性
# =============================================================================

@dataclass
class VASPWorkflow:
    """VASP工作流聚合根"""
    workflow_id: str
    research_title: str
    calculations: List[VASPCalculation] = field(default_factory=list)
    hpc_jobs: List[HPCJob] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def add_calculation(self, calculation: VASPCalculation) -> None:
        """添加计算到工作流"""
        # 验证计算与工作流的一致性
        if calculation in self.calculations:
            raise ValueError("计算已存在于工作流中")
        self.calculations.append(calculation)

    def add_hpc_job(self, job: HPCJob) -> None:
        """添加HPC作业到工作流"""
        # 验证作业与工作流中计算的一致性
        calculation_ids = [calc.calculation_id for calc in self.calculations]
        if job.calculation.calculation_id not in calculation_ids:
            raise ValueError("作业对应的计算不在工作流中")
        self.hpc_jobs.append(job)

    def get_active_jobs(self) -> List[HPCJob]:
        """获取活跃的HPC作业"""
        return [job for job in self.hpc_jobs if not job.is_completed]

    def get_calculations_by_type(self, calc_type: CalculationType) -> List[VASPCalculation]:
        """按类型获取计算"""
        return [calc for calc in self.calculations if calc.calculation_type == calc_type]

# =============================================================================
# 工厂类 - 创建领域对象
# =============================================================================

class VASPCalculationFactory:
    """VASP计算工厂类"""

    @staticmethod
    def create_bulk_calculation(
        calc_id: str,
        material: MaterialSystem,
        kpoints_density: int = 12,
        energy_cutoff: float = 600.0
    ) -> VASPCalculation:
        """创建块体优化计算"""
        kpoints_config = KPointsConfig(
            mode="Monkhorst-Pack",
            grid=(kpoints_density, kpoints_density, kpoints_density)
        )

        electronic_config = VASPElectronicConfig(
            smearing_method=SmearingMethod.FERMI_DIRAC,
            smearing_width=0.05,
            energy_cutoff=energy_cutoff
        )

        convergence_criteria = ConvergenceCriteria(
            energy_threshold=1e-6,
            force_threshold=0.015,
            stress_threshold=0.1
        )

        return VASPCalculation(
            calculation_id=calc_id,
            calculation_type=CalculationType.GEOMETRY_OPTIMIZATION,
            material_system=material,
            electronic_config=electronic_config,
            kpoints_config=kpoints_config,
            convergence_criteria=convergence_criteria
        )

    @staticmethod
    def create_surface_calculation(
        calc_id: str,
        material: MaterialSystem,
        surface_config: SurfaceConfig,
        kpoints_density: int = 8
    ) -> VASPCalculation:
        """创建表面弛豫计算"""
        kpoints_config = KPointsConfig(
            mode="Monkhorst-Pack",
            grid=(kpoints_density, kpoints_density, 1)
        )

        electronic_config = VASPElectronicConfig(
            smearing_method=SmearingMethod.FERMI_DIRAC,
            smearing_width=0.05,
            energy_cutoff=600.0
        )

        convergence_criteria = ConvergenceCriteria(
            energy_threshold=1e-5,
            force_threshold=0.015,
            stress_threshold=0.1
        )

        return VASPCalculation(
            calculation_id=calc_id,
            calculation_type=CalculationType.SURFACE_RELAXATION,
            material_system=material,
            electronic_config=electronic_config,
            kpoints_config=kpoints_config,
            convergence_criteria=convergence_criteria,
            surface_config=surface_config
        )

# =============================================================================
# 使用示例
# =============================================================================

if __name__ == "__main__":
    # 创建材料系统
    si_c_bulk = MaterialSystem(
        name="3C-SiC Bulk",
        chemical_formula="SiC",
        elements=["Si", "C"],
        crystal_structure="zincblende",
        lattice_parameters={"a": 4.3596}
    )

    # 创建表面配置
    si_c_surface = SurfaceConfig(
        miller_indices=(1, 1, 1),
        layers=6,
        vacuum_thickness=20.0,
        dipole_correction=True
    )

    # 使用工厂创建计算
    bulk_calc = VASPCalculationFactory.create_bulk_calculation(
        "si_c_bulk_opt",
        si_c_bulk
    )

    surface_calc = VASPCalculationFactory.create_surface_calculation(
        "si_c_surface_relax",
        si_c_bulk,
        si_c_surface
    )

    # 创建工作流
    workflow = VASPWorkflow(
        workflow_id="si_c_2deg_study",
        research_title="SiC表面2DEG现象研究"
    )

    workflow.add_calculation(bulk_calc)
    workflow.add_calculation(surface_calc)

    print("✅ 优化的类型系统示例创建成功！")
    print(f"工作流ID: {workflow.workflow_id}")
    print(f"计算数量: {len(workflow.calculations)}")
    print(f"块体计算: {bulk_calc.calculation_type.value}")
    print(f"表面计算: {surface_calc.calculation_type.value}")
    print(f"表面配置: {surface_calc.surface_config.miller_indices} {surface_calc.surface_config.layers}层")