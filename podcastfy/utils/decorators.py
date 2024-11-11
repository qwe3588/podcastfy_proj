import threading
from functools import wraps
from typing import Optional, Callable, Any
import logging
from fastapi import HTTPException, Header
from podcastfy.constants import ADMIN_API_KEY

logger = logging.getLogger(__name__)

def check_cancelled(func: Callable) -> Callable:
    """
    装饰器: 检查操作是否被取消
    
    在函数执行前和执行后检查 cancel_event 状态。
    如果被取消,则抛出异常。
    
    Args:
        func: 要装饰的函数
        
    Returns:
        装饰后的函数
        
    Raises:
        Exception: 当操作被取消时
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # 获取 cancel_event 参数
        cancel_event = kwargs.get('cancel_event')
        
        # 如果有 cancel_event 且被设置,则抛出异常
        if cancel_event and isinstance(cancel_event, threading.Event) and cancel_event.is_set():
            logger.info(f"Operation {func.__name__} cancelled")
            raise Exception(f"Operation {func.__name__} cancelled by user")
            
        # 执行原函数
        result = func(*args, **kwargs)
        
        # 再次检查取消状态
        if cancel_event and isinstance(cancel_event, threading.Event) and cancel_event.is_set():
            logger.info(f"Operation {func.__name__} cancelled")
            raise Exception(f"Operation {func.__name__} cancelled by user")
            
        return result
    return wrapper

def check_cancelled_async(func: Callable) -> Callable:
    """
    装饰器: 检查异步操作是否被取消
    
    异步函数版本的取消检查装饰器
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        cancel_event = kwargs.get('cancel_event')
        
        if cancel_event and isinstance(cancel_event, threading.Event) and cancel_event.is_set():
            logger.info(f"Operation {func.__name__} cancelled")
            raise Exception(f"Operation {func.__name__} cancelled by user")
            
        result = await func(*args, **kwargs)
        
        if cancel_event and isinstance(cancel_event, threading.Event) and cancel_event.is_set():
            logger.info(f"Operation {func.__name__} cancelled")
            raise Exception(f"Operation {func.__name__} cancelled by user")
            
        return result
    return wrapper 

def verify_admin_key(x_admin_key: Optional[str] = Header(None)):
    """验证管理员 API Key"""
    if not x_admin_key or x_admin_key != ADMIN_API_KEY:
        raise HTTPException(
            status_code=403,
            detail="无效的管理员 API Key"
        )
    return x_admin_key