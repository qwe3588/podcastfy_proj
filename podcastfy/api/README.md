# Podcastfy API

该目录包含了 API 服务的主要实现，包括用户认证、作业提交与管理等功能。

## 目录结构

```
api/
├── __init__.py           # API 包初始化文件
├── api_service.py        # FastAPI 服务主入口
├── models/               # 数据模型定义
│   ├── __init__.py
│   ├── config_models.py  # 配置相关模型
│   └── job_models.py     # 作业相关模型
├── utils/                # 工具函数
│   ├── __init__.py
│   ├── auth.py           # 认证相关工具
│   └── utils.py          # 通用工具函数
├── output_files/         # 输出文件目录
│   └── ...               # 作业生成的音频和文本文件
```

## 简介

Podcastfy API 是基于 FastAPI 框架开发的播客生成服务，提供用户注册、登录、作业提交、查询和下载等功能。

## 标准工作流程

1. **用户注册**：新用户通过 `/register` 接口进行注册，需使用受邀的邮箱。
2. **用户登录**：注册成功后，通过 `/login` 获取访问令牌（JWT）。
3. **提交作业**：使用访问令牌，通过 `/submit_job` 提交新的播客生成作业。
4. **查询作业状态**：通过 `/jobs/{job_id}` 查询特定作业状态，或 `/jobs` 获取作业列表。
5. **下载结果文件**：当作业完成后，可通过 `/jobs/{job_id}/download/audio` 和 `/jobs/{job_id}/download/text` 下载音频和文本文件。
6. **管理作业**：可使用 `/jobs/stop` 停止作业，或 `/jobs/clear` 清理历史作业。
7. **用户管理**：可修改密码 `/change-password`，管理员可管理用户。

## API 接口说明

### 用户管理

#### 1. 注册新用户

**POST `/register`**

**描述**：用户注册，需要使用被邀请的邮箱。

**请求参数**：

- `username`：用户邮箱。
- `password`：密码，需满足复杂度要求。

**示例**：

  ```bash
  curl -X POST "http://localhost:8000/register" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=user@example.com&password=YourPassword123!"
  ```

#### 2. 用户登录

**POST `/login`**

**描述**：用户登录，获取访问令牌。

**请求参数**：

- `username`：用户邮箱。
- `password`：密码。

**示例**：

  ```bash
  curl -X POST "http://localhost:8000/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=user@example.com&password=YourPassword123!"
  ```

