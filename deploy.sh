#!/bin/bash
# 银豹库存管理系统 - 快速部署脚本

echo "=== 银豹库存管理系统部署 ==="

# 1. 安装依赖
echo "[1/6] 安装依赖..."
pip install -r requirements.txt

# 2. 数据库初始化
echo "[2/6] 初始化数据库..."
python manage.py migrate

# 3. 创建管理员账号
echo "[3/6] 创建管理员账号..."
python manage.py createsuperuser

# 4. 收集静态文件
echo "[4/6] 收集静态文件..."
python manage.py collectstatic --noinput

# 5. 启动Redis (如果未启动)
echo "[5/6] 检查Redis..."
redis-cli ping || redis-server --daemonize yes

# 6. 启动服务
echo "[6/6] 启动服务..."
gunicorn --workers 3 --bind 0.0.0.0:8000 --access-logfile logs/access.log --error-logfile logs/error.log pospal_project.wsgi:application --daemon

echo ""
echo "=== 部署完成 ==="
echo "访问 http://your-ip:8000/admin/ 管理后台"
echo "访问 http://your-ip:8000/clerk/ 店员系统"
