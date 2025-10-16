"""
HPC Interface for VASP calculations
Handles SSH connections, file transfers, and job submission to remote clusters.
"""

import paramiko
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import yaml

@dataclass
class HPCConfig:
    """HPC cluster configuration"""
    host: str
    port: int
    user: str
    remote_root: str
    vasp_module: str
    vasp_exec: str
    potcar_root: str
    partition: str
    nodes: int
    ntasks_per_node: int
    walltime_minutes: int


class HPCInterface:
    """Interface for HPC cluster operations via SSH"""

    def __init__(self, config_path: str = "config/vasp_config.yaml"):
        self.config = self._load_config(config_path)
        self.ssh_client = None
        self.connected = False

    def _load_config(self, config_path: str) -> HPCConfig:
        """Load HPC configuration from YAML"""
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)

        return HPCConfig(
            host=config_data["ssh"]["host"],
            port=config_data["ssh"]["port"],
            user=config_data["ssh"]["user"],
            remote_root=config_data["paths"]["remote_root"],
            vasp_module=config_data["env"]["vasp_module"],
            vasp_exec=config_data["env"]["vasp_exec"],
            potcar_root=config_data["env"]["potcar_root"],
            partition=config_data["hpc"]["partition"],
            nodes=config_data["hpc"]["nodes"],
            ntasks_per_node=config_data["hpc"]["ntasks_per_node"],
            walltime_minutes=config_data["hpc"]["walltime_minutes"]
        )

    def connect(self) -> bool:
        """Establish SSH connection to HPC cluster using existing SSH config"""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Use existing SSH configuration from ~/.ssh/config
            ssh_config = paramiko.SSHConfig()
            with open(os.path.expanduser("~/.ssh/config")) as f:
                ssh_config.parse(f)

            host_config = ssh_config.lookup(self.config.host)

            # Get connection parameters from SSH config
            hostname = host_config.get('hostname', self.config.host)
            port = int(host_config.get('port', self.config.port))
            username = host_config.get('user', self.config.user)
            key_filename = host_config.get('identityfile', [None])[0]

            print(f"🔌 Connecting to HPC via SSH config: {self.config.host}")
            print(f"   Target: {username}@{hostname}:{port}")

            try:
                self.ssh_client.connect(
                    hostname=hostname,
                    port=port,
                    username=username,
                    key_filename=key_filename,
                    timeout=10,
                    allow_agent=True  # Use SSH agent if available
                )
            except paramiko.AuthenticationException as e:
                print(f"❌ SSH authentication failed: {e}")
                print("💡 Ensure your SSH keys are configured for nk-hpc")
                print("   Test with: ssh nk-hpc")
                return False
            except Exception as e:
                print(f"❌ SSH connection failed: {e}")
                return False

            self.connected = True
            print(f"✅ Connected to HPC cluster {self.config.host}")

            # Test connection and show system info
            stdin, stdout, stderr = self.ssh_client.exec_command("hostname; whoami")
            full_output = stdout.read().decode().strip().split('\n')
            hostname_out = full_output[0] if full_output else "unknown"
            username_out = full_output[1] if len(full_output) > 1 else "unknown"
            print(f"🖥️  Connected to: {hostname_out} as {username_out}")

            return True

        except Exception as e:
            print(f"❌ Failed to connect to HPC cluster: {e}")
            return False

    def disconnect(self):
        """Close SSH connection"""
        if self.ssh_client:
            self.ssh_client.close()
            self.connected = False
            print("🔌 Disconnected from HPC cluster")

    def upload_files(self, local_dir: Path, remote_dir: str) -> bool:
        """Upload directory contents to HPC cluster"""
        if not self.connected:
            print("❌ Not connected to HPC cluster")
            return False

        try:
            sftp = self.ssh_client.open_sftp()

            # Create remote directory if it doesn't exist
            try:
                sftp.stat(remote_dir)
            except FileNotFoundError:
                print(f"📁 Creating remote directory: {remote_dir}")
                self._execute_remote_command(f"mkdir -p {remote_dir}")

            # Upload files
            uploaded_files = []
            for local_file in local_dir.rglob('*'):
                if local_file.is_file():
                    relative_path = local_file.relative_to(local_dir)
                    remote_path = f"{remote_dir}/{relative_path}"

                    # Create remote subdirectories if needed
                    remote_subdir = str(Path(remote_path).parent)
                    try:
                        sftp.stat(remote_subdir)
                    except FileNotFoundError:
                        sftp.mkdir(remote_subdir)

                    print(f"📤 Uploading: {relative_path}")
                    sftp.put(str(local_file), remote_path)
                    uploaded_files.append(relative_path)

            sftp.close()
            print(f"✅ Uploaded {len(uploaded_files)} files to {remote_dir}")
            return True

        except Exception as e:
            print(f"❌ Failed to upload files: {e}")
            return False

    def submit_job(self, remote_dir: str, script_name: str = "run.slurm") -> Optional[str]:
        """Submit Slurm job to HPC queue"""
        if not self.connected:
            print("❌ Not connected to HPC cluster")
            return None

        try:
            # Change to remote directory and submit job
            remote_script = f"{remote_dir}/{script_name}"
            command = f"cd {remote_dir} && sbatch {script_name}"

            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()

            if error:
                print(f"❌ Job submission error: {error}")
                return None

            # Extract job ID from sbatch output (e.g., "Submitted batch job 12345")
            if "Submitted batch job" in output:
                job_id = output.split()[-1]
                print(f"✅ Job submitted successfully: {job_id}")
                return job_id
            else:
                print(f"❌ Unexpected job submission output: {output}")
                return None

        except Exception as e:
            print(f"❌ Failed to submit job: {e}")
            return None

    def check_job_status(self, job_id: str) -> Tuple[str, Optional[str]]:
        """Check job status in Slurm queue"""
        if not self.connected:
            return "UNKNOWN", "Not connected to HPC"

        try:
            command = f"squeue -j {job_id} -h -o %T"
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            status = stdout.read().decode().strip()

            if not status:
                # Job might be completed
                command = f"sacct -j {job_id} -n -o State"
                stdin, stdout, stderr = self.ssh_client.exec_command(command)
                final_status = stdout.read().decode().strip()
                return final_status or "COMPLETED", None

            return status, None

        except Exception as e:
            return "ERROR", str(e)

    def download_results(self, remote_dir: str, local_dir: Path) -> bool:
        """Download calculation results from HPC cluster"""
        if not self.connected:
            print("❌ Not connected to HPC cluster")
            return False

        try:
            sftp = self.ssh_client.open_sftp()

            # Create local directory if it doesn't exist
            local_dir.mkdir(parents=True, exist_ok=True)

            # Files to download
            result_files = [
                "OUTCAR", "vasprun.xml", "vasp.out",
                "PROCAR", "DOSCAR", "EIGENVAL",
                "CHGCAR", "CHG", "WAVECAR",
                "hashes.json", "lineage.json"
            ]

            downloaded_files = []
            for filename in result_files:
                remote_path = f"{remote_dir}/{filename}"
                local_path = local_dir / filename

                try:
                    sftp.stat(remote_path)  # Check if file exists
                    print(f"📥 Downloading: {filename}")
                    sftp.get(remote_path, str(local_path))
                    downloaded_files.append(filename)
                except FileNotFoundError:
                    print(f"⚠️  File not found: {filename}")

            sftp.close()
            print(f"✅ Downloaded {len(downloaded_files)} result files")
            return True

        except Exception as e:
            print(f"❌ Failed to download results: {e}")
            return False

    def _execute_remote_command(self, command: str) -> Tuple[str, str]:
        """Execute command on remote HPC"""
        if not self.connected:
            return "", "Not connected to HPC"

        stdin, stdout, stderr = self.ssh_client.exec_command(command)
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        return output, error

    def monitor_job(self, job_id: str, check_interval: int = 30) -> bool:
        """Monitor job until completion"""
        print(f"👀 Monitoring job {job_id}...")

        while True:
            status, error = self.check_job_status(job_id)

            if error:
                print(f"❌ Error checking job status: {error}")
                return False

            print(f"📊 Job {job_id} status: {status}")

            if status in ["COMPLETED", "FAILED", "CANCELLED"]:
                break

            time.sleep(check_interval)

        return status == "COMPLETED"

    def get_hpc_info(self) -> Dict[str, str]:
        """Get HPC cluster information"""
        if not self.connected:
            return {"status": "Not connected"}

        try:
            # Get cluster load
            stdin, stdout, stderr = self.ssh_client.exec_command("sinfo -s")
            cluster_info = stdout.read().decode().strip()

            # Get queue info
            stdin, stdout, stderr = self.ssh_client.exec_command("squeue -s")
            queue_info = stdout.read().decode().strip()

            return {
                "cluster": cluster_info,
                "queue": queue_info
            }

        except Exception as e:
            return {"error": str(e)}