**响应示例**：

  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR...",
    "token_type": "bearer"
  }
  ```

#### 3. 修改密码

**POST `/change-password`**

**描述**：用户修改密码。

**请求头**：

- `Authorization: Bearer {access_token}`

**请求参数**：

- `old_password`：旧密码。
- `new_password`：新密码，需满足复杂度要求。

**示例**：

  ```bash
  curl -X POST "http://localhost:8000/change-password" \
    -H "Authorization: Bearer {access_token}" \
    -H "Content-Type: application/json" \
    -d '{"old_password": "YourOldPassword123!", "new_password": "YourNewPassword456#"}'
  ```

#### 4. 获取当前用户信息

**GET `/users/me`**

**描述**：获取当前登录用户的信息。

**请求头**：

- `Authorization: Bearer {access_token}`

**示例**：

  ```bash
  curl -X GET "http://localhost:8000/users/me" \
    -H "Authorization: Bearer {access_token}"
  ```

### 作业管理

#### 1. 提交新作业

**POST `/submit_job`**

**描述**：提交新的播客生成作业。

**请求头**：

- `Authorization: Bearer {access_token}`

**请求参数**：

- `url_list`：待处理的 URL 列表（可选）。
- `files`：上传的文件（可选）。
- `transcript_file`：转录文件（可选）。
- `tts_model`：指定 TTS 模型（可选）。
- `transcript_only`：仅生成转录（可选）。
- `config`：配置参数（可选）。
- `conversation_config`：会话配置参数（可选）。
- `text`：直接提供的文本内容（可选）。

**示例**：

  ```bash
  curl -X POST "http://localhost:8000/submit_job" \
    -H "Authorization: Bearer {access_token}" \
    -F "url_list=https://example.com/article1" \
    -F "files=@/path/to/file.pdf" \
    -F "text=这是直接提供的文本内容。"
  ```

**响应示例**：

  ```json
  {
    "job_id": "123e4567-e89b-12d3-a456-426614174000",
    "message": "作业已提交，正在等待处理。请使用 /jobs/{job_id} 查询作业状态。"
  }
  ```

#### 2. 查询作业状态

**GET `/jobs/{job_id}`**

**描述**：获取指定作业的状态信息。

**请求头**：

- `Authorization: Bearer {access_token}`

**路径参数**：

- `job_id`：作业 ID。

**示例**：

  ```bash
  curl -X GET "http://localhost:8000/jobs/123e4567-e89b-12d3-a456-426614174000" \
    -H "Authorization: Bearer {access_token}"
  ```

**响应示例**：

  ```json
  {
    "job_id": "123e4567-e89b-12d3-a456-426614174000",
    "status": "processing",
    "create_time": "2023-10-18 10:00:00 +0800",
    "update_time": "2023-10-18 10:05:00 +0800",
    "urls": ["https://example.com/article1"],
    "tts_model": "elevenlabs",
    "config": {
      "llm_model": "gpt-3.5-turbo",
      "max_output_tokens": 1000
    },
    "conversation_config": {
      "conversation_style": ["informative", "engaging"],
      "voice_config": {
        "model": "elevenlabs",
        "voices": {
          "question": "Voice1",
          "answer": "Voice2"
        },
        "audio_format": "mp3",
        "podcast_name": "My Podcast",
        "podcast_tagline": "Exploring AI",
        "ending_message": "Thanks for listening!"
      }
    }
  }
  ```

#### 3. 列出作业

**GET `/jobs`**

**描述**：列出当前用户的作业。

**请求头**：

- `Authorization: Bearer {access_token}`

**查询参数**：

- `status`：过滤指定状态的作业（可选，如 `completed`、`processing`）。
- `time_range`：查询多少分钟内的作业，默认 60（可选）。
- `page`：页码，默认 1（可选）。
- `page_size`：每页数量，默认 20（可选）。

**示例**：

  ```bash
  curl -X GET "http://localhost:8000/jobs?status=completed&time_range=120" \
    -H "Authorization: Bearer {access_token}"
  ```

#### 4. 停止作业

**POST `/jobs/stop`**

**描述**：停止指定的作业。

**请求头**：

- `Authorization: Bearer {access_token}`

**请求参数**：

- `job_ids`：要停止的作业 ID 列表。

**示例**：

  ```bash
  curl -X POST "http://localhost:8000/jobs/stop" \
    -H "Authorization: Bearer {access_token}" \
    -H "Content-Type: application/json" \
    -d '{"job_ids": ["123e4567-e89b-12d3-a456-426614174000"]}'
  ```

#### 5. 下载音频文件

**GET `/jobs/{job_id}/download/audio`**

**描述**：下载指定作业的音频文件。

**请求头**：

- `Authorization: Bearer {access_token}`

**路径参数**：

- `job_id`：作业 ID。

**示例**：

  ```bash
  curl -X GET "http://localhost:8000/jobs/123e4567-e89b-12d3-a456-426614174000/download/audio" \
    -H "Authorization: Bearer {access_token}" \
    -o "output_audio.mp3"
  ```

#### 6. 下载文本文件

**GET `/jobs/{job_id}/download/text`**

**描述**：下载指定作业的文本文件。

**请求头**：

- `Authorization: Bearer {access_token}`

**路径参数**：

- `job_id`：作业 ID。

**示例**：

  ```bash
  curl -X GET "http://localhost:8000/jobs/123e4567-e89b-12d3-a456-426614174000/download/text" \
    -H "Authorization: Bearer {access_token}" \
    -o "output_text.txt"
  ```

#### 7. 清理历史作业

**DELETE `/jobs/clear`**

**描述**：清理历史作业记录。

**请求头**：

- `Authorization: Bearer {access_token}`

**查询参数**：

- `before_days`：清理多少天前的记录（可选）。
- `status`：指定要清理的作业状态（可选）。

**示例**：

  ```bash
  curl -X DELETE "http://localhost:8000/jobs/clear?before_days=7&status=completed" \
    -H "Authorization: Bearer {access_token}"
  ```

### 管理员功能

#### 1. 获取所有用户列表

**GET `/admin/users`**

**描述**：获取所有用户列表。

**请求参数**：

- `admin_key`：管理员 API 密钥。

**示例**：

  ```bash
  curl -X GET "http://localhost:8000/admin/users?admin_key=YourAdminAPIKey"
  ```

#### 2. 设置用户管理员状态

**PUT `/admin/users/{email}/admin-status`**

**描述**：设置指定用户的管理员状态。

**请求参数**：

- `admin_key`：管理员 API 密钥。
- `make_admin`：是否设置为管理员，默认 `true`（可选）。

**路径参数**：

- `email`：用户邮箱。

**示例**：

  ```bash
  curl -X PUT "http://localhost:8000/admin/users/user@example.com/admin-status?admin_key=YourAdminAPIKey&make_admin=true"
  ```

## 使用指南

### 环境配置

1. 确保 Redis 服务正常运行。
2. 设置必要的环境变量：
   - `AUTH_SECRET_KEY`：JWT 密钥。
   - `ADMIN_API_KEY`：管理员 API 密钥。
   - `REDIS_URL`：Redis 连接 URL。

### 开发指南

1. 所有新接口应包含适当的权限验证。
2. 使用 `get_current_active_user` 进行用户认证。
3. 管理员功能使用 `get_current_admin_user`。
4. 文件操作需考虑清理机制。

### 安全建议

1. 定期更新 JWT 密钥。
2. 监控异常登录行为。
3. 定期清理过期数据。
4. 限制上传文件的大小和类型。

## 注意事项

- 所有需要认证的接口，均需在请求头中添加 `Authorization: Bearer {access_token}`。
- 密码需满足复杂度要求：至少8位，包括大小写字母、数字和特殊字符。
- 管理员功能需提供有效的 `admin_key`。
- 作业提交后，可通过作业 ID 查询状态，完成后可下载结果文件。