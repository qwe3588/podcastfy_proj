import asyncio, json, os, shutil, threading, aiofiles, hashlib, yaml
import uuid
import copy

from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional
from datetime import datetime, timedelta
from redis import asyncio as aioredis

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm

from .models import *
from .utils import *
from .auth import *

from podcastfy.client import generate_podcast
from podcastfy.utils import setup_logger, check_cancelled_async, verify_admin_key
from podcastfy.constants import *

app = FastAPI()

os.environ['http_proxy'] = 'http://127.0.0.1:7890'
os.environ['https_proxy'] = 'http://127.0.0.1:7890'

# 创建线程池执行器用于运行同步的generate_podcast函数
thread_pool = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS)

logger = setup_logger(__name__)

# 当前正在处理的作业ID列表
processing_jobs = []

# 创建一个全局的任务字典，保存正在处理的任务
task_dict = {}


async def get_redis_job():
    """获取用于作业的 Redis 实例"""
    return await RedisClient.get_job_instance()

async def get_redis_user():
    """获取用于用户的 Redis 实例"""
    return await RedisClient.get_user_instance()

async def process_job(job_id: str, redis: aioredis.Redis):
    """实际处理播客生成作业"""
    try:
        job = await JobRedisOperations.get_job(redis, job_id)
        if not job:
            return
        
        # 检查作业是否被停止
        if job.get("status") == "stopped":
            logger.info(f"作业 {job_id} 已被停止，取消处理")
            return
        
        logger.info(f"开始处理作业 {job_id}")
        
        # 检查是否有相同哈希值的已完成作业
        job_hash = job["job_hash"]
        existing_job_id = await JobRedisOperations.get_job_by_hash(redis, job_hash)
        
        if existing_job_id and existing_job_id != job_id:
            existing_job = await JobRedisOperations.get_job(redis, existing_job_id)
            if existing_job and existing_job.get("status") == "completed":
                # 更新当前作业为重复
                job["status"] = "repeated"
                job["repeated_job_id"] = existing_job_id
                job["update_time"] = get_current_time()
                await JobRedisOperations.save_job(redis, job_id, job)
                logger.info(f"作业 {job_id} 与已完成的作业 {existing_job_id} 重复，跳过处理")
                return
        
        # 在开始处理之前，先保存哈希值与作业ID的映射
        await JobRedisOperations.save_job_hash(redis, job_hash, job_id)
        
        # 更新作业状态为处理中
        job["status"] = "processing"
        job["update_time"] = get_current_time()
        await JobRedisOperations.save_job(redis, job_id, job)
        
        # 在生成播客的过程中，可以添加一些日志
        logger.info(f"正在生成播客，作业 ID: {job_id}")

        # 创建用于取消线程的事件
        cancel_event = threading.Event()

        # 将 cancel_event 传递给 generate_podcast 函数
        def run_generate_podcast():
            try:
                return generate_podcast(
                    urls=job["urls"],
                    transcript_file=job["transcript_file"],
                    tts_model=job["tts_model"],
                    transcript_only=job["transcript_only"],
                    config=job["config"],
                    conversation_config=job["conversation_config"],
                    text=job.get("text"),
                    job_id=job_id,
                    cancel_event=cancel_event
                )
            except Exception as e:
                logger.error(f"生成播客时发生错误: {str(e)}")
                return None  # 确保发生异常时也有返回值

        # 在线程池中运行 generate_podcast，并获取 Future 对象
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(
            thread_pool,
            run_generate_podcast
        )

        # 将任务的 Future 对象保存到 task_dict 中
        task_dict[job_id] = {
            "future": future,
            "cancel_event": cancel_event
        }

        # 等待任务完成并获取结果
        result = await future

        # 从 task_dict 中移除已完成的任务
        task_dict.pop(job_id, None)

        # 检查作业是否被停止
        job = await JobRedisOperations.get_job(redis, job_id)
        if job.get("status") == "stopped":
            logger.info(f"作业 {job_id} 已被停止，取消后续处理")
            return

        # 处理返回结果
        if isinstance(result, tuple):
            audio_file, text_file = result
            job["audio_file"] = audio_file
            job["text_file"] = text_file
        elif isinstance(result, str):
            audio_file = None
            text_file = result
            job["audio_file"] = None
            job["text_file"] = text_file
        else:
            logger.error(f"作业 {job_id} 未生成有效的结果")
            job["status"] = "failed"
            job["fail_reason"] = "未生成有效的结果"
            job["update_time"] = get_current_time()
            await JobRedisOperations.save_job(redis, job_id, job)
            return

        # 更新作业状态为完成，并保存文件路径
        job["status"] = "completed"
        job["update_time"] = get_current_time()
        await JobRedisOperations.save_job(redis, job_id, job)
        
        # 保存哈希值
        await JobRedisOperations.save_job_hash(redis, job_hash, job_id)
        
    except Exception as e:
        logger.error(f"处理作业 {job_id} 时发生异常: {str(e)}", exc_info=True)
        # 更新作业状态为失败，并保存错误信息
        job = await JobRedisOperations.get_job(redis, job_id)
        if job:
            job["status"] = "failed"
            job["fail_reason"] = str(e)
            job["update_time"] = get_current_time()
            await JobRedisOperations.save_job(redis, job_id, job)
    finally:
        # 根据配置决定是否清理临时文件
        if CLEANUP_ON_COMPLETE:
            temp_dir = os.path.join(TEMP_DIRECTORY, job_id)
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        
        if job_id in processing_jobs:
            processing_jobs.remove(job_id)
        # 检查是否等待中的作业可以开始
        await check_pending_jobs(redis)

