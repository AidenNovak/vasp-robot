"""
统一的错误处理模块
Unified Error Handling Module

提供清晰的错误处理模式和自定义异常类
"""

import sys
from typing import Any, Optional, Type, Callable
from functools import wraps
from enum import Enum


class ErrorCategory(Enum):
    """错误类别"""
    CONFIG = "configuration"
    NETWORK = "network"
    FILE_IO = "file_io"
    VASP = "vasp_calculation"
    HPC = "hpc_operation"
    AI_PARSING = "ai_parsing"
    VALIDATION = "validation"


class VASPRobotError(Exception):
    """VASP Robot基础异常类"""

    def __init__(
        self,
        message: str,
        category: ErrorCategory,
        details: Optional[dict] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.details = details or {}
        self.cause = cause

    def __str__(self) -> str:
        error_msg = f"[{self.category.value.upper()}] {self.message}"
        if self.details:
            error_msg += f"\nDetails: {self.details}"
        if self.cause:
            error_msg += f"\nCaused by: {str(self.cause)}"
        return error_msg


class ConfigError(VASPRobotError):
    """配置错误"""
    def __init__(self, message: str, config_file: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCategory.CONFIG, **kwargs)
        if config_file:
            self.details["config_file"] = config_file


class NetworkError(VASPRobotError):
    """网络连接错误"""
    def __init__(self, message: str, host: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCategory.NETWORK, **kwargs)
        if host:
            self.details["host"] = host


class FileIOError(VASPRobotError):
    """文件操作错误"""
    def __init__(self, message: str, file_path: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCategory.FILE_IO, **kwargs)
        if file_path:
            self.details["file_path"] = file_path


class VASPError(VASPRobotError):
    """VASP计算错误"""
    def __init__(self, message: str, incar_params: Optional[dict] = None, **kwargs):
        super().__init__(message, ErrorCategory.VASP, **kwargs)
        if incar_params:
            self.details["incar_params"] = incar_params


class HPCError(VASPRobotError):
    """HPC操作错误"""
    def __init__(self, message: str, job_id: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCategory.HPC, **kwargs)
        if job_id:
            self.details["job_id"] = job_id


class AIParsingError(VASPRobotError):
    """AI解析错误"""
    def __init__(self, message: str, input_text: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCategory.AI_PARSING, **kwargs)
        if input_text:
            self.details["input_text"] = input_text[:100] + "..." if len(input_text) > 100 else input_text


class ValidationError(VASPRobotError):
    """验证错误"""
    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCategory.VALIDATION, **kwargs)
        if field:
            self.details["field"] = field


def handle_errors(
    category: ErrorCategory,
    reraise: bool = True,
    default_return: Any = None,
    log_errors: bool = True
):
    """
    错误处理装饰器

    Args:
        category: 错误类别
        reraise: 是否重新抛出异常
        default_return: 发生错误时的默认返回值
        log_errors: 是否记录错误
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # 转换为相应的错误类别
                if isinstance(e, VASPRobotError):
                    error = e
                else:
                    error = VASPRobotError(
                        message=str(e),
                        category=category,
                        cause=e
                    )

                if log_errors:
                    print(f"❌ 错误: {error}", file=sys.stderr)

                if reraise:
                    raise error
                else:
                    return default_return

        return wrapper
    return decorator


def safe_execute(func: Callable, *args, default: Any = None, **kwargs) -> Any:
    """
    安全执行函数，捕获所有异常

    Args:
        func: 要执行的函数
        default: 发生错误时的默认返回值
        args: 位置参数
        kwargs: 关键字参数

    Returns:
        函数结果或默认值
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        print(f"⚠️ 执行失败 {func.__name__}: {str(e)}", file=sys.stderr)
        return default


def retry_on_error(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    重试装饰器

    Args:
        max_attempts: 最大尝试次数
        delay: 初始延迟（秒）
        backoff: 延迟倍数
        exceptions: 需要重试的异常类型
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        print(f"⚠️ 尝试 {attempt + 1}/{max_attempts} 失败: {str(e)}")
                        import time
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        print(f"❌ 所有尝试失败")

            raise last_exception

        return wrapper
    return decorator


def validate_input(validation_dict: dict):
    """
    输入验证装饰器

    Args:
        validation_dict: 验证规则字典
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 验证参数
            for param_name, rules in validation_dict.items():
                if param_name in kwargs:
                    value = kwargs[param_name]
                    # 类型检查
                    if "type" in rules and not isinstance(value, rules["type"]):
                        raise ValidationError(
                            f"参数 {param_name} 类型错误，期望 {rules['type'].__name__}",
                            field=param_name
                        )
                    # 值范围检查
                    if "choices" in rules and value not in rules["choices"]:
                        raise ValidationError(
                            f"参数 {param_name} 值无效，可选值: {rules['choices']}",
                            field=param_name
                        )
                    # 自定义验证函数
                    if "validator" in rules:
                        validator = rules["validator"]
                        if not validator(value):
                            raise ValidationError(
                                f"参数 {param_name} 验证失败",
                                field=param_name
                            )

            return func(*args, **kwargs)

        return wrapper
    return decorator


# 便捷的错误创建函数
def create_config_error(message: str, **kwargs) -> ConfigError:
    """创建配置错误"""
    return ConfigError(message, **kwargs)


def create_network_error(message: str, **kwargs) -> NetworkError:
    """创建网络错误"""
    return NetworkError(message, **kwargs)


def create_file_error(message: str, **kwargs) -> FileIOError:
    """创建文件错误"""
    return FileIOError(message, **kwargs)


def create_vasp_error(message: str, **kwargs) -> VASPError:
    """创建VASP错误"""
    return VASPError(message, **kwargs)


def create_hpc_error(message: str, **kwargs) -> HPCError:
    """创建HPC错误"""
    return HPCError(message, **kwargs)


def create_ai_error(message: str, **kwargs) -> AIParsingError:
    """创建AI解析错误"""
    return AIParsingError(message, **kwargs)


def create_validation_error(message: str, **kwargs) -> ValidationError:
    """创建验证错误"""
    return ValidationError(message, **kwargs)