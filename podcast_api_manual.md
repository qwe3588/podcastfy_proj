# AudioBook AI API 使用手册

欢迎使用 **AudioBook AI** API，这是一个基于 FastAPI 框架开发的播客生成服务。该 API 提供了用户注册、登录、作业提交、查询、下载和管理等一系列功能，可以用来生成个性化的播客内容。

## 目录

- [API 简介](#api-简介)
- [快速开始](#快速开始)
  - [环境配置](#环境配置)
  - [基本使用流程](#基本使用流程)
- [API 接口详细说明](#api-接口详细说明)
  - [用户管理](#用户管理)
    - [注册新用户](#1-注册新用户)
    - [用户登录](#2-用户登录)
    - [修改密码](#3-修改密码)
    - [获取当前用户信息](#4-获取当前用户信息)
  - [作业管理](#作业管理)
    - [提交新作业](#1-提交新作业)
    - [查询作业状态](#2-查询作业状态)
    - [列出作业](#3-列出作业)
    - [停止作业](#4-停止作业)
    - [下载音频文件](#5-下载音频文件)
    - [下载文本文件](#6-下载文本文件)
    - [清理历史作业](#7-清理历史作业)
  - [管理员功能](#管理员功能)
    - [获取所有用户列表](#1-获取所有用户列表)
    - [设置用户管理员状态](#2-设置用户管理员状态)
- [作业参数详解](#作业参数详解)
  - [配置参数 `config` 说明](#配置参数-config-说明)
  - [会话配置参数 `conversation_config` 说明](#会话配置参数-conversation_config-说明)
- [附录](#附录)
  - [完整配置文件示例](#完整配置文件示例)
- [常见问题与支持](#常见问题与支持)

---

## API 简介

Podcastfy API 提供了一套强大的接口，允许用户提交带有指定配置的播客生成作业。通过提交文本、URL 或文件，用户可以生成个性化的播客音频和转录文本。

Base URL：
```
https://audioai.alphalio.cn/api
```

请在所有请求中使用 HTTPS，并确保请求地址以 `/api` 开头。

---

## 快速开始

### 环境配置

1. **确保网络可用**：访问 `https://audioai.alphalio.cn`。

2. **准备工具**：建议使用 `curl` 或 Postman 等工具测试 API。

### 基本使用流程

1. **用户注册**：通过 `/register` 接口注册新用户。

2. **用户登录**：使用 `/login` 接口获取访问令牌（JWT）。

3. **提交作业**：使用访问令牌，通过 `/submit_job` 提交新的播客生成作业，提供文本、URL 或文件，以及配置参数。

4. **查询作业状态**：通过 `/jobs/{job_id}` 查询特定作业状态，或 `/jobs` 获取作业列表。

5. **下载结果文件**：当作业完成后，可通过 `/jobs/{job_id}/download/audio` 和 `/jobs/{job_id}/download/text` 下载音频和文本文件。

6. **管理作业**：可使用 `/jobs/stop` 停止作业，或 `/jobs/clear` 清理历史作业。

---

## API 接口详细说明

### 用户管理

#### 1. 注册新用户

**POST `/register`**

**描述**：用户注册，需要使用**被邀请**的邮箱。

**请求参数**：

- `username`：用户邮箱。
- `password`：密码，需满足复杂度要求（至少8位，包括大小写字母、数字和特殊字符）。

**示例**：
```bash
curl -X POST "https://audioai.alphalio.cn/api/register" \
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
curl -X POST "https://audioai.alphalio.cn/api/login" \
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
curl -X POST "https://audioai.alphalio.cn/api/change-password" \
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
curl -X GET "https://audioai.alphalio.cn/api/users/me" \
-H "Authorization: Bearer {access_token}"
```

---

### 作业管理

#### 1. 提交新作业

**POST `/submit_job`**

**描述**：提交新的播客生成作业。

**请求头**：

- `Authorization: Bearer {access_token}`

**请求参数**：

- `url_list`：待处理的 URL 列表（可选，列表类型）。
- `files`：上传的文件（可选，用于上传 PDF、DOCX 等文件）。
- `transcript_file`：转录文件（可选，上传已存在的转录文本文件）。
- `tts_model`：指定 TTS 模型（可选，默认根据配置文件，暂时仅支持openai）。
- `transcript_only`：仅生成转录（可选，布尔值）。
- `config`：配置参数（可选，JSON 格式的字符串，详见下文）。
- `conversation_config`：会话配置参数（可选，JSON 格式的字符串，详见下文）。
- `text`：直接提供的文本内容（可选，字符串）。

**注意**：

- 所有参数均为可选，但至少需要提供 `url_list`、`files`、`text` 或 `transcript_file` 之一。
- `config` 和 `conversation_config` 可以自定义，未提供时使用默认配置。

**示例**：
```bash
curl -X POST "https://audioai.alphalio.cn/api/submit_job" \
-H "Authorization: Bearer {access_token}" \
-F "url_list=https://example.com/article1" \
-F "files=@/path/to/file.pdf" \
-F "text=这是直接提供的文本内容。" \
-F "tts_model=openai" \
-F "transcript_only=false"
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
curl -X GET "https://audioai.alphalio.cn/api/jobs/123e4567-e89b-12d3-a456-426614174000" \
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
"transcript_only": false,
"config": {
"llm_model": "gpt-3.5-turbo",
"max_output_tokens": 1000,
"word_count": 2000
},
"conversation_config": {
"conversation_style": ["engaging", "informative"],
"dialogue_structure": ["Introduction", "Main Content", "Conclusion"],
"output_language": "English",
"creativity": 1,
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
curl -X GET "https://audioai.alphalio.cn/api/jobs?status=completed&time_range=120" \
-H "Authorization: Bearer {access_token}"
```

#### 4. 停止作业

**POST `/jobs/stop`**

**描述**：停止指定的作业。

**请求头**：

- `Authorization: Bearer {access_token}`

**请求参数**：

- `job_ids`：要停止的作业 ID 列表（JSON 格式的数组）。

**示例**：
```bash
curl -X POST "https://audioai.alphalio.cn/api/jobs/stop" \
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
curl -X GET "https://audioai.alphalio.cn/api/jobs/123e4567-e89b-12d3-a456-426614174000/download/audio" \
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
curl -X GET "https://audioai.alphalio.cn/api/jobs/123e4567-e89b-12d3-a456-426614174000/download/text" \
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
curl -X DELETE "https://audioai.alphalio.cn/api/jobs/clear?before_days=7&status=completed" \
-H "Authorization: Bearer {access_token}"
```

---

### 管理员功能

#### 1. 获取所有用户列表

**GET `/admin/users`**

**描述**：获取所有用户列表。

**请求参数**：

- `admin_key`：管理员 API 密钥。

**示例**：
```bash
curl -X GET "https://audioai.alphalio.cn/api/admin/users?admin_key=YourAdminAPIKey"
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
curl -X PUT "https://audioai.alphalio.cn/api/admin/users/user@example.com/admin-status?admin_key=YourAdminAPIKey&make_admin=true"
```

---

## 作业参数详解

在提交作业时，您可以通过 `config` 和 `conversation_config` 参数自定义作业的生成方式。这些参数允许您精细控制内容生成和语音合成的细节。

### 配置参数 `config` 说明

`config` 参数用于配置内容生成器和内容提取器的行为，以下是详细说明：

- **content_generator**（内容生成器）：
  - `llm_model`：指定使用的语言模型，如 `gpt-3.5-turbo`、`gpt-4` 等。
  - `gemini_model`：指定 Gemini 模型版本。
  - `max_output_tokens`：生成内容的最大字数。
  - `prompt_template`：提示模板，用于生成内容的初始提示。
  - `prompt_commit`：提示模板的具体版本或提交哈希值。

- **content_extractor**（内容提取器）：
  - `youtube_url_patterns`：指定支持的 YouTube URL 模式列表。

**示例**：
```json
{
"content_generator": {
"llm_model": "gpt-4",
"gemini_model": "gemini-1.5-pro-latest",
"max_output_tokens": 1024,
"prompt_template": "custom_template",
"prompt_commit": "abcdef123456"
},
"content_extractor": {
"youtube_url_patterns": ["youtube.com", "youtu.be"]
}
}
```

### 会话配置参数 `conversation_config` 说明

`conversation_config` 参数用于配置对话的风格、结构以及语音合成的细节，以下是详细说明：

- `word_count`：生成内容的总字数。
- `conversation_style`：对话风格，可包含多个描述性词语，如 `"engaging"`、`"informative"`。
- `roles_person1`：第一位发言者的角色定位。
- `roles_person2`：第二位发言者的角色定位。
- `dialogue_structure`：对话的结构，如 `["Introduction", "Main Content", "Conclusion"]`。
- `podcast_name`：播客的名称。
- `podcast_tagline`：播客的标语。
- `output_language`：输出语言。
- `engagement_techniques`：增强对话吸引力的技巧，如 `"humor"`、`"anecdotes"`。
- `creativity`：内容生成的创造力等级，通常为 0 到 1 之间的浮点数。
- `user_instructions`：用户的特殊指令。

- **text_to_speech**（语音合成配置）：
  - `default_tts_model`：默认使用的 TTS 模型，如 `"openai"`、`"elevenlabs"`。
  - `output_directories`：输出文件目录设置。
    - `transcripts`：转录文本的输出目录。
    - `audio`：音频文件的输出目录。
  - `audio_format`：输出音频文件的格式，如 `"mp3"`。
  - `ending_message`：音频结尾时的消息，如 `"Thanks for listening!"`。
  - 各 TTS 模型的特定配置，例如：
    - `elevenlabs`：
      - `default_voices`：默认使用的声音配置。
        - `question`：提问者的声音。
        - `answer`：回答者的声音。
      - `model`：指定的模型版本。

**示例**：
```json
{
"word_count": 2000,
"conversation_style": ["engaging", "fast-paced", "enthusiastic"],
"roles_person1": "main summarizer",
"roles_person2": "questioner/clarifier",
"dialogue_structure": ["Introduction", "Main Content Summary", "Conclusion"],
"podcast_name": "PODCASTFY",
"podcast_tagline": "Your Personal Generative AI Podcast",
"output_language": "English",
"engagement_techniques": ["rhetorical questions", "anecdotes", "humor"],
"creativity": 1,
"user_instructions": "",
"text_to_speech": {
"default_tts_model": "elevenlabs",
"output_directories": {
"transcripts": "./data/transcripts",
"audio": "./data/audio"
},
"audio_format": "mp3",
"ending_message": "Thanks for listening!",
"elevenlabs": {
"default_voices": {
"question": "Chris",
"answer": "Jessica"
},
"model": "eleven_multilingual_v2"
}
}
}
```

---

## 附录

### 完整配置文件示例

以下是完整的 `config.yaml` 和 `conversation_config.yaml` 文件示例，可供参考：

**config.yaml**：
```yaml
content_generator:
llm_model: "gpt-3.5-turbo"
gemini_model: "gemini-1.5-pro-latest"
max_output_tokens: 8192
prompt_template: "default_template"
prompt_commit: "latest"
content_extractor:
youtube_url_patterns:
"youtube.com"
"youtu.be"
logging:
level: "INFO"
format: "%(asctime)s - %(levelname)s - %(message)s"
datefmt: "%y.%m.%d %H:%M:%S"
timezone: "Asia/Shanghai"
```

**conversation_config.yaml**：
```yaml
word_count: 2000
conversation_style:
"engaging"
"fast-paced"
"enthusiastic"
roles_person1: "main summarizer"
roles_person2: "questioner/clarifier"
dialogue_structure:
"Introduction"
"Main Content Summary"
"Conclusion"
podcast_name: "PODCASTFY"
podcast_tagline: "Your Personal Generative AI Podcast"
output_language: "English"
engagement_techniques:
"rhetorical questions"
"anecdotes"
"humor"
creativity: 1
user_instructions: ""
text_to_speech:
default_tts_model: "elevenlabs"
output_directories:
transcripts: "./data/transcripts"
audio: "./data/audio"
audio_format: "mp3"
ending_message: "Thanks for listening!"
elevenlabs:
default_voices:
question: "Chris"
answer: "Jessica"
model: "eleven_multilingual_v2"
```

---

## 常见问题与支持

- **Q**：为什么我的作业一直处于 `waiting` 状态？

  **A**：可能当前处理的作业数量已达上限，您的作业正在队列中等待处理。

- **Q**：如何选择不同的 TTS 模型？

  **A**：在提交作业时，通过 `tts_model` 参数指定模型，例如 `"openai"`、`"elevenlabs"`、`"edge"` 等。

- **Q**：如何自定义生成内容的风格？

  **A**：通过 `conversation_config` 参数中的 `conversation_style`、`engagement_techniques` 等字段进行配置。

- **Q**：提交的配置参数有什么格式要求？

  **A**：`config` 和 `conversation_config` 参数需要是 JSON 格式的字符串。


