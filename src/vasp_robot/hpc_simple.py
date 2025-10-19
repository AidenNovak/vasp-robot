"""
简化的HPC自动化模块
Simplified HPC Automation Module

减少SSH/SCP命令的复杂性，提供更清晰的接口
"""

import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
import json


@dataclass
class HPCConnection:
    """HPC连接配置"""
    host: str
    user: str
    port: int = 22
    timeout: int = 30
    strict_host_key: bool = False


@dataclass
class HPCJob:
    """HPC作业信息"""
    job_id: str
    job_dir: str
    status: str = "PENDING"
    submit_time: Optional[str] = None


class SimpleHPCClient:
    """简化的HPC客户端"""

    def __init__(self, connection: HPCConnection):
        """初始化客户端"""
        self.conn = connection

    def test_connection(self) -> Tuple[bool, str]:
        """测试HPC连接"""
        try:
            result = self._run_command("echo 'Connection OK'", timeout=10)
            return result
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    def upload_job(self, local_dir: Path, remote_job_dir: str) -> bool:
        """上传作业文件"""
        return self._transfer_files(local_dir, remote_job_dir, upload=True)

    def download_results(self, remote_job_dir: str, local_dir: Path) -> bool:
        """下载计算结果"""
        return self._transfer_files(remote_job_dir, local_dir, upload=False)

    def submit_job(self, job_dir: str, script_name: str = "run.slurm") -> Optional[str]:
        """提交作业"""
        cmd = f"cd {job_dir} && sbatch {script_name}"
        success, output = self._run_command(cmd)

        if success and "Submitted batch job" in output:
            # 提取作业ID
            job_id = output.split()[-1]
            return job_id
        return None

    def get_job_status(self, job_id: str) -> Optional[str]:
        """获取作业状态"""
        cmd = f"squeue -j {job_id} -h -o %T"
        success, output = self._run_command(cmd)

        if success:
            return output.strip() if output else "COMPLETED"
        return None

    def cancel_job(self, job_id: str) -> bool:
        """取消作业"""
        cmd = f"scancel {job_id}"
        success, _ = self._run_command(cmd)
        return success

    def create_remote_directory(self, remote_dir: str) -> bool:
        """创建远程目录"""
        cmd = f"mkdir -p {remote_dir}"
        success, _ = self._run_command(cmd)
        return success

    def _run_command(self, command: str, timeout: Optional[int] = None) -> Tuple[bool, str]:
        """执行SSH命令"""
        ssh_cmd = self._build_ssh_command(command, timeout)
        return self._execute_subprocess(ssh_cmd)

    def _transfer_files(self, source: str, destination: str, upload: bool) -> bool:
        """传输文件"""
        scp_cmd = self._build_scp_command(source, destination, upload)
        success, _ = self._execute_subprocess(scp_cmd, timeout=600)
        return success

    def _build_ssh_command(self, command: str, timeout: Optional[int] = None) -> list:
        """构建SSH命令"""
        ssh_opts = [
            "-o", f"ConnectTimeout={timeout or self.conn.timeout}",
            "-o", f"StrictHostKeyChecking={'yes' if self.conn.strict_host_key else 'no'}",
            "-p", str(self.conn.port)
        ]

        return [
            "ssh",
            *ssh_opts,
            f"{self.conn.user}@{self.conn.host}",
            command
        ]

    def _build_scp_command(self, source: str, destination: str, upload: bool) -> list:
        """构建SCP命令"""
        scp_opts = [
            "-r",
            "-o", f"ConnectTimeout={self.conn.timeout}",
            "-o", f"StrictHostKeyChecking={'yes' if self.conn.strict_host_key else 'no'}",
            "-P", str(self.conn.port)
        ]

        if upload:
            return ["scp", *scp_opts, str(source), f"{self.conn.user}@{self.conn.host}:{destination}"]
        else:
            return ["scp", *scp_opts, f"{self.conn.user}@{self.conn.host}:{source}", str(destination)]

    def _execute_subprocess(self, cmd: list, timeout: Optional[int] = None) -> Tuple[bool, str]:
        """执行子进程命令"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout or self.conn.timeout
            )

            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, result.stderr.strip()

        except subprocess.TimeoutExpired:
            return False, "Command timeout"
        except Exception as e:
            return False, f"Command error: {str(e)}"


class VASPHPCManager:
    """VASP HPC管理器 - 高级接口"""

    def __init__(self, connection: HPCConnection, work_dir: str = "~/vasp_calculations"):
        """初始化管理器"""
        self.client = SimpleHPCClient(connection)
        self.work_dir = work_dir

    def prepare_and_submit(self, job_dir: Path, job_name: str) -> Optional[HPCJob]:
        """准备并提交作业"""
        # 测试连接
        success, msg = self.client.test_connection()
        if not success:
            print(f"❌ HPC连接失败: {msg}")
            return None

        # 创建远程目录
        remote_job_dir = f"{self.work_dir}/{job_name}"
        if not self.client.create_remote_directory(remote_job_dir):
            print("❌ 创建远程目录失败")
            return None

        # 上传文件
        print(f"📤 上传文件到: {remote_job_dir}")
        if not self.client.upload_job(job_dir, remote_job_dir):
            print("❌ 文件上传失败")
            return None

        # 提交作业
        print(f"🚀 提交作业: {job_name}")
        slurm_job_id = self.client.submit_job(remote_job_dir)
        if not slurm_job_id:
            print("❌ 作业提交失败")
            return None

        job = HPCJob(
            job_id=slurm_job_id,
            job_dir=remote_job_dir,
            status="PENDING"
        )

        print(f"✅ 作业提交成功 (Slurm ID: {slurm_job_id})")
        return job

    def monitor_job(self, job: HPCJob, check_interval: int = 60) -> bool:
        """监控作业状态"""
        import time
        from datetime import datetime

        print(f"👀 监控作业 {job.job_id}...")

        while True:
            status = self.client.get_job_status(job.job_id)
            if status is None:
                print("❌ 无法获取作业状态")
                return False

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{current_time}] 作业状态: {status}")

            if status == "COMPLETED":
                print("✅ 作业完成!")
                return True
            elif status in ["FAILED", "CANCELLED", "TIMEOUT"]:
                print(f"❌ 作业失败: {status}")
                return False

            time.sleep(check_interval)

    def download_results(self, job: HPCJob, local_dir: Path) -> bool:
        """下载计算结果"""
        print(f"📥 下载结果到: {local_dir}")
        local_dir.mkdir(parents=True, exist_ok=True)

        # 只下载重要文件
        important_files = [
            "OUTCAR", "vasprun.xml", "CONTCAR",
            "EIGENVAL", "DOSCAR", "PROCAR",
            "CHGCAR", "WAVECAR", "vasp.out"
        ]

        # 下载整个目录（简化版本）
        return self.client.download_results(job.job_dir, local_dir)