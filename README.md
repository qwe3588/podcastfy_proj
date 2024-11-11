# Podcastfy 项目说明

该项目提供了基于内容生成播客的功能，包括文本到语音转换、内容生成等。

## 功能特性

- **邀请注册**：只有在 `invitation_list.yaml` 中的邮箱才能注册，确保了用户的可控性。
- **用户认证**：采用 JWT 认证机制，用户的密码以哈希方式存储，保证了账户的安全。
- **作业管理**：用户可以提交作业、查询作业状态、下载生成的播客等。

## 使用指南

1. **配置邀请列表**：在项目根目录下的 `invitation_list.yaml` 文件中，添加被邀请的用户邮箱。
   ```yaml
   - user1@example.com
   - user2@example.com
   # 添加更多的邀请邮箱
   ```

2. **启动 Redis 服务**：确保 Redis 服务已启动，并在 `models.py` 中配置正确的连接信息。

3. **运行项目**：
   ```bash
   uvicorn podcastfy.api.api_service:app --reload
   ```

## 注意事项

- **密码安全**：用户的密码将以哈希方式存储在 Redis 中，不会以明文形式保存。

- **API 调用**：所有的 API 调用都需要进行用户认证，需提供有效的 JWT 令牌。