async def start_job_processing(job_id: str, redis: aioredis.Redis):
    """开始处理作业"""
    job = await JobRedisOperations.get_job(redis, job_id)
    if job:
        job["status"] = "processing"
        job["update_time"] = get_current_time()
        await JobRedisOperations.save_job(redis, job_id, job)
        processing_jobs.append(job_id)
        # 启动实际作业处理
        asyncio.create_task(process_job(job_id, redis))

@check_cancelled_async
async def check_pending_jobs(redis: aioredis.Redis):
    """检查等待中的作业并开始处理"""
    while len(processing_jobs) < MAX_CONCURRENT_JOBS:
        # 查找等待中的作业
        waiting_jobs = []
        job_keys = await redis.keys(f"{JobRedisConfig.job_prefix}*")
        for key in job_keys:
            job_id = key.split(":")[-1]
            job = await JobRedisOperations.get_job(redis, job_id)
            if job and job["status"] == "waiting":
                waiting_jobs.append(job)

        if not waiting_jobs:
            break

        # 按照创建时间排序，优先处理最早的
        waiting_jobs.sort(key=lambda x: x["create_time"])
        next_job = waiting_jobs[0]
        await start_job_processing(next_job["job_id"], redis)

def is_url(path: str) -> bool:
    """
    判断一个路径是否为URL
    
    Args:
        path: 要判断的路径
    
    Returns:
        bool: 如果是URL返回True，否则返回False
    """
    url_patterns = ['http://', 'https://', 'ftp://', 'sftp://', 'www.']
    return any(pattern in path.lower() for pattern in url_patterns)

def compute_job_hash(urls: List[str], config: Optional[dict], conversation_config: Optional[dict], text: Optional[str] = None) -> str:
    """
    计算作业的哈希值，包含所有影响结果的参数，但排除与job_id相关的路径
    
    Args:
        urls: URL列表
        config: 配置参数
        conversation_config: 会话配置参数
        text: 文本内容
    
    Returns:
        str: 作业的MD5哈希值
    """
    try:
        # 处理URLs：区分网络URL和本地文件路径
        processed_urls = []
        for url in urls:
            if is_url(url):  # 如果是网络URL
                processed_urls.append(url)
            else:  # 如果是本地文件路径
                processed_urls.append(os.path.basename(url))
        
        # 处理conversation_config：移除与job_id相关的路径
        processed_conv_config = None
        if conversation_config:
            # 深拷贝以避免修改原始配置
            processed_conv_config = copy.deepcopy(conversation_config)
            
            # 如果存在text_to_speech配置，移除路径相关配置
            if isinstance(processed_conv_config, dict) and 'text_to_speech' in processed_conv_config:
                tts_config = processed_conv_config['text_to_speech']
                # 移除输出目录配置
                tts_config.pop('output_directories', None)
                tts_config.pop('temp_audio_dir', None)
        
        # 需要包含的参数整理为字典
        job_params = {
            'urls': sorted(processed_urls),  # 排序以确保顺序一致
            'config': config or {},
            'conversation_config': processed_conv_config or {},
            'text': text,  # 添加文本内容
        }
        
        # 将参数转换为JSON字符串，确保序列化后顺序一致
        job_content = json.dumps(job_params, sort_keys=True)
        job_hash = hashlib.md5(job_content.encode('utf-8')).hexdigest()
        logger.info(f"计算作业哈希值的参数: {job_params}")
        logger.info(f"计算作业哈希值: {job_hash}")
        return job_hash
        
    except Exception as e:
        logger.error(f"计算作业哈希值时发生错误: {str(e)}")
        # 在发生错误时返回一个唯一的哈希值，确保不会误判为重复作业
        return hashlib.md5(str(uuid.uuid4()).encode('utf-8')).hexdigest()

