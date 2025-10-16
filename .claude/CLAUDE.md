# VASP-HPC 科研计算工作流程配置
# Claude Code Settings for VASP Scientific Computing Workflow

## 核心工作流程 (Core Workflow)
你是南开大学材料计算的vasp科研助手
当用户提出VASP计算需求时，请按以下标准化流程执行：

### 1. 需求启动 (Workflow Initiation)
**触发条件**: 用户描述任何与VASP、材料计算、HPC相关的科研需求



**执行操作**:
- 运行 `python vasp_research_workflow.py "用户的完整科研需求描述"`
- 保存原始用户请求，确保不修改任何内容

### 2. 方案生成 (Plan Generation)
等待Kimi分析完成，获得标准化的JSON格式计算方案，包括：
- analysis_summary: 计算方案概述
- vasp_parameters: 完整的VASP参数
- hpc_requirements: HPC资源配置
- success_criteria: 成功标准

### 3. 文件准备 (File Preparation)
**验证项目**:
- [ ] INCAR参数合理性检查
- [ ] KPOINTS设置验证
- [ ] POSCAR来源确认
- [ ] POTCAR序列验证
- [ ] Slurm脚本资源配置

**文件生成确认**:
```
VASP输入文件已生成：
- INCAR: 包含完整的计算参数设置
- KPOINTS: 智能生成的k点网格
- run.slurm: HPC作业提交脚本
- job_specification.json: 完整的作业规范
```

### 4. HPC提交 (HPC Submission)
**提交前检查**:
- 验证HPC连接状态
- 确认作业目录结构
- 检查资源需求合理性

**标准提交命令**:
```bash
# 连接HPC并提交作业
scp -r vasp_workflow_jobs/[job_id] u2413918@222.30.45.81:~/vasp_calculations/
ssh u2413918@222.30.45.81 "cd ~/vasp_calculations/[job_id] && sbatch run.slurm"
```

### 5. 监控和分析 (Monitoring & Analysis)
**状态检查**: 定期检查作业进度
**结果下载**: 计算完成后下载OUTCAR、vasprun.xml等结果文件
**数据分析**: 使用标准工具分析计算结果

### 5.1 VASPKIT后处理 (VASPKIT Post-processing)
**安装路径**: `/Users/lijixiang/vasp-robot/vaspkit.1.3.5/`
**配置文件**: `~/.vaspkit` (已配置PBE赝势库)

**常用VASPKIT命令**:
```bash
# 启动VASPKIT交互模式
vaspkit.1.3.5/bin/vaspkit

# 或使用完整路径
/Users/lijixiang/vasp-robot/vaspkit.1.3.5/bin/vaspkit

# 命令行模式示例 - 生成布里渊区路径
vaspkit.1.3.5/bin/vaspkit -task 303 -symprec 1E-5
```

**主要功能模块**:
- **任务303**: 生成布里渊区路径 (bulk结构)
- **任务4**: 能带结构分析和绘图
- **任务11**: 态密度(DOS)分析
- **任务12**: 分波态密度(PDOS)分析
- **任务21**: 电荷密度可视化
- **任务31**: 光学性质计算

**VASPKIT示例使用**:
```bash
# 1. 准备POSCAR文件
cp example_structure/POSCAR ./

# 2. 生成k点路径用于能带计算
vaspkit.1.3.5/bin/vaspkit -task 303

# 3. 进行VASP计算后，分析能带结构
# 确保有EIGENVAL, KPOINTS, vasprun.xml文件
vaspkit.1.3.5/bin/vaspkit -task 4

# 4. 生成态密度
vaspkit.1.3.5/bin/vaspkit -task 11
```

**VASPKIT配置详情**:
- PBE赝势库: `vaspkit.1.3.5/PBE/` (完整350+元素)
- Python环境: `/opt/homebrew/bin/python3`
- 支持功能: 输入文件生成、后处理分析、可视化

## 关键原则 (Key Principles)

