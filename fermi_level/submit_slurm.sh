#!/bin/bash
# SiC 2DEG Research Project - HPC Submission Script
# 用于提交SiC表面2DEG研究的VASP计算作业

#SBATCH --job-name=SiC_2DEG_Bulk_Test
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=48
#SBATCH --time=02:00:00
#SBATCH --output=SiC_bulk_%j.out
#SBATCH --error=SiC_bulk_%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=u2413918@nankai.edu.cn

# 加载VASP模块
module load app/vasp/6.3.2/cpu

# 设置环境变量
export OMP_NUM_THREADS=48
export VASP_PP_PATH=/public/apps/vasp/6.3.2/potentials/pbe

echo "=========================================="
echo "SiC 2DEG Bulk Calculation - Phase 1"
echo "Job ID: $SLURM_JOB_ID"
echo "Start Time: $(date)"
echo "Node: $SLURM_JOB_NODELIST"
echo "Tasks: $SLURM_NTASKS"
echo "=========================================="

# 检查输入文件
echo "Checking input files..."
for file in INCAR POSCAR KPOINTS POTCAR; do
    if [ -f "$file" ]; then
        echo "✓ $file found"
    else
        echo "✗ $file missing - exiting"
        exit 1
    fi
done

# 检查POTCAR内容
echo "Checking POTCAR content..."
if [ -s "POTCAR" ]; then
    echo "✓ POTCAR contains data"
    grep -c "PAW_PBE" POTCAR
else
    echo "✗ POTCAR is empty - exiting"
    exit 1
fi

# 运行VASP计算
echo "Starting VASP calculation..."
mpirun -np $SLURM_NTASKS vasp_std

# 检查计算结果
echo "Checking calculation results..."
if [ -f "OUTCAR" ]; then
    echo "✓ OUTCAR generated"
    echo "Final energy:" $(grep "free  energy    TOTEN" OUTCAR | tail -1)
else
    echo "✗ OUTCAR not found - calculation may have failed"
fi

if [ -f "CONTCAR" ]; then
    echo "✓ CONTCAR generated - structure optimized"
else
    echo "! CONTCAR not found - may need more optimization steps"
fi

echo "Calculation completed at: $(date)"
echo "=========================================="

# 创建摘要报告
cat > calculation_summary.txt << EOF
SiC 2DEG Bulk Calculation Summary
==================================
Job ID: $SLURM_JOB_ID
Start Time: $(date)
End Time: $(date)
Node: $SLURM_JOB_NODELIST
Tasks: $SLURM_NTASKS

Files Generated:
- INCAR: Input parameters
- POSCAR: Initial structure
- KPOINTS: k-point mesh
- POTCAR: Pseudopotentials
- OUTCAR: VASP output
- CONTCAR: Final structure (if optimization converged)
- CHGCAR: Charge density (if available)
- WAVECAR: Wavefunction (if available)

Next Steps:
1. Check OUTCAR for convergence
2. Analyze electronic structure if converged
3. Proceed to surface calculations
4. Submit next phase calculations
EOF

echo "Summary report generated: calculation_summary.txt"