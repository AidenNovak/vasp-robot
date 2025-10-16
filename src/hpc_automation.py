#!/usr/bin/env python3
"""
HPC自动化连接和提交脚本
HPC Automation Script for Connection and Job Submission
支持VASP计算的HPC集群自动化操作
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import yaml


@dataclass
class HPCJobStatus:
    """HPC作业状态"""
    job_id: str
    status: str  # PENDING, RUNNING, COMPLETED, FAILED
    submit_time: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    nodes_used: int = 0
    walltime_used: str = ""
    exit_code: Optional[int] = None


@dataclass
class HPCConfig:
    """HPC配置"""
    host: str
    user: str
    port: int
    work_dir: str
    vasp_module: str
    vasp_exec: str
    potcar_path: str


class HPCAutomation:
    """HPC自动化操作类"""

    def __init__(self, config_path: str = "config/workflow_config.yaml"):
        self.config = self._load_config(config_path)

        # 使用新的配置格式
        cluster_config = self.config["hpc_environment"]["cluster"]

        self.hpc_config = HPCConfig(
            host=cluster_config["host"],
            user=cluster_config["user"],
            port=cluster_config.get("port", 22),
            work_dir=cluster_config["work_dir"],
            vasp_module=self.config["hpc_environment"]["vasp_module"]["name"],
            vasp_exec=self.config["hpc_environment"]["vasp_module"]["executable"],
            potcar_path=self.config["hpc_environment"]["vasp_module"]["potcar_path"]
        )

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """加载配置文件"""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    def _run_ssh_command(self, command: str, timeout: int = None) -> Tuple[bool, str]:
        """执行SSH命令"""
        try:
            # 使用配置文件中的超时设置
            if timeout is None:
                timeout = self.config["hpc_environment"]["connection"]["timeout"]

            strict_host_key = self.config["hpc_environment"]["connection"]["strict_host_key_checking"]

            # 构建SSH命令，使用配置参数
            ssh_cmd = [
                "ssh",
                "-o", f"ConnectTimeout={timeout}",
                "-o", f"StrictHostKeyChecking={strict_host_key}",
                "-p", str(self.hpc_config.port),
                f"{self.hpc_config.user}@{self.hpc_config.host}",
                command
            ]

            print(f"🔌 执行SSH命令: {command}")
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, result.stderr.strip()

        except subprocess.TimeoutExpired:
            return False, "SSH命令执行超时"
        except Exception as e:
            return False, f"SSH执行错误: {str(e)}"

    def _run_scp_command(self, local_path: str, remote_path: str, upload: bool = True) -> bool:
        """执行SCP文件传输"""
        try:
            timeout = self.config["hpc_environment"]["connection"]["timeout"]
            strict_host_key = self.config["hpc_environment"]["connection"]["strict_host_key_checking"]

            if upload:
                scp_cmd = [
                    "scp", "-r",
                    "-o", f"ConnectTimeout={timeout}",
                    "-o", f"StrictHostKeyChecking={strict_host_key}",
                    "-P", str(self.hpc_config.port),
                    local_path,
                    f"{self.hpc_config.user}@{self.hpc_config.host}:{remote_path}"
                ]
                direction = "上传"
            else:
                scp_cmd = [
                    "scp", "-r",
                    "-o", f"ConnectTimeout={timeout}",
                    "-o", f"StrictHostKeyChecking={strict_host_key}",
                    "-P", str(self.hpc_config.port),
                    f"{self.hpc_config.user}@{self.hpc_config.host}:{remote_path}",
                    local_path
                ]
                direction = "下载"

            print(f"📁 {direction}文件: {local_path} -> {remote_path}")
            result = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=600)

            if result.returncode == 0:
                print(f"✅ 文件{direction}成功")
                return True
            else:
                print(f"❌ 文件{direction}失败: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            print(f"❌ 文件{direction}超时")
            return False
        except Exception as e:
            print(f"❌ 文件{direction}错误: {str(e)}")
            return False

    def test_hpc_connection(self) -> bool:
        """测试HPC连接"""
        print("🔍 测试HPC连接...")

        # 测试基本连接
        success, output = self._run_ssh_command("echo 'HPC连接测试成功'", timeout=10)
        if not success:
            print(f"❌ HPC连接失败: {output}")
            return False

        print("✅ HPC连接成功")

        # 检查工作目录
        success, output = self._run_ssh_command(f"test -d {self.hpc_config.work_dir} && echo '目录存在' || echo '目录不存在'")
        if success and "目录存在" in output:
            print(f"✅ 工作目录存在: {self.hpc_config.work_dir}")
        else:
            print(f"⚠️ 工作目录不存在，将创建: {self.hpc_config.work_dir}")
            success, _ = self._run_ssh_command(f"mkdir -p {self.hpc_config.work_dir}")
            if success:
                print("✅ 工作目录创建成功")
            else:
                print("❌ 工作目录创建失败")
                return False

        # 检查VASP模块
        success, output = self._run_ssh_command(f"module spider {self.hpc_config.vasp_module}")
        if success:
            print(f"✅ VASP模块可用: {self.hpc_config.vasp_module}")
        else:
            print(f"❌ VASP模块不可用: {self.hpc_config.vasp_module}")
            return False

        # 检查Slurm状态
        success, output = self._run_ssh_command("sinfo --version")
        if success:
            print("✅ Slurm调度系统正常")
        else:
            print("❌ Slurm调度系统异常")
            return False

        return True

    def upload_job_files(self, job_dir: Path, job_id: str) -> bool:
        """上传作业文件到HPC"""
        print(f"📤 上传作业文件: {job_id}")

        # 远程目录（确保路径格式正确）
        remote_job_dir = f"{self.hpc_config.work_dir.rstrip('/')}/{job_id}"

        # 创建远程目录
        success, _ = self._run_ssh_command(f"mkdir -p {remote_job_dir}")
        if not success:
            print("❌ 创建远程目录失败")
            return False

        # 上传作业文件（直接上传目录内容，避免嵌套）
        local_job_dir = Path("vasp_workflow_jobs") / job_id
        if not local_job_dir.exists():
            print(f"❌ 本地作业目录不存在: {local_job_dir}")
            return False

        # 上传目录内的所有文件，而不是整个目录
        upload_success = True
        for file_path in local_job_dir.glob("*"):
            if file_path.is_file():
                if not self._run_scp_command(str(file_path), f"{remote_job_dir}/{file_path.name}", upload=True):
                    upload_success = False
                    print(f"❌ 文件上传失败: {file_path.name}")

        return upload_success

    def submit_vasp_job(self, job_id: str) -> Optional[str]:
        """提交VASP作业"""
        print(f"🚀 提交VASP作业: {job_id}")

        remote_job_dir = f"{self.hpc_config.work_dir.rstrip('/')}/{job_id}"
        submit_cmd = f"cd {remote_job_dir} && sbatch run.slurm"

        success, output = self._run_ssh_command(submit_cmd)
        if success:
            # 解析作业ID
            import re
            job_id_match = re.search(r'Submitted batch job (\d+)', output)
            if job_id_match:
                slurm_job_id = job_id_match.group(1)
                print(f"✅ 作业提交成功，Slurm作业ID: {slurm_job_id}")
                return slurm_job_id
            else:
                print("⚠️ 无法解析作业ID，但提交可能成功")
                return "unknown"
        else:
            print(f"❌ 作业提交失败: {output}")
            return None

    def get_job_status(self, slurm_job_id: str) -> Optional[HPCJobStatus]:
        """获取作业状态"""
        if slurm_job_id == "unknown":
            return None

        print(f"🔍 查询作业状态: {slurm_job_id}")

        # 获取作业基本信息
        cmd = f"squeue -j {slurm_job_id} -h -o '%T|%A|%u|%N|%l|%M|%S'"
        success, output = self._run_ssh_command(cmd)

        if success and output.strip():
            parts = output.strip().split('|')
            if len(parts) >= 7:
                status = parts[0]
                submit_time = parts[6] if len(parts) > 6 else ""

                return HPCJobStatus(
                    job_id=slurm_job_id,
                    status=status,
                    submit_time=submit_time
                )
        else:
            # 作业可能已完成，检查历史
            history_cmd = f"sacct -j {slurm_job_id} -n -o 'State,Submit,Start,End,ExitCode,AllocNodes'"
            success, output = self._run_ssh_command(history_cmd)

            if success and output.strip():
                lines = output.strip().split('\n')
                for line in lines:
                    if line.strip():
                        parts = line.strip().split()
                        if len(parts) >= 6:
                            state = parts[0]
                            submit_time = parts[1]
                            start_time = parts[2]
                            end_time = parts[3]
                            exit_code = parts[4]
                            nodes_used = int(parts[5]) if parts[5].isdigit() else 0

                            # 确定最终状态
                            if "COMPLETED" in state:
                                status = "COMPLETED"
                            elif "FAILED" in state:
                                status = "FAILED"
                            elif "CANCELLED" in state:
                                status = "CANCELLED"
                            else:
                                status = "COMPLETED"  # 默认为完成

                            return HPCJobStatus(
                                job_id=slurm_job_id,
                                status=status,
                                submit_time=submit_time,
                                start_time=start_time if start_time != "Unknown" else None,
                                end_time=end_time if end_time != "Unknown" else None,
                                nodes_used=nodes_used,
                                exit_code=int(exit_code.split(':')[0]) if ':' in exit_code else None
                            )

        return None

    def monitor_job(self, slurm_job_id: str, check_interval: int = 60, max_wait: int = 7200) -> bool:
        """监控作业执行"""
        print(f"👁️ 开始监控作业: {slurm_job_id}")
        print(f"⏰ 检查间隔: {check_interval}秒，最长等待: {max_wait/3600:.1f}小时")

        start_time = time.time()
        last_status = None

        while time.time() - start_time < max_wait:
            job_status = self.get_job_status(slurm_job_id)

            if job_status:
                current_status = job_status.status
                if current_status != last_status:
                    print(f"📊 作业状态更新: {current_status}")
                    last_status = current_status

                if current_status in ["COMPLETED", "FAILED", "CANCELLED"]:
                    print(f"🏁 作业结束，最终状态: {current_status}")
                    if job_status.exit_code is not None:
                        print(f"🔢 退出代码: {job_status.exit_code}")
                    return current_status == "COMPLETED"

            time.sleep(check_interval)

        print(f"⏰ 监控超时 ({max_wait/3600:.1f}小时)")
        return False

    def download_results(self, job_id: str, local_result_dir: str = "vasp_results") -> bool:
        """下载计算结果"""
        print(f"📥 下载计算结果: {job_id}")

        # 创建本地结果目录
        local_path = Path(local_result_dir) / job_id
        local_path.mkdir(parents=True, exist_ok=True)

        # 远程目录
        remote_dir = f"{self.hpc_config.work_dir.rstrip('/')}/{job_id}"

        # 下载关键结果文件
        result_files = [
            "OUTCAR",
            "vasprun.xml",
            "CONTCAR",
            "PROCAR",
            "CHGCAR",
            "WAVECAR",
            "DOSCAR",
            "EIGENVAL",
            "vasp.out",
            "slurm-*.out"
        ]

        for file_pattern in result_files:
            # 使用通配符下载文件
            success, _ = self._run_ssh_command(f"cd {remote_dir} && ls {file_pattern} 2>/dev/null")
            if success:
                # 下载匹配的文件
                download_cmd = f"{remote_dir}/{file_pattern}"
                if self._run_scp_command(download_cmd, str(local_path), upload=False):
                    print(f"✅ 已下载: {file_pattern}")
                else:
                    print(f"⚠️ 下载失败: {file_pattern}")

        return True

    def cleanup_remote_files(self, job_id: str, keep_results: bool = True) -> bool:
        """清理远程文件"""
        print(f"🧹 清理远程文件: {job_id}")

        remote_dir = f"{self.hpc_config.work_dir.rstrip('/')}/{job_id}"

        if keep_results:
            # 只删除临时文件，保留结果
            temp_files = ["*.tmp", "*.rel", "*~"]
            for pattern in temp_files:
                self._run_ssh_command(f"cd {remote_dir} && rm -f {pattern}")
            print("✅ 临时文件清理完成")
        else:
            # 删除整个作业目录
            success, _ = self._run_ssh_command(f"rm -rf {remote_dir}")
            if success:
                print("✅ 远程作业目录删除完成")
            else:
                print("❌ 远程作业目录删除失败")

        return True

    def run_complete_job_cycle(self, job_id: str) -> Dict[str, Any]:
        """运行完整的作业周期"""
        print(f"🔄 开始完整作业周期: {job_id}")

        result = {
            "job_id": job_id,
            "steps": {},
            "success": False,
            "error": None
        }

        try:
            # 1. 上传文件
            if not self.upload_job_files(Path("vasp_workflow_jobs") / job_id, job_id):
                raise Exception("文件上传失败")
            result["steps"]["upload"] = "completed"

            # 2. 提交作业
            slurm_job_id = self.submit_vasp_job(job_id)
            if not slurm_job_id:
                raise Exception("作业提交失败")
            result["steps"]["submit"] = "completed"
            result["slurm_job_id"] = slurm_job_id

            # 3. 监控作业
            if not self.monitor_job(slurm_job_id):
                raise Exception("作业监控超时或失败")
            result["steps"]["monitor"] = "completed"

            # 4. 下载结果
            if not self.download_results(job_id):
                raise Exception("结果下载失败")
            result["steps"]["download"] = "completed"

            # 5. 清理临时文件
            self.cleanup_remote_files(job_id, keep_results=True)
            result["steps"]["cleanup"] = "completed"

            result["success"] = True
            print("✅ 完整作业周期执行成功")

        except Exception as e:
            result["error"] = str(e)
            print(f"❌ 作业周期执行失败: {e}")

        return result


# 命令行接口
def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python hpc_automation.py test                    # 测试HPC连接")
        print("  python hpc_automation.py submit <job_id>        # 提交作业")
        print("  python hpc_automation.py status <slurm_job_id>  # 查询状态")
        print("  python hpc_automation.py monitor <slurm_job_id> # 监控作业")
        print("  python hpc_automation.py download <job_id>      # 下载结果")
        print("  python hpc_automation.py run <job_id>           # 完整周期")
        sys.exit(1)

    command = sys.argv[1]

    hpc = HPCAutomation()

    if command == "test":
        success = hpc.test_hpc_connection()
        sys.exit(0 if success else 1)

    elif command == "submit" and len(sys.argv) >= 3:
        job_id = sys.argv[2]
        slurm_job_id = hpc.submit_vasp_job(job_id)
        if slurm_job_id:
            print(f"作业ID: {slurm_job_id}")
        else:
            sys.exit(1)

    elif command == "status" and len(sys.argv) >= 3:
        slurm_job_id = sys.argv[2]
        status = hpc.get_job_status(slurm_job_id)
        if status:
            print(f"作业状态: {status.status}")
            print(f"提交时间: {status.submit_time}")
            if status.start_time:
                print(f"开始时间: {status.start_time}")
            if status.end_time:
                print(f"结束时间: {status.end_time}")
        else:
            print("无法获取作业状态")
            sys.exit(1)

    elif command == "monitor" and len(sys.argv) >= 3:
        slurm_job_id = sys.argv[2]
        success = hpc.monitor_job(slurm_job_id)
        sys.exit(0 if success else 1)

    elif command == "download" and len(sys.argv) >= 3:
        job_id = sys.argv[2]
        success = hpc.download_results(job_id)
        sys.exit(0 if success else 1)

    elif command == "run" and len(sys.argv) >= 3:
        job_id = sys.argv[2]
        result = hpc.run_complete_job_cycle(job_id)
        print(f"作业周期结果: {json.dumps(result, indent=2)}")
        sys.exit(0 if result["success"] else 1)

    else:
        print("无效的命令或参数不足")
        sys.exit(1)


if __name__ == "__main__":
    main()