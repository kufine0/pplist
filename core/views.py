import logging
import os
import time
from decimal import Decimal
from datetime import datetime
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.core.cache import cache

from .models import Store, NotificationConfig, Clerk, PurchaseOrder, SystemSettings
from . import api as pospal_api
from .notifications import send_notification


logger = logging.getLogger(__name__)


def login_view(request):
    """管理员登录"""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('dashboard')
        messages.error(request, '用户名或密码错误')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})


def logout_view(request):
    """管理员登出"""
    logout(request)
    return redirect('login')


@login_required
def dashboard(request):
    """首页仪表盘"""
    if request.method == 'POST':
        if 'refresh_cache' in request.POST:
            store_id = request.POST.get('store_id')
            store = Store.objects.get(id=store_id)
            products = pospal_api.refresh_product_cache(store)
            messages.success(request, f"商品缓存已刷新，共 {len(products)} 个商品")
        elif 'test_notification' in request.POST:
            try:
                from .notifications import send_notification
                send_notification('🧪 测试通知\n\n这是一条测试消息，验证通知是否正常工作。')
                messages.success(request, "测试通知已发送")
            except Exception as e:
                messages.error(request, f"发送失败: {e}")

    stores = Store.objects.filter(is_active=True)
    clerk_count = Clerk.objects.filter(is_active=True).count()
    order_today = PurchaseOrder.objects.filter(created_at__date=timezone.now().date()).count()

    cached_data = cache.get("pospal_products")
    refresh_timestamp = cache.get("pospal_products_refresh_time")
    refresh_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(refresh_timestamp)) if refresh_timestamp else None

    context = {
        'stores': stores,
        'clerk_count': clerk_count,
        'order_today': order_today,
        'cache_status': {
            'has_cache': cached_data is not None,
            'product_count': len(cached_data) if cached_data else 0,
            'refresh_time': refresh_time,
        },
    }
    return render(request, 'dashboard.html', context)


# ==================== 店员系统 ====================

def clerk_login(request):
    """店员登录"""
    if request.session.get('clerk_id'):
        return redirect('clerk_dashboard')

    if request.method == 'POST':
        job_number = request.POST.get('job_number', '').strip()
        password = request.POST.get('password', '').strip()

        if not job_number or not password:
            messages.error(request, '请输入工号和密码')
            return redirect('clerk_login')

        try:
            clerk = Clerk.objects.select_related('store').get(job_number=job_number, is_active=True)
        except Clerk.DoesNotExist:
            messages.error(request, '工号不存在或已被禁用')
            return redirect('clerk_login')

        if not clerk.store.can_login:
            messages.error(request, f'该门店（{clerk.store.name}）暂不允许登录')
            return redirect('clerk_login')

        if clerk.password != password:
            messages.error(request, '密码错误')
            return redirect('clerk_login')

        request.session['clerk_id'] = clerk.id
        request.session['clerk_name'] = clerk.name
        request.session['store_id'] = clerk.store.id
        request.session['store_name'] = clerk.store.name
        request.session['can_view_price'] = clerk.can_view_price

        try:
            notify_text = f"店员登录提醒\n工号: {clerk.job_number}\n姓名: {clerk.name}\n门店: {clerk.store.name}\n时间: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
            send_notification(notify_text)
        except Exception as e:
            logger.error(f"登录通知发送失败: {e}")

        return redirect('clerk_dashboard')

    return render(request, 'clerk/login.html')


def clerk_logout(request):
    """店员登出"""
    request.session.flush()
    return redirect('clerk_login')


def clerk_dashboard(request):
    """店员工作台"""
    clerk_id = request.session.get('clerk_id')
    if not clerk_id:
        return redirect('clerk_login')

    clerk = Clerk.objects.get(id=clerk_id)
    store = clerk.store

    context = {
        'clerk': clerk,
        'store': store,
    }
    return render(request, 'clerk/dashboard.html', context)


