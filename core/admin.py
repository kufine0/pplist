from django.contrib import admin
from django import forms
from django.shortcuts import render, redirect
from django.core.cache import cache
import time
from .models import Store, NotificationConfig, Clerk, PurchaseOrder, SystemSettings
from . import api as pospal_api
import os


class ClerkAdminForm(forms.ModelForm):
    """店员表单 - 支持修改密码"""
    new_password = forms.CharField(
        label='新密码',
        widget=forms.PasswordInput(),
        required=False,
        help_text='留空则不修改密码'
    )

    class Meta:
        model = Clerk
        fields = '__all__'

    def save(self, commit=True):
        clerk = super().save(commit=False)
        new_password = self.cleaned_data.get('new_password')
        if new_password:
            clerk.password = new_password
        if commit:
            clerk.save()
        return clerk


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ['name', 'app_id', 'is_active', 'can_login', 'created_at']
    list_filter = ['is_active', 'can_login']
    search_fields = ['name', 'app_id']
    list_editable = ['is_active', 'can_login']
    change_list_template = 'admin/store_changelist.html'

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        urls.insert(0, path('cache/', self.admin_site.admin_view(self.cache_view), name='cache'))
        urls.insert(0, path('logs/', self.admin_site.admin_view(self.logs_view), name='logs'))
        return urls

    def cache_view(self, request):
        if request.method == 'POST':
            store_id = request.POST.get('store_id')
            store = Store.objects.get(id=store_id)
            products = pospal_api.refresh_product_cache(store)
            self.message_user(request, f"商品缓存已刷新，共 {len(products)} 个商品")
            return redirect('admin:core_store_changelist')

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

    def logs_view(self, request):
        from .models import SystemSettings
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


@admin.register(Clerk)
class ClerkAdmin(admin.ModelAdmin):
    form = ClerkAdminForm
    list_display = ['job_number', 'name', 'store', 'is_active', 'can_view_price', 'created_at']
    list_filter = ['is_active', 'can_view_price', 'store']
    search_fields = ['job_number', 'name']
    list_editable = ['is_active', 'can_view_price']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('基本信息', {
            'fields': ('job_number', 'name', 'store')
        }),
        ('权限', {
            'fields': ('is_active',)
        }),
        ('密码', {
            'fields': ('new_password',),
            'classes': ('collapse',)
        }),
        ('其他', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(NotificationConfig)
class NotificationConfigAdmin(admin.ModelAdmin):
    list_display = ['channel', 'is_active']
    list_filter = ['channel', 'is_active']


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ['log_directory', 'updated_at']
    fieldsets = (
        ('日志配置', {
            'fields': ('log_directory',)
        }),
    )


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ['order_id', 'store', 'clerk', 'total_quantity', 'created_at']
    list_filter = ['store', 'created_at']
    search_fields = ['order_id', 'store__name']
    readonly_fields = ['created_at']
    fieldsets = (
        ('基本信息', {
            'fields': ('order_id', 'store', 'clerk', 'total_quantity')
        }),
        ('图片', {
            'fields': ('image',)
        }),
        ('其他', {
            'fields': ('remarks', 'status', 'created_at')
        }),
    )