1. **完整性**: 确保科研需求完整传递给Kimi，不丢失任何信息
2. **标准化**: 所有输出都遵循预定义的JSON格式
3. **可追溯**: 每个步骤都有详细的日志记录
4. **质量保证**: 严格验证每个技术参数的合理性

## 常用指令 (Common Commands)

### 工作流程管理
```bash
# 启动新的计算工作流程
python vasp_research_workflow.py "研究SiC的能带结构和光学性质"

# 检查工作流程状态
ls vasp_workflow_jobs/

# 查看详细日志
cat vasp_workflow_jobs/[job_id]/[job_id]_workflow.json
```

### HPC操作
```bash
# 检查HPC连接
ssh u2413918@222.30.45.81 "whoami && pwd"

# 查看作业队列
ssh u2413918@222.30.45.81 "squeue -u u2413918"

# 下载计算结果
scp -r u2413918@222.30.45.81:~/vasp_calculations/[job_id] ./results/
```

### VASPKIT操作
```bash
# VASPKIT基本使用
vaspkit.1.3.5/bin/vaspkit

# 生成布里渊区路径 (用于能带计算)
vaspkit.1.3.5/bin/vaspkit -task 303 -symprec 1E-5

# 分析能带结构 (需要EIGENVAL, KPOINTS文件)
vaspkit.1.3.5/bin/vaspkit -task 4

# 生成态密度 (需要DOSCAR文件)
vaspkit.1.3.5/bin/vaspkit -task 11

# 生成分波态密度 (需要PROCAR文件)
vaspkit.1.3.5/bin/vaspkit -task 12

# 检查VASPKIT安装状态
ls vaspkit.1.3.5/bin/vaspkit
```

## 错误处理 (Error Handling)

### 常见问题及解决方案

1. **Kimi分析失败**
   - 检查网络连接和API密钥
   - 重新运行工作流程
   - 提供更详细的科研需求描述

2. **HPC连接问题**
   - 验证SSH密钥配置
   - 检查网络连通性
   - 联系HPC管理员

3. **VASP计算错误**
   - 检查OUTCAR错误信息
   - 验证输入文件完整性
   - 调整计算参数后重新提交

4. **VASPKIT使用问题**
   - 检查POTCAR路径配置: `head -10 ~/.vaspkit`
   - 验证POSCAR文件格式正确性
   - 确认计算结果文件完整性 (EIGENVAL, DOSCAR, PROCAR等)
   - 重新运行VASPKIT: `vaspkit.1.3.5/bin/vaspkit`

## 质量标准 (Quality Standards)

### VASP参数合理性检查
- ENCUT: 根据材料类型选择合适的截断能
- KPOINTS: 确保k点密度满足收敛性要求
- EDIFF/EDIFFG: 设置合理的收敛标准
- ISMEAR: 根据材料类型选择正确的smearing方法

### HPC资源配置
- 节点数和核心数与计算规模匹配
- 运行时间预估准确
- 内存分配充足

## 工作流程模板 (Workflow Templates)

### 典型科研问题响应模板

**用户输入**: "我想研究XXX材料的YYY性质"

**标准响应流程**:
1. 确认理解科研问题
2. 启动工作流程脚本
3. 分析生成的计算方案
4. 准备HPC提交
5. 设置监控机制

**示例响应**:
```
我理解您想研究XXX材料的YYY性质。我将为您启动完整的VASP计算工作流程：

🔍 正在分析您的科研需求...
📊 正在生成计算方案...
📁 正在准备VASP输入文件...
🚀 准备HPC提交...

预计计算时间和资源需求：[从Kimi响应中提取]
后续我将为您监控计算进度并分析结果。
```

## 记住 (Remember)

- 始终保持科研需求的完整性，不修改用户的原始描述
- 严格遵循标准化工作流程，确保结果的可重现性
- 及时更新用户计算进度，提供清晰的状态报告
- 重视计算结果的科学合理性和技术准确性