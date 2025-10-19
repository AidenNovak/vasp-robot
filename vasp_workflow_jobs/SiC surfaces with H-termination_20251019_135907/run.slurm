#!/bin/bash
#SBATCH -p cpu
#SBATCH -N 1
#SBATCH --ntasks-per-node=48
#SBATCH -J SiC surfaces with H-termination_20251019_135907
#SBATCH -o vasp.out
#SBATCH -t 02:00:00

module load app/vasp/6.3.2/cpu
export VASP_PP_PATH=/public/apps/vasp/6.3.2/potentials/pbe

echo "Starting VASP calculation for SiC surfaces with H-termination_20251019_135907"
echo "Start time: $(date)"
echo "Job ID: $SLURM_JOB_ID"
echo "Nodes: $SLURM_JOB_NUM_NODES"
echo "Tasks: $SLURM_NTASKS"

# Build POTCAR (example - should be customized based on elements)
# cat $VASP_PP_PATH/*/POTCAR > POTCAR

mpirun -np $SLURM_NTASKS vasp_std

echo "VASP calculation completed"
echo "End time: $(date)"
