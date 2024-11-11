"""API configuration module."""

import os
import yaml
from typing import Dict, Any

# 加载 api_config.yaml
api_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'api_config.yaml')
with open(api_config_path, 'r') as f:
    api_config = yaml.safe_load(f)

# 作业处理相关配置
MAX_CONCURRENT_JOBS = api_config['job_processing']['max_concurrent_jobs']
TEMP_DIRECTORY = api_config['job_processing']['temp_directory']
OUTPUT_DIRECTORY = api_config['job_processing']['output_directory']
JOB_EXPIRE_DAYS = api_config['job_processing']['job_expire_days']

# Redis 相关配置
REDIS_URL = api_config['redis']['url']
JOB_PREFIX = api_config['redis']['prefix']['job']
JOB_HASH_PREFIX = api_config['redis']['prefix']['job_hash']

# 文件处理配置
ALLOWED_EXTENSIONS = api_config['file_handling']['allowed_extensions']
MAX_FILE_SIZE_MB = api_config['file_handling']['max_file_size_mb']
CLEANUP_ON_COMPLETE = api_config['file_handling']['cleanup_on_complete']

# API TEST 相关配置
API_TEST_BASE_URL = api_config['api_test']['base_url']
API_TEST_TIMEOUT = api_config['api_test']['timeout']