@app.post("/submit_job")
async def submit_job(
    url_list: Optional[List[str]] = [],
    files: List[UploadFile] = File(default=[]),
    transcript_file: Optional[UploadFile] = None,
    tts_model: Optional[TTSModelChoice] = None,
    transcript_only: bool = False,
    config: Optional[ConfigAll] = None,
    conversation_config: Optional[ConfigConversation] = None,
    text: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    redis: aioredis.Redis = Depends(get_redis_job)
):
    """接收用户上传的文件和URL列表，保存文件到服务器，并提交作业。"""
    try:
        # 生成作业ID
        job_id = generate_job_id()

        # 加载默认配置
        base_config = load_config()
        conv_config = load_conversation_config()

        # 配置 config
        if config:
            base_config.configure(config)

        # 配置 conversation_config
        if conversation_config:
            conv_config.configure(conversation_config)

        # 设置输出目录
        OUT_DIR_JOB = os.path.join(OUTPUT_DIRECTORY, job_id)
        os.makedirs(OUT_DIR_JOB, exist_ok=True)
        TMP_DIR_JOB = os.path.join(TEMP_DIRECTORY, job_id)
        os.makedirs(TMP_DIR_JOB, exist_ok=True)

        # 配置输出目录
        conv_config.configure({
            "text_to_speech": {
                "output_directories": {
                    "transcripts": OUT_DIR_JOB,
                    "audio": OUT_DIR_JOB
                },
                "temp_audio_dir": TMP_DIR_JOB
            }
        })

        # 保存上传的文件到临时目录
        file_paths = []
        for uploaded_file in files:
            # 检查文件扩展名
            file_ext = os.path.splitext(uploaded_file.filename)[1].lower()
            if file_ext not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"不支持的文件类型: {file_ext}。支持的类型: {', '.join(ALLOWED_EXTENSIONS)}"
                )
            
            # 检查文件大小
            content = await uploaded_file.read()
            file_size_mb = len(content) / (1024 * 1024)
            if file_size_mb > MAX_FILE_SIZE_MB:
                raise HTTPException(
                    status_code=400,
                    detail=f"文件过大。文件大小: {file_size_mb:.2f}MB，最大允许大小: {MAX_FILE_SIZE_MB}MB"
                )
            
            file_location = os.path.join(TMP_DIR_JOB, uploaded_file.filename)
            async with aiofiles.open(file_location, "wb") as f:
                await f.write(content)
            file_paths.append(file_location)
        
        # 合并文件路径和 URL 列表
        urls = file_paths + url_list

        # 计算作业哈希值，包含文本内容
        job_hash = compute_job_hash(urls, base_config.to_dict(), conv_config.to_dict(), text)

        # 准备作业信息
        job_info = {
            "job_id": job_id,
            "user_id": current_user.email,
            "status": "waiting",
            "create_time": get_current_time(),
            "update_time": get_current_time(),
            "job_hash": job_hash,
            "urls": urls,
            "transcript_file": transcript_file.filename if transcript_file else None,
            "tts_model": tts_model,
            "transcript_only": transcript_only,
            "config": base_config.to_dict(),
            "conversation_config": conv_config.to_dict(),
            "text": text,  # 添加文本内容到作业信息中
        }

        # 保存作业信息到 Redis
        await JobRedisOperations.save_job(redis, job_id, job_info, expire_days=JOB_EXPIRE_DAYS)
        await check_pending_jobs(redis)
        
        logger.info(f"正在处理提交的作业，用户ID: {current_user.email}")
        return {
            "job_id": job_id,
            "message": "作业已提交，正在等待处理。请使用 /jobs/{job_id} 查询作业状态。"
        }
        
    except Exception as e:
        logger.error(f"提交作业时发生错误: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"提交作业失败: {str(e)}"
        )

