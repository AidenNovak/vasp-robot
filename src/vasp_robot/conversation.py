"""
对话管理器 - 支持多轮对话和API调用持久化记录
"""

import os
import json
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from pathlib import Path
import yaml
from openai import OpenAI

if TYPE_CHECKING:  # pragma: no cover - used for type hints only
    from .settings import Settings


class ConversationManager:
    """管理多轮对话和API调用记录"""

    def __init__(
        self,
        config_path: str = "config/system_prompts.yaml",
        *,
        settings: Optional["Settings"] = None,
        secrets_path: str = "config/secrets.yaml",
    ):
        if settings is not None:
            self.config = settings.prompts
            self._secrets = settings.secrets
        else:
            self.config = self._load_config(config_path)
            self._secrets = self._load_yaml_file(secrets_path)
        self.messages: List[Dict[str, str]] = []
        self.client: Optional[OpenAI] = None
        self._service_config = {}
        self._default_model = "kimi-k2-0905-preview"

        if isinstance(self._secrets, dict):
            kimi_config = self._secrets.get("services", {}).get("kimi", {})
            if isinstance(kimi_config, dict):
                self._service_config = kimi_config
                self._default_model = kimi_config.get("model", self._default_model)

        # 设置持久化目录
        self.log_dir = Path("api_logs")
        self.log_dir.mkdir(exist_ok=True)

        # 初始化API客户端
        self._init_api_client()

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """加载配置文件"""
        data = self._load_yaml_file(config_path)
        if data:
            return data
        return self._get_default_config()

    def _load_yaml_file(self, path: str) -> Dict[str, Any]:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                loaded = yaml.safe_load(f) or {}
                return loaded if isinstance(loaded, dict) else {}
        except FileNotFoundError:
            return {}
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            return {}

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "vasp_orchestrator_prompt": "你是VASP-HPC编排器助手。",
            "vasp_analysis_prompt": "请解析VASP计算需求。",
            "conversation": {
                "max_history_messages": 20,
                "save_interval": 1,
                "context_window": 4096
            },
            "persistence": {
                "enable_logging": True,
                "log_directory": "api_logs",
                "save_format": "json",
                "include_metadata": True
            }
        }

    def _init_api_client(self):
        """初始化API客户端"""
        api_key = self._resolve_api_key()
        if not api_key:
            raise ValueError(
                "KIMI API key not configured. Set the KIMI_API_KEY environment "
                "variable or update config/secrets.yaml."
            )

        base_url = self._service_config.get("base_url", "https://api.moonshot.cn/v1")
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = OpenAI(**client_kwargs)

    def _resolve_api_key(self) -> Optional[str]:
        env_key = os.getenv("KIMI_API_KEY")
        if env_key:
            return env_key

        if isinstance(self._secrets, dict):
            api_keys = self._secrets.get("api_keys", {})
            if isinstance(api_keys, dict):
                candidate = api_keys.get("kimi") or api_keys.get("KIMI")
                if candidate and "SET_ME" not in candidate:
                    return candidate
        return None

    def make_messages(self, input_text: str, system_prompt: str = None, n: int = None) -> List[Dict[str, str]]:
        """
        构建消息列表，支持多轮对话

        Args:
            input_text: 用户输入
            system_prompt: 系统提示词（可选）
            n: 最大历史消息数量

        Returns:
            构建的消息列表
        """
        if n is None:
            n = self.config["conversation"]["max_history_messages"]

        if system_prompt is None:
            system_prompt = self.config["vasp_orchestrator_prompt"]

        # 添加用户消息到历史记录
        self.messages.append({
            "role": "user",
            "content": input_text,
            "timestamp": datetime.now().isoformat()
        })

        # 构建新的消息列表
        new_messages = []

        # 添加系统消息
        new_messages.append({
            "role": "system",
            "content": system_prompt
        })

        # 如果历史消息超过限制，只保留最新的n条
        if len(self.messages) > n:
            self.messages = self.messages[-n:]

        # 添加历史消息（不包含内部时间戳）
        for msg in self.messages:
            new_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        return new_messages

    def chat(
        self,
        input_text: str,
        system_prompt: str = None,
        temperature: float = 0.7,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        进行多轮对话

        Args:
            input_text: 用户输入
            system_prompt: 系统提示词（可选）
            temperature: 温度参数
            model: 模型名称

        Returns:
            包含回复和元数据的字典
        """
        if not self.client:
            raise RuntimeError("API客户端未初始化")

        start_time = time.time()

        if model is None:
            model = self._default_model

        # 构建消息
        messages = self.make_messages(input_text, system_prompt)

        # 准备API调用日志
        api_log = {
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "temperature": temperature,
            "input": input_text,
            "messages_count": len(messages),
            "system_prompt": system_prompt
        }

        try:
            # 调用API
            completion = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )

            # 获取回复
            assistant_message = completion.choices[0].message
            response_text = assistant_message.content

            # 记录API使用信息
            usage = completion.usage
            api_log.update({
                "response": response_text,
                "prompt_tokens": usage.prompt_tokens if usage else None,
                "completion_tokens": usage.completion_tokens if usage else None,
                "total_tokens": usage.total_tokens if usage else None,
                "response_time": time.time() - start_time,
                "status": "success"
            })

            # 将助手回复添加到历史记录
            self.messages.append({
                "role": "assistant",
                "content": response_text,
                "timestamp": datetime.now().isoformat()
            })

            # 保存日志
            if self.config["persistence"]["enable_logging"]:
                self._save_api_log(api_log)

            return {
                "response": response_text,
                "usage": {
                    "prompt_tokens": usage.prompt_tokens if usage else None,
                    "completion_tokens": usage.completion_tokens if usage else None,
                    "total_tokens": usage.total_tokens if usage else None
                },
                "response_time": api_log["response_time"],
                "status": "success"
            }

        except Exception as e:
            # 记录错误
            api_log.update({
                "error": str(e),
                "response_time": time.time() - start_time,
                "status": "error"
            })

            if self.config["persistence"]["enable_logging"]:
                self._save_api_log(api_log)

            return {
                "error": str(e),
                "response_time": api_log["response_time"],
                "status": "error"
            }

    def _save_api_log(self, log_data: Dict[str, Any]):
        """保存API调用日志"""
        try:
            timestamp = datetime.now()
            log_filename = f"api_calls_{timestamp.strftime('%Y%m%d')}.json"
            log_path = self.log_dir / log_filename

            # 读取现有日志
            logs = []
            if log_path.exists():
                with open(log_path, 'r', encoding='utf-8') as f:
                    try:
                        logs = json.load(f)
                    except json.JSONDecodeError:
                        logs = []

            # 添加新日志
            logs.append(log_data)

            # 保存日志
            with open(log_path, 'w', encoding='utf-8') as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"保存API日志失败: {e}")

    def save_conversation(self, filename: str = None):
        """保存当前对话历史"""
        if filename is None:
            timestamp = datetime.now()
            filename = f"conversation_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"

        conversation_path = self.log_dir / filename

        try:
            with open(conversation_path, 'w', encoding='utf-8') as f:
                json.dump(self.messages, f, ensure_ascii=False, indent=2)
            print(f"对话已保存到: {conversation_path}")
        except Exception as e:
            print(f"保存对话失败: {e}")

    def load_conversation(self, filename: str):
        """加载对话历史"""
        conversation_path = self.log_dir / filename

        try:
            with open(conversation_path, 'r', encoding='utf-8') as f:
                self.messages = json.load(f)
            print(f"对话已从 {conversation_path} 加载")
        except Exception as e:
            print(f"加载对话失败: {e}")

    def clear_conversation(self):
        """清空对话历史"""
        self.messages = []
        print("对话历史已清空")

    def spawn_child(self, keep_history: bool = False) -> "ConversationManager":
        """Create a lightweight child session sharing the same API client.

        Claude Code often benefits from orchestrating multiple specialised
        sub-agents that should not leak conversation state between each other.
        This helper returns a new :class:`ConversationManager` instance that
        shares the configuration, API client and persistence settings with the
        parent manager while optionally copying the existing message history.

        Args:
            keep_history: Whether to copy the current message history into the
                spawned session. Defaults to ``False`` so each sub-agent starts
                with a clean slate.

        Returns:
            ConversationManager: A ready-to-use manager sharing the same API
            client connection.
        """

        child = ConversationManager.__new__(ConversationManager)
        child.config = self.config
        child.messages = list(self.messages) if keep_history else []
        child.client = self.client
        child.log_dir = self.log_dir
        child._secrets = self._secrets
        child._service_config = self._service_config
        child._default_model = self._default_model
        return child

    def get_conversation_summary(self) -> Dict[str, Any]:
        """获取对话摘要"""
        if not self.messages:
            return {"total_messages": 0}

        user_messages = [msg for msg in self.messages if msg["role"] == "user"]
        assistant_messages = [msg for msg in self.messages if msg["role"] == "assistant"]

        return {
            "total_messages": len(self.messages),
            "user_messages": len(user_messages),
            "assistant_messages": len(assistant_messages),
            "first_message_time": self.messages[0].get("timestamp"),
            "last_message_time": self.messages[-1].get("timestamp")
        }

    def get_recent_logs(self, days: int = 1) -> List[Dict[str, Any]]:
        """获取最近的API调用日志"""
        recent_logs = []
        cutoff_time = datetime.now().timestamp() - (days * 24 * 3600)

        # 遍历日志文件
        for log_file in self.log_dir.glob("api_calls_*.json"):
            if log_file.stat().st_mtime < cutoff_time:
                continue

            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
                    recent_logs.extend(logs)
            except Exception:
                continue

        # 按时间排序
        recent_logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return recent_logs

    def print_api_statistics(self, days: int = 1):
        """打印API使用统计"""
        logs = self.get_recent_logs(days)

        if not logs:
            print(f"最近{days}天没有API调用记录")
            return

        total_calls = len(logs)
        successful_calls = len([log for log in logs if log.get("status") == "success"])
        failed_calls = total_calls - successful_calls

        total_tokens = sum(log.get("total_tokens", 0) for log in logs if log.get("total_tokens"))
        total_time = sum(log.get("response_time", 0) for log in logs)

        print(f"\n📊 API使用统计 (最近{days}天):")
        print(f"总调用次数: {total_calls}")
        print(f"成功次数: {successful_calls}")
        print(f"失败次数: {failed_calls}")
        print(f"成功率: {successful_calls/total_calls*100:.1f}%")
        print(f"总Token数: {total_tokens:,}")
        print(f"总响应时间: {total_time:.2f}秒")
        print(f"平均响应时间: {total_time/total_calls:.2f}秒")
