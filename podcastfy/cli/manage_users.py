import asyncio
import argparse
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from podcastfy.api.auth import create_user, get_password_hash, get_user
from podcastfy.api.models import RedisClient

async def create_admin_user(email: str, password: str):
    """创建管理员用户"""
    # 检查用户是否已存在
    existing_user = await get_user(email)
    if existing_user:
        print(f"用户 {email} 已存在")
        return False
        
    # 生成密码哈希
    password_hash = await get_password_hash(password)
    
    # 获取 Redis 连接
    redis = await RedisClient.get_user_instance()
    
    # 创建用户数据
    user_data = {
        "email": email,
        "password_hash": password_hash,
        "is_active": "true",
        "is_admin": "true"  # 设置为管理员
    }
    
    # 保存用户数据
    for key, value in user_data.items():
        await redis.hset(f"user:{email}", key, value)
    
    print(f"管理员用户 {email} 创建成功")
    return True

async def reset_user_password(email: str, new_password: str):
    """重置用户密码"""
    # 检查用户是否存在
    existing_user = await get_user(email)
    if not existing_user:
        print(f"用户 {email} 不存在")
        return False
        
    # 生成新密码哈希
    password_hash = await get_password_hash(new_password)
    
    # 获取 Redis 连接
    redis = await RedisClient.get_user_instance()
    
    # 更新密码
    await redis.hset(f"user:{email}", "password_hash", password_hash)
    
    print(f"用户 {email} 密码重置成功")
    return True

async def delete_all_users():
    """删除所有用户（谨慎使用）"""
    redis = await RedisClient.get_user_instance()
    # 获取所有用户的 key
    user_keys = await redis.keys("user:*")
    
    if not user_keys:
        print("没有找到任何用户")
        return
        
    # 删除所有用户
    for key in user_keys:
        await redis.delete(key)
    
    print(f"已删除 {len(user_keys)} 个用户")

def main():
    parser = argparse.ArgumentParser(description="用户管理工具")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # 创建管理员用户命令
    create_parser = subparsers.add_parser("create-admin", help="创建���理员用户")
    create_parser.add_argument("email", help="用户邮箱")
    create_parser.add_argument("password", help="用户密码")
    
    # 重置密码命令
    reset_parser = subparsers.add_parser("reset-password", help="重置用户密码")
    reset_parser.add_argument("email", help="用户邮箱")
    reset_parser.add_argument("password", help="新密码")
    
    # 删除所有用户命令
    subparsers.add_parser("delete-all", help="删除所有用户（谨慎使用）")
    
    args = parser.parse_args()
    
    if args.command == "create-admin":
        asyncio.run(create_admin_user(args.email, args.password))
    elif args.command == "reset-password":
        asyncio.run(reset_user_password(args.email, args.password))
    elif args.command == "delete-all":
        confirm = input("此操作将删除所有用户数据！输入 'YES' 确认: ")
        if confirm == "YES":
            asyncio.run(delete_all_users())
        else:
            print("操作已取消")
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 