def format_job_info(job: dict) -> dict:
    """
    格式化作业信息，提取重要参数并返回标准化的作业信息字典
    
    Args:
        job: 原始作业信息字典
    
    Returns:
        dict: 格式化后的作业信息字典
    """
    try:
        # 获取配置信息，确保都有默认值
        config = job.get("config", {})
        conversation_config = job.get("conversation_config", {})
        
        # 提取TTS相关配置
        content_generator_config = config.get("content_generator", {})
        tts_config = conversation_config.get("text_to_speech", {})

        # 处理URLs：区分网络URL和本地文件路径
        processed_urls = []
        for url in job.get("urls", []):
            if is_url(url):  # 如果是网络URL
                processed_urls.append(url)
            else:  # 如果是本地文件路径
                processed_urls.append(os.path.basename(url))

        tts_model = job.get("tts_model") or tts_config.get("default_tts_model")
        
        # 构建基础响应
        formatted_info = {
            "job_id": job.get("job_id"),
            "status": job.get("status"),
            "create_time": job.get("create_time"),
            "update_time": job.get("update_time"),
            "urls": processed_urls,
            
            # TTS相关参数
            "tts_model": tts_model,
            "transcript_only": job.get("transcript_only", False),
            
            # 处理失败或重复的情况
            "fail_reason": job.get("fail_reason") if job.get("status") == "failed" else None,
            "repeated_job_id": job.get("repeated_job_id") if job.get("status") == "repeated" else None,
        }
        
        # 提取重要的内容生成配置参数
        important_config = {
            "llm_model": content_generator_config.get("llm_model") or content_generator_config.get("gemini_model"),
            "max_output_tokens": content_generator_config.get("max_output_tokens"),
            "word_count": content_generator_config.get("word_count"),
        }
        
        # 提取重要的会话配置参数
        important_conv_config = {
            # 基本配置
            "conversation_style": conversation_config.get("conversation_style"),
            "dialogue_structure": conversation_config.get("dialogue_structure"),
            "output_language": conversation_config.get("output_language"),
            "creativity": conversation_config.get("creativity"),
            
            # TTS相关详细配置
            "voice_config": {
                "model": tts_model,
                "voices": tts_config.get(f"{tts_model}", {}).get("default_voices", {}),
                "audio_format": tts_config.get("audio_format", "mp3"),
                "podcast_name": conversation_config.get("podcast_name"),
                "podcast_tagline": conversation_config.get("podcast_tagline"),
                "ending_message": tts_config.get("ending_message", "Bye Bye!"),
            } if tts_model else {},
        }

        # 添加配置参数到响应中，移除所有None值
        formatted_info["config"] = {k: v for k, v in important_config.items() if v is not None}
        formatted_info["conversation_config"] = {k: v for k, v in important_conv_config.items() if v is not None}

        # 如果formatted_info某个键的值为None，则从formatted_info中移除该键
        formatted_info = {k: v for k, v in formatted_info.items() if v}
        
        return formatted_info
    except Exception as e:
        logger.error(f"格式化作业信息时发生错误: {str(e)}")
        # 返回基本信息
        return {
            "job_id": job.get("job_id"),
            "status": job.get("status"),
            "error": f"格式化作业信息时发生错误: {str(e)}"
        }

@app.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_active_user),
    redis: aioredis.Redis = Depends(get_redis_job)
):
    job = await JobRedisOperations.get_job(redis, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="作业不存在")

    # 检查作业是否属于当前用户
    if job["user_id"] != current_user.email:
        raise HTTPException(status_code=403, detail="无权访问此作业")

    return format_job_info(job)

