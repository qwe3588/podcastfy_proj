import uuid
from datetime import datetime
import pytz
from podcastfy.utils import load_config
import re
from typing import Tuple

config = load_config()
timezone_str = config.get('logging', {}).get('timezone', 'Asia/Shanghai')
timezone = pytz.timezone(timezone_str)

def generate_job_id() -> str:
  return str(uuid.uuid4())

def get_current_time(type='str') -> str:
    """获取当前时区的时间"""
    current_time = datetime.now(timezone).replace(microsecond=0)
    if type == 'str':
        return current_time.strftime('%Y-%m-%d %H:%M:%S %z')
    elif type == 'dt':
        return current_time

def validate_password(password: str) -> Tuple[bool, str]:
    """
    验证密码复杂度
    
    规则:
    1. 最小长度8个字符
    2. 至少包含一个大写字母
    3. 至少包含一个小写字母
    4. 至少包含一个数字
    5. 至少包含一个特殊字符
    
    Args:
        password: 要验证的密码
        
    Returns:
        Tuple[bool, str]: (是否通过验证, 错误信息)
    """
    if len(password) < 8:
        return False, "密码长度必须至少为8个字符"
        
    if not re.search(r'[A-Z]', password):
        return False, "密码必须包含至少一个大写字母"
        
    if not re.search(r'[a-z]', password):
        return False, "密码必须包含至少一个小写字母"
        
    if not re.search(r'\d', password):
        return False, "密码必须包含至少一个数字"
        
    if not re.search(r'[!@#$%^&*(),.?":{}|<>_]', password):
        return False, "密码必须包含至少一个特殊字符(!@#$%^&*(),.?\":{}|<>_)"
        
    return True, ""