def clerk_create_purchase(request):
    """店员创建进货单"""
    clerk_id = request.session.get('clerk_id')
    if not clerk_id:
        return redirect('clerk_login')

    clerk = Clerk.objects.get(id=clerk_id)
    store = clerk.store

    if request.method == 'POST':
        image = request.FILES.get('image')

        items = []
        item_count = int(request.POST.get('item_count', 0))

        # 获取商品缓存用于显示名称和进价
        try:
            products = pospal_api.get_products(store)
            product_name_map = {p.get('barcode'): p.get('name', '') for p in products}
            product_price_map = {p.get('barcode'): Decimal(str(p.get('buyPrice', 0))) for p in products}
        except:
            product_name_map = {}
            product_price_map = {}

        for i in range(item_count):
            barcode = request.POST.get(f'barcode_{i}', '').strip()
            quantity = request.POST.get(f'quantity_{i}', '').strip()

            if barcode and quantity:
                try:
                    qty = int(quantity)
                    unit_price = product_price_map.get(barcode, Decimal('0'))
                    items.append({
                        "barcode": barcode,
                        "name": product_name_map.get(barcode, ''),
                        "unitQuantity": qty,
                        "unitBuyPrice": float(unit_price),
                    })
                except ValueError:
                    pass

        if not items:
            messages.error(request, '请至少添加一个商品')
            return redirect('clerk_create_purchase')

        remarks = request.POST.get('remarks', '').strip()

        try:
            result = pospal_api.create_purchase_order(
                store=store,
                to_user_app_id=store.app_id,
                items=items,
                remarks=remarks
            )

            if result.get('status') == 'success':
                order_id = datetime.now().strftime('%Y%m%d%H%M%S')
                total_quantity = sum(item.get('unitQuantity', 0) for item in items)
                total_amount = sum(Decimal(str(item.get('unitBuyPrice', 0))) * item.get('unitQuantity', 0) for item in items)
                PurchaseOrder.objects.create(
                    clerk=clerk,
                    store=store,
                    order_id=order_id,
                    items=items,
                    total_quantity=total_quantity,
                    total_amount=total_amount,
                    image=image,
                    remarks=remarks,
                    status='success'
                )

                messages.success(request, f"进货单创建成功! ID: {order_id}")

                try:
                    product_names = [f"• {item['barcode']} x{item['unitQuantity']}" for item in items]
                    notify_text = f"📦 进货单来啦！\n\n🏪 店铺: {store.name}\n👤 店员: {clerk.job_number}\n\n📝 商品清单:\n{chr(10).join(product_names)}\n\n📋 备注: {remarks or '无'}\n\n✅ 请及时确认收货哦~"
                    send_notification(notify_text)
                except Exception as e:
                    logger.error(f"通知发送失败: {e}")
            else:
                logger.error(f"创建失败: {result.get('messages')}")

        except Exception as e:
            logger.error(f'创建失败: {e}')

        return redirect('clerk_create_purchase')

    purchase_history = PurchaseOrder.objects.filter(
        clerk=clerk,
        store=store
    ).order_by('-created_at')[:10]

    # 从缓存获取商品名称和进价映射
    try:
        products = pospal_api.get_products(store)
        product_name_map = {p.get('barcode'): p.get('name', '') for p in products}
        product_price_map = {p.get('barcode'): float(p.get('buyPrice', 0)) for p in products}
    except Exception as e:
        logger.error(f"获取商品缓存失败: {e}")
        product_name_map = {}
        product_price_map = {}

    context = {
        'clerk': clerk,
        'store': store,
        'can_view_price': clerk.can_view_price,
        'purchase_history': purchase_history,
        'product_name_map': product_name_map,
        'product_price_map': product_price_map,
    }
    return render(request, 'clerk/create_purchase.html', context)


def clerk_search_products(request):
    """店员搜索商品 (AJAX)"""
    clerk_id = request.session.get('clerk_id')
    if not clerk_id:
        return JsonResponse({'error': '未登录'}, status=401)

    keyword = request.GET.get('keyword', '').strip()
    if len(keyword) < 1:
        return JsonResponse({'products': []})

    clerk = Clerk.objects.get(id=clerk_id)
    store = clerk.store

    try:
        products = pospal_api.search_products(store, keyword)
        products = products[:20]

        can_view_price = clerk.can_view_price
        filtered = []
        for p in products:
            item = {
                'barcode': p.get('barcode'),
                'name': p.get('name'),
                'stock': p.get('stock', 0),
            }
            if can_view_price:
                item['price'] = p.get('price', 0)
            filtered.append(item)

        return JsonResponse({'products': filtered})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def clerk_api_status(request):
    """获取店员 API 状态 (AJAX)"""
    return JsonResponse({})


# ==================== 系统管理 ====================

@login_required
def cache_management(request):
    """商品缓存管理"""
    if request.method == 'POST':
        store_id = request.POST.get('store_id')
        store = Store.objects.get(id=store_id)
        products = pospal_api.refresh_product_cache(store)
        messages.success(request, f"商品缓存已刷新，共 {len(products)} 个商品")
        return redirect('cache_management')

    stores = Store.objects.all()
    cached_data = cache.get("pospal_products")
    refresh_timestamp = cache.get("pospal_products_refresh_time")
    refresh_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(refresh_timestamp)) if refresh_timestamp else None
    cache_status = {
        'has_cache': cached_data is not None,
        'product_count': len(cached_data) if cached_data else 0,
        'refresh_time': refresh_time,
    }
    return render(request, 'admin/cache.html', {
        'stores': stores,
        'cache_status': cache_status,
    })


@login_required
def log_viewer(request):
    """日志查看"""
    settings = SystemSettings.objects.first()
    log_dir = settings.log_directory if settings and settings.log_directory else '/var/log/ppl'
    
    log_files = [
        f'{log_dir}/app.log',
        f'{log_dir}/error.log',
    ]
    tail_lines = request.GET.get('lines', '100')

    content = ""
    found = False
    for log_file in log_files:
        if os.path.exists(log_file):
            found = True
            content += f"\n=== {log_file} ===\n"
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    try:
                        n = int(tail_lines)
                    except ValueError:
                        n = 100
                    recent = lines[-n:] if len(lines) > n else lines
                    content += ''.join(reversed(recent))
            except PermissionError:
                content += "无权限读取\n"
            except Exception as e:
                content += f"读取失败: {str(e)}\n"

    if not found:
        content = "日志文件不存在，请检查服务器配置"

    return render(request, 'admin/logs.html', {
        'log_content': content,
        'lines': tail_lines,
    })