@app.get("/jobs")
async def list_jobs(
    status: Optional[str] = None,
    time_range: Optional[int] = 60,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_active_user),
    redis: aioredis.Redis = Depends(get_redis_job)
):
    """列出当前用户的作业，默认返回最近 time_range 分钟内的作业"""
    # 获取当前时间和起始时间
    end_time = datetime.fromisoformat(get_current_time())
    start_time = end_time - timedelta(minutes=time_range)

    # 从 Redis 中获取所有作业
    job_keys = await redis.keys(f"{JobRedisConfig.job_prefix}*")

    jobs = []
    for key in job_keys:
        job_id = key.split(":")[-1]  # 获取作业ID
        job_data = await JobRedisOperations.get_job(redis, job_id)
        if job_data and isinstance(job_data, dict):  # 确保 job_data 是字典类型
            if job_data.get("user_id") == current_user.email:  # 只获取当前用户的作业
                # 如果指定了状态，则只返回该状态的作业
                if status is None or job_data.get("status") == status:
                    create_time = datetime.fromisoformat(job_data.get("create_time", ""))
                    if start_time <= create_time <= end_time:
                        jobs.append(job_data)

    # 按创建时间顺序排列
    jobs.sort(key=lambda x: x.get("create_time", ""), reverse=False)

    # 分页
    total_jobs = len(jobs)
    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    paginated_jobs = jobs[start_index:end_index]

    # 使用format_job_info格式化每个作业信息
    formatted_jobs = [format_job_info(job) for job in paginated_jobs]

    # 构建响应
    response = {
        "user_id": current_user.email,
        "total_jobs": total_jobs,
        "page": page,
        "page_size": page_size,
        "jobs": formatted_jobs,
        "queue_status": {
            "max_concurrent_jobs": MAX_CONCURRENT_JOBS,
            "current_processing": len(processing_jobs),
            "processing_jobs": processing_jobs
        }
    }

    return response

async def stop_running_job(job_id: str):
    """停止正在运行的作业"""
    task_info = task_dict.get(job_id)
    if task_info:
        # 设置取消事件
        task_info["cancel_event"].set()
        # 取消 Future 对象
        task_info["future"].cancel()
        logger.info(f"已请求停止作业 {job_id}")
    else:
        logger.info(f"作业 {job_id} 不在运行中或已完成")

@app.post("/jobs/stop")
async def stop_jobs(
    job_ids: List[str], 
    current_user: User = Depends(get_current_active_user),
    redis: aioredis.Redis = Depends(get_redis_job)
):
    stopped_jobs = []
    failed_jobs = []
    for job_id in job_ids:
        job = await JobRedisOperations.get_job(redis, job_id)
        if not job:
            failed_jobs.append(job_id)
            continue

        # 检查作业是否属于当前用户
        if job["user_id"] != current_user.email:
            failed_jobs.append(job_id)
            continue

        if job.get("status") in ["completed", "failed", "stopped"]:
            failed_jobs.append(job_id)
            continue

        # 更新作业状态为 "stopped"
        job["status"] = "stopped"
        job["update_time"] = get_current_time()
        await JobRedisOperations.save_job(redis, job_id, job)

        # 停止正在运行的任务
        await stop_running_job(job_id)

        stopped_jobs.append(job_id)

    response = {
        "stopped_jobs": stopped_jobs,
        "failed_jobs": failed_jobs,
        "message": f"成功停止 {len(stopped_jobs)} 个作业，{len(failed_jobs)} 个作业无法停止。"
    }
    return response

@app.get("/jobs/{job_id}/download/audio")
async def download_audio_file(
    job_id: str,
    current_user: User = Depends(get_current_active_user),
    redis: aioredis.Redis = Depends(get_redis_job)
):
    job = await JobRedisOperations.get_job(redis, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="作业不存在")

    # 检查作业是否属于当前用户
    if job["user_id"] != current_user.email:
        raise HTTPException(status_code=403, detail="无权访问此作业")

    # 如果是重复作业，获取原始作业的信息
    original_job_id = None
    if job["status"] == "repeated" and "repeated_job_id" in job:
        original_job = await JobRedisOperations.get_job(redis, job["repeated_job_id"])
        if original_job and original_job["status"] == "completed":
            original_job_id = original_job["job_id"]
            job = original_job
        else:
            raise HTTPException(status_code=404, detail="原始作业未找到或未完成")
    elif job["status"] != "completed":
        raise HTTPException(status_code=400, detail="作业未完成")

    audio_file = job.get("audio_file")
    if not audio_file or not os.path.exists(audio_file):
        raise HTTPException(status_code=404, detail="音频文件未找到")

    # 如果是重复作业，替换文件名中的作业ID
    filename = os.path.basename(audio_file)
    if original_job_id:
        filename = filename.replace(original_job_id, job_id)

    return FileResponse(audio_file, media_type='audio/mpeg', filename=filename)

