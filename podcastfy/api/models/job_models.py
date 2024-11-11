import os, json
from redis import asyncio as aioredis
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from fastapi import UploadFile

from .config_models import ConfigAll, ConfigConversation, TTSModelChoice
from podcastfy.api.utils import get_current_time
from podcastfy.constants import JOB_EXPIRE_DAYS, JOB_PREFIX, JOB_HASH_PREFIX

class RedisClient:
    _instance_user: Optional[aioredis.Redis] = None
    _instance_job: Optional[aioredis.Redis] = None
    redis_url: str = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    @classmethod
    async def get_user_instance(cls) -> aioredis.Redis:
        if cls._instance_user is None:
            cls._instance_user = await aioredis.from_url(
                cls.redis_url,
                encoding="utf-8",
                decode_responses=True,
                db=0  # 用户数据使用 db 0
            )
        return cls._instance_user

    @classmethod
    async def get_job_instance(cls) -> aioredis.Redis:
        if cls._instance_job is None:
            cls._instance_job = await aioredis.from_url(
                cls.redis_url,
                encoding="utf-8",
                decode_responses=True,
                db=1  # 作业数据使用 db 1
            )
        return cls._instance_job

    @classmethod
    async def close(cls):
        if cls._instance_user is not None:
            await cls._instance_user.close()
            cls._instance_user = None
        if cls._instance_job is not None:
            await cls._instance_job.close()
            cls._instance_job = None 


# 作业模型
class Job(BaseModel):
    # 定义作业相关的字段
    job_id: str
    user_id: str
    status: str
    create_time: datetime
    update_time: datetime
    job_hash: str
    urls: List[str]
    transcript_file: Optional[UploadFile] = None
    tts_model: TTSModelChoice = None
    transcript_only: bool = False
    config: ConfigAll = None
    conversation_config: ConfigConversation = None

class JobRedisConfig:
    """Redis configuration class."""
    job_prefix = JOB_PREFIX
    job_hash_prefix = JOB_HASH_PREFIX

# Redis 操作相关的辅助函数
class JobRedisOperations:
    @staticmethod
    async def save_job(
        redis: aioredis.Redis, 
        job_id: str, 
        job_info: dict, 
        expire_days: int = JOB_EXPIRE_DAYS
    ):
        """保存作业信息到 Redis"""
        await redis.hset(f"{JobRedisConfig.job_prefix}{job_id}", mapping={
            "data": json.dumps(job_info)
        })
        # 设置过期时间
        await redis.expire(f"{JobRedisConfig.job_prefix}{job_id}", 60 * 60 * 24 * expire_days)

    @staticmethod
    async def get_job(redis: aioredis.Redis, job_id: str) -> Optional[dict]:
        """从 Redis 获取作业信息"""
        job_data = await redis.hget(f"{JobRedisConfig.job_prefix}{job_id}", "data")
        return json.loads(job_data) if job_data else None

    @staticmethod
    async def save_job_hash(redis: aioredis.Redis, job_hash: str, job_id: str):
        """保存作业哈希值到 Redis"""
        key = f"{JobRedisConfig.job_hash_prefix}{job_hash}"
        await redis.set(key, job_id)
        # 设置与作业相同的过期时间
        await redis.expire(key, 60 * 60 * 24 * JOB_EXPIRE_DAYS)

    @staticmethod
    async def get_job_by_hash(redis: aioredis.Redis, job_hash: str) -> Optional[str]:
        """通过哈希值获取作业 ID"""
        key = f"{JobRedisConfig.job_hash_prefix}{job_hash}"
        return await redis.get(key)

    @staticmethod
    async def stop_job(redis: aioredis.Redis, job_id: str) -> bool:
        """停止指定的作业"""
        job = await JobRedisOperations.get_job(redis, job_id)
        if job:
            job["status"] = "stopped"
            job["update_time"] = get_current_time().isoformat()
            await JobRedisOperations.save_job(redis, job_id, job)
            return True
        return False