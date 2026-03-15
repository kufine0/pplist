from django.contrib import admin
from django import forms
from django.contrib.auth.hashers import make_password
from .models import Store, NotificationConfig, Clerk, PurchaseOrder


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
            clerk.password = make_password(new_password)
        if commit:
            clerk.save()
        return clerk


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ['name', 'app_id', 'is_active', 'can_login', 'created_at']
    list_filter = ['is_active', 'can_login']
    search_fields = ['name', 'app_id']
    list_editable = ['is_active', 'can_login']


@admin.register(Clerk)
class ClerkAdmin(admin.ModelAdmin):
    form = ClerkAdminForm
    list_display = ['job_number', 'name', 'store', 'is_active', 'can_view_price', 'created_at']
    list_filter = ['is_active', 'can_view_price', 'store']
    search_fields = ['job_number', 'name']
    list_editable = ['is_active', 'can_view_price']
    readonly_fields = ['job_number', 'created_at', 'updated_at']

    fieldsets = (
        ('基本信息', {
            'fields': ('job_number', 'name', 'store')
        }),
        ('权限', {
            'fields': ('is_active', 'can_view_price')
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