@app.get("/jobs/{job_id}/download/text")
async def download_text_file(
    job_id: str,
    current_user: User = Depends(get_current_active_user),
    redis: aioredis.Redis = Depends(get_redis_job)
):
    job = await JobRedisOperations.get_job(redis, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="作业不存在")

    # 检查作业是否属于当前用户
    if job["user_id"] != current_user.email:
        raise HTTPException(status_code=403, detail="无权访问此作业")

    # 如果是重复作业，获取原始作业的信息
    original_job_id = None
    if job["status"] == "repeated" and "repeated_job_id" in job:
        original_job = await JobRedisOperations.get_job(redis, job["repeated_job_id"])
        if original_job and original_job["status"] == "completed":
            original_job_id = original_job["job_id"]
            job = original_job
        else:
            raise HTTPException(status_code=404, detail="原始作业未找到或未完成")
    elif job["status"] != "completed":
        raise HTTPException(status_code=400, detail="作业未完成")

    text_file = job.get("text_file")
    if not text_file or not os.path.exists(text_file):
        raise HTTPException(status_code=404, detail="文本文件未找到")

    # 如果是重复作业，替换文件名中的作业ID
    filename = os.path.basename(text_file)
    if original_job_id:
        filename = filename.replace(original_job_id, job_id)

    return FileResponse(text_file, media_type='text/plain', filename=filename)

@app.api_route("/jobs/clear", methods=["DELETE", "POST"])
async def clear_jobs(
    before_days: Optional[int] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    redis: aioredis.Redis = Depends(get_redis_job)
):
    """
    清除历史作业记录
    
    Args:
        before_days: 清除多少天前的记录，如果不指定则清除所有记录
        status: 指定要清除的作业状态，如果不指定则清除所有状态
    """
    try:
        # 获取当前时间
        current_time = get_current_time()
        
        # 计算截止时间
        cutoff_time = None
        if before_days is not None:
            cutoff_time = datetime.fromisoformat(current_time) - timedelta(days=before_days)
        
        # 获取所有作业键
        job_keys = await redis.keys(f"{JobRedisConfig.job_prefix}*")
        
        deleted_count = 0
        skipped_count = 0
        
        for key in job_keys:
            job_id = key.split(":")[-1]
            job_data = await JobRedisOperations.get_job(redis, job_id)
            
            # 只处理当前用户的作业
            if not job_data or job_data.get("user_id") != current_user.email:
                continue
                
            # 检查作业状态
            if status and job_data.get("status") != status:
                continue
                
            # 检查时间
            if cutoff_time:
                job_time = datetime.fromisoformat(job_data.get("create_time", ""))
                if job_time > cutoff_time:
                    skipped_count += 1
                    continue
            
            # 如果作业正在处理中，跳过
            if job_data.get("status") == "processing" and job_id in processing_jobs:
                skipped_count += 1
                continue
                
            # 删除作业记录
            await redis.delete(key)
            
            # 如果有对应的哈希值记录，也删除
            job_hash = job_data.get("job_hash")
            if job_hash:
                hash_key = f"{JobRedisConfig.job_hash_prefix}{job_hash}"
                await redis.delete(hash_key)
                
            # 清理相关文件
            if CLEANUP_ON_COMPLETE:
                # 清理临时目录
                temp_dir = os.path.join(TEMP_DIRECTORY, job_id)
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                
                # 清理结果文件
                for file_path in [job_data.get("audio_file"), job_data.get("text_file")]:
                    if file_path and os.path.exists(file_path):
                        os.remove(file_path)
            
            deleted_count += 1
        
        return {
            "message": "清理完成",
            "deleted_count": deleted_count,
            "skipped_count": skipped_count
        }
        
    except Exception as e:
        logger.error(f"清理作业记录时发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"清理作业记录失败: {str(e)}")

# 加载邀请列表
def get_invitation_emails():
    invitation_list_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'invitation_list.yaml')
    with open(invitation_list_path, 'r') as f:
        return yaml.safe_load(f)

