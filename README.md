# VASP-HPC Research Workflow

A complete workflow for VASP (Vienna Ab initio Simulation Package) calculations on HPC clusters, powered by Kimi AI LLM and Claude Code integration.

## Features

- 🤖 **AI-Powered Planning**: Kimi LLM analyzes research needs and generates professional VASP calculation plans
- 🔬 **Scientific Workflow**: Complete pipeline from research problem to HPC execution
- 📋 **Intelligent Parameter Generation**: Automatically optimized VASP parameters for different calculations
- 🛡️ **Quality Control**: Human approval required before HPC submission
- 🔍 **Full Audit Trail**: Complete reproducibility with file hashes and metadata
- 🚀 **HPC Integration**: Automated SSH/Slurm integration for NK-HPC cluster
- 📊 **Result Analysis**: Parse and summarize VASP outputs automatically

## Quick Start

### 1. Environment Setup

```bash
# Create and activate virtual environment
python3 -m venv vasp-env
source vasp-env/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy environment template
cp .env.example .env

# Set your Kimi API key
# Edit .env and add: KIMI_API_KEY=your_kimi_api_key_here
```

### 3. Run the Workflow

```bash
# Start the research workflow
python vasp_research_workflow.py "研究SiC的能带结构和光学性质"
```

## Usage Examples

### Scientific Research Workflow

```bash
# Material properties calculation
python vasp_research_workflow.py "研究SiC的能带结构和光学性质"

# Geometry optimization
python vasp_research_workflow.py "优化Si晶体的几何结构"

# Mechanical properties
python vasp_research_workflow.py "计算SiC的体模量和弹性常数"
```

The workflow will:
1. **AI Analysis**: Kimi LLM analyzes your research requirements
2. **Parameter Generation**: Automatically generate optimized VASP parameters
3. **File Creation**: Generate INCAR, KPOINTS, POSCAR, and Slurm scripts
4. **HPC Upload**: Transfer files to NK-HPC cluster
5. **Job Submission**: Submit to Slurm queue for execution
6. **Monitoring**: Track job progress and download results

### Interactive Mode

```bash
# Start interactive VASP agent
python main.py
```

### HPC Management

```bash
# Test HPC connection
python src/hpc_automation.py test

# Monitor job status
python src/hpc_automation.py status <job_id>

# Download results
python src/hpc_automation.py download <job_id>
```

## Project Structure

```
vasp-robot/
├── src/
│   ├── vasp_orchestrator.py        # Core VASP calculation logic and AI integration
│   ├── conversation_manager.py     # Kimi LLM API integration and dialogue management
│   ├── hpc_automation.py           # HPC cluster automation and file transfer
│   └── hpc_interface.py            # HPC SSH interface and job management
├── config/
│   ├── system_prompts.yaml         # AI system prompts for VASP analysis
│   ├── vasp_config.yaml            # Default VASP parameters and settings
│   └── workflow_config.yaml        # HPC environment and workflow configuration
├── templates/
│   ├── kpoints/                    # K-points template files
│   │   └── kpath_SiC.txt          # SiC k-path template
│   └── structures/                 # Structure template files
│       └── SiC_POSCAR.txt         # SiC POSCAR template
├── .claude/
│   ├── CLAUDE.md                   # Claude Code integration and workflow settings
│   └── settings.local.json         # Local Claude Code settings
├── main.py                         # Interactive VASP assistant entry point
├── vasp_research_workflow.py       # Complete automated workflow runner
├── requirements.txt                # Python dependencies
├── .env.example                   # Environment variables template
├── .gitignore                     # Git ignore rules
├── LICENSE                        # MIT License file
└── README.md                      # Project documentation
```

## Configuration

### HPC Environment (`config/workflow_config.yaml`)

```yaml
hpc_environment:
  cluster:
    name: "NK-HPC"
    host: "222.30.45.81"
    port: 20010
    user: "u2413918"
    work_dir: "/home/u2413918/vasp_calculations"

  vasp_module:
    name: "app/vasp/6.3.2/cpu"
    executable: "vasp_std"
    potcar_path: "/public/apps/vasp/6.3.2/potentials/pbe"

  default_resources:
    nodes: 1
    ntasks_per_node: 48
    walltime: "02:00:00"
    partition: "cpu"
```

### AI System Prompts (`config/system_prompts.yaml`)

- `vasp_orchestrator_prompt`: Main dialogue system prompt
- `vasp_analysis_prompt`: VASP calculation analysis prompt
- Customizable for different research domains

## Claude Code Integration

The system includes Claude Code integration through `.claude/CLAUDE.md`:

- Automatic workflow triggering
- Standardized response templates
- Error handling procedures
- Quality control guidelines

## Security & Reproducibility

- ✅ **AI-Powered**: Kimi LLM ensures scientific accuracy
- ✅ **Human Approval**: No HPC jobs submitted without confirmation
- ✅ **File Hashing**: All input files hashed for integrity verification
- ✅ **Audit Trail**: Complete workflow logging and metadata
- ✅ **Deterministic**: Reproducible calculations with fixed parameters
- ✅ **White Box**: All operations transparent and inspectable

## Development

### Workflow Architecture

1. **Research Analysis**: Kimi LLM analyzes scientific requirements
2. **Parameter Optimization**: AI generates optimized VASP parameters
3. **File Generation**: Automated creation of all input files
4. **HPC Integration**: Seamless cluster communication and job management
5. **Result Processing**: Automated download and analysis

### Testing

```bash
# Test HPC connection
python src/hpc_automation.py test

# Test complete workflow
python vasp_research_workflow.py "测试SiC几何优化"
```

## Requirements

- Python 3.8+
- Kimi API key (KIMI_API_KEY)
- SSH access to NK-HPC cluster (222.30.45.81:20010)
- VASP 6.3.2 installation on target cluster
- Slurm scheduler access

## License

MIT License - see LICENSE file for details.
