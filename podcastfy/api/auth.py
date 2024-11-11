from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import asyncio
from typing import Optional, Dict, Any, List

from podcastfy.constants import AUTH_SECRET_KEY
from podcastfy.api.models import User, RedisClient
from podcastfy.api.utils import get_current_time

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7


# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def verify_password(plain_password: str, hashed_password: str) -> bool:
    """异步验证密码"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        pwd_context.verify,
        plain_password,
        hashed_password
    )

async def get_password_hash(password: str) -> str:
    """异步生成密码哈希"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        pwd_context.hash,
        password
    )

async def get_user(email: str) -> Optional[User]:
    """从 Redis 获取用户信息"""
    redis = await RedisClient.get_user_instance()
    user_data = await redis.hgetall(f"user:{email}")
    if user_data:
        # 将字符串 "True"/"False" 转换为布尔值
        if "is_active" in user_data:
            user_data["is_active"] = user_data["is_active"].lower() == "true"
        return User(**user_data)
    return None

async def create_user(email: str, password_hash: str):
    """创建新用户"""
    redis = await RedisClient.get_user_instance()
    user = User(email=email, password_hash=password_hash)
    
    # 将用户数据转换为字符串格式
    user_data = {
        "email": user.email,
        "password_hash": user.password_hash,
        "is_active": str(user.is_active)  # 将布尔值转换为字符串
    }
    
    # 使用 hset 替代 hmset
    for key, value in user_data.items():
        await redis.hset(f"user:{user.email}", key, value)

async def authenticate_user(email: str, password: str):
    """验证用户"""
    redis = await RedisClient.get_user_instance()
    
    # 添加登录失败次数限制
    fail_key = f"login_fail:{email}"
    fail_count = await redis.get(fail_key)
    
    if fail_count and int(fail_count) >= 5:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="登录失败次数过多,请15分钟后重试"
        )
    
    user = await get_user(email)
    if not user or not await verify_password(password, user.password_hash):
        # 记录失败次数
        await redis.incr(fail_key)
        await redis.expire(fail_key, 900)  # 15分钟后重置
        return False
        
    # 登录成功,清除失败记录
    await redis.delete(fail_key)
    return user

def create_access_token(data: dict, expires_delta: timedelta = None):
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = get_current_time('dt') + expires_delta
    else:
        expire = get_current_time('dt') + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, AUTH_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """获取当前用户"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, AUTH_SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = await get_user(email)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    """获取当前活跃用户"""
    if current_user.is_active:
        return current_user
    raise HTTPException(status_code=400, detail="用户未激活")

async def get_all_users() -> List[Dict[str, Any]]:
    """
    获取所有用户信息
    
    Returns:
        List[Dict[str, Any]]: 用户信息列表，不包含密码哈希
    """
    redis = await RedisClient.get_user_instance()
    # 获取所有用户的 key
    user_keys = await redis.keys("user:*")
    users = []
    
    for key in user_keys:
        user_data = await redis.hgetall(key)
        if user_data:
            # 将字符串 "True"/"False" 转换为布尔值
            for bool_field in ["is_active", "is_admin"]:
                if bool_field in user_data:
                    user_data[bool_field] = user_data[bool_field].lower() == "true"
            
            # 删除敏感信息
            if "password_hash" in user_data:
                del user_data["password_hash"]
                
            users.append(user_data)
    
    return users

async def delete_user(email: str) -> bool:
    """删除指定用户"""
    redis = await RedisClient.get_user_instance()
    # 检查用户是否存在
    user_key = f"user:{email}"
    exists = await redis.exists(user_key)
    if exists:
        # 删除用户数据
        await redis.delete(user_key)
        return True
    return False

def check_admin(user: User):
    """检查用户是否是管理员"""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return user

async def get_current_admin_user(current_user: User = Depends(get_current_active_user)):
    """获取当前管理员用户"""
    return check_admin(current_user)