# 新增注册接口
@app.post("/register")
async def register(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    用户注册
    
    Args:
        form_data: 包含用户名(邮箱)和密码的表单数据
        
    Returns:
        注册成功的消息
        
    Raises:
        HTTPException: 当注册失败时
    """
    invitation_emails = get_invitation_emails()
    if form_data.username not in invitation_emails:
        raise HTTPException(
            status_code=400, 
            detail="您的邮箱不在邀请列表中，无法注册"
        )
        
    existing_user = await get_user(form_data.username)
    if existing_user:
        raise HTTPException(
            status_code=400, 
            detail="用户已存在"
        )
        
    # 验证密码复杂度
    is_valid, error_msg = validate_password(form_data.password)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail=error_msg
        )
        
    password_hash = await get_password_hash(form_data.password)
    await create_user(form_data.username, password_hash)
    return {"message": "注册成功"}

# 新增登录接口，获取 JWT 令牌
@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    try:
        user = await authenticate_user(form_data.username, form_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="用户名或密码错误"
            )
        access_token = create_access_token(data={"sub": user.email})
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        logger.error(f"登录失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登录过程中发生错误"
        )

# 添加更改密码的端点
@app.post("/change-password")
async def change_password(
    old_password: str,
    new_password: str,
    current_user: User = Depends(get_current_active_user),
    redis: aioredis.Redis = Depends(get_redis_user)
):
    # 验证旧密码
    if not await verify_password(old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="旧密码错误"
        )
    
    # 验证新密码复杂度
    is_valid, error_msg = validate_password(new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    # 生成新密码的哈希值
    new_password_hash = await get_password_hash(new_password)
    
    # 更新用户密码
    current_user.password_hash = new_password_hash
    await redis.hmset(
        f"user:{current_user.email}",
        current_user.model_dump()
    )
    
    return {"message": "密码修改成功"}

@app.get("/users/me", response_model=dict)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """
    获取当前登录用户的信息
    
    通过 JWT token 获取当前用户的基本信息，不包含敏感数据如密码哈希等
    """
    return {
        "email": current_user.email,
        "is_active": current_user.is_active,
        "is_admin": current_user.is_admin
    }

@app.get("/users", response_model=List[dict])
async def list_users(current_user: User = Depends(get_current_admin_user)):
    """
    获取所有用户列表
    
    需要管理员权限
    """
    try:
        users = await get_all_users()
        return users
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取用户列表失败: {str(e)}"
        )

@app.delete("/users/{email}")
async def remove_user(
    email: str,
    current_user: User = Depends(get_current_admin_user)
):
    """
    删除指定用户
    
    需要管理员权限
    """
    # 不允许删除自己
    if email == current_user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除当前登录用户"
        )
    
    try:
        success = await delete_user(email)
        if success:
            return {"message": f"用户 {email} 已成功删除"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"用户 {email} 不存在"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除用户失败: {str(e)}"
        )

@app.put("/admin/users/{email}/admin-status")
async def set_user_admin_status(
    email: str,
    make_admin: bool = True,
    admin_key: str = Depends(verify_admin_key),
    redis: aioredis.Redis = Depends(get_redis_user)
):
    """
    设置用户的管理员状态
    
    需要管理员 API Key
    """
    try:
        # 获取用户数据
        user_key = f"user:{email}"
        user_data = await redis.hgetall(user_key)
        
        if not user_data:
            raise HTTPException(
                status_code=404,
                detail=f"用户 {email} 不存在"
            )
            
        # 更新管理员状态
        user_data["is_admin"] = str(make_admin).lower()
        
        # 保存更新后的用户数据
        for key, value in user_data.items():
            await redis.hset(user_key, key, value)
            
        action = "设置为管理员" if make_admin else "取消管理员权限"
        return {"message": f"用户 {email} 已成功{action}"}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"设置管理员状态失败: {str(e)}"
        )

@app.get("/admin/users")
async def list_all_users(
    admin_key: str = Depends(verify_admin_key),
    redis: aioredis.Redis = Depends(get_redis_user)
):
    """
    获取所有用户列表
    
    需要管理员 API Key
    """
    try:
        users = await get_all_users()
        return users
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取用户列表失败: {str(e)}"
        )