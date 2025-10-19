# SiC表面2DEG现象研究计划
# SiC Surface 2DEG Phenomenon Research Plan

## 项目概述 / Project Overview

### 研究背景 / Research Background
二维电子气(2DEG)在材料表面界面的形成是凝聚态物理的重要现象。SiC作为宽带隙半导体，其表面在适当的氢终止处理后可能形成2DEG，这在高电子迁移率晶体管和量子器件中具有重要应用价值。

Two-dimensional electron gas (2DEG) formation at material interfaces is a fundamental phenomenon in condensed matter physics. Silicon carbide (SiC), as a wide-bandgap semiconductor, may form 2DEG at its surfaces when properly hydrogen-terminated, which has important applications in high-electron-mobility transistors and quantum devices.

### 科学问题 / Scientific Questions
1. SiC不同表面取向如何影响2DEG的形成？
2. 氢终止配置对表面电子结构的影响机制是什么？
3. 费米能级附近的电子态密度分布特征如何？
4. 2DEG的输运性质和潜在应用前景如何？

1. How do different SiC surface orientations affect 2DEG formation?
2. What is the mechanism of H-termination configuration influence on surface electronic structure?
3. What are the characteristics of electronic density of states near the Fermi level?
4. How are the transport properties and potential applications of the 2DEG?

## 计算方法 / Computational Methods

### DFT参数设置 / DFT Parameters
- **交换关联泛函**: PBEsol + D3色散修正
- **赝势**: PAW-PBE
- **截断能**: 600 eV (收敛性测试确认)
- **K点密度**: 表面布里渊区6×6×1，态密度计算12×12×1
- **收敛标准**: 能量1e-6 eV，力0.001 eV/Å

### 表面模型 / Surface Models
- **真空层厚度**: 20 Å
- **平板厚度**: 12-16层原子
- **偶极修正**: LVHAR = .TRUE.
- **表面取向**: (111), (001), (1-10), (110)

### 氢终止策略 / H-termination Strategies
1. **全覆盖**: 1×1氢吸附
2. **部分覆盖**: 2×1, 3×3重构
3. **混合终止**: Si端+C端组合
4. **单侧终止**: 仅单面氢化

## 研究阶段 / Research Phases

### 第一阶段：块体优化 (Phase 1: Bulk Optimization)
- [ ] 3C-SiC、4H-SiC、6H-SiC结构优化
- [ ] 晶格常数和体模量计算
- [ ] 电子结构基准计算

### 第二阶段：表面构建 (Phase 2: Surface Construction)
- [ ] 不同取向表面平板模型构建
- [ ] 氢终止配置优化
- [ ] 表面能计算和稳定性分析

### 第三阶段：电子结构 (Phase 3: Electronic Structure)
- [ ] 自洽场计算和高密度k点采样
- [ ] 能带结构和态密度计算
- [ ] 层分解态密度分析
- [ ] 电荷密度分布可视化

### 第四阶段：输运性质 (Phase 4: Transport Properties)
- [ ] 有效质量张量计算
- [ ] 费米速度和载流子密度
- [ ] 量子电容分析

## 预期结果 / Expected Outcomes

### 电子结构特征 / Electronic Structure Features
1. **金属表面态**: 费米能级穿过表面态
2. **电荷局域化**: 电荷密度在表面层集中
3. **各向异性**: 不同方向输运性质差异

### 物理量计算 / Physical Quantities
- 表面能 (Surface energy): J/m²
- 载流子密度 (Carrier density): 10¹³-10¹⁴ cm⁻²
- 迁移率 (Mobility): >1000 cm²/V·s
- 有效质量 (Effective mass): 0.1-0.5 m₀

## 技术路线 / Technical Roadmap

### 计算资源需求 / Computational Resources
- **总计算量**: ~15,000 CPU小时
- **并行效率**: 48核心并行
- **存储需求**: ~500 GB中间文件
- **内存需求**: 每节点64 GB+

### 软件工具链 / Software Toolchain
- **VASP 6.3.2**: 第一性原理计算
- **VASPKIT**: 后处理和分析
- **BoltzTraP**: 输运性质计算
- **VESTA**: 电荷密度可视化

## 风险评估 / Risk Assessment

### 计算风险 / Computational Risks
1. **收敛困难**: 表面偶极矩导致SCF不收敛
2. **尺寸效应**: 有限平板尺寸对2DEG特征的影响
3. **赝势选择**: 不同赝势对表面态的影响

### 解决方案 / Solutions
1. **混合泛函**: HSE06用于关键体系验证
2. **收敛加速**: 混合参数和初始态优化
3. **测试计算**: 多种参数设置对比

## 创新点 / Innovations

1. **系统性研究**: 多种表面取向和终止配置对比
2. **机器学习**: 探索AI辅助的表面结构预测
3. **高通量计算**: 建立SiC表面2DEG数据库
4. **实验关联**: 与现有实验结果对比验证

## 时间规划 / Timeline

- **第1-2周**: 块体优化和表面模型构建
- **第3-4周**: 氢终止配置优化和稳定性分析
- **第5-6周**: 电子结构详细计算
- **第7-8周**: 输运性质分析和数据整理
- **第9-10周**: 结果总结和论文撰写

## 合作与交流 / Collaboration & Communication

### 数据管理 / Data Management
- 计算数据版本控制 (Git LFS)
- 原始数据备份 (HPC + 本地)
- 结果可视化自动化

### 交流计划 / Communication Plan
- 周进度报告
- 中期结果讨论
- 最终成果汇报

---

*创建日期: 2025-10-19*
*项目负责人: Claude Code VASP Assistant*
*计算平台: NK-HPC Cluster*