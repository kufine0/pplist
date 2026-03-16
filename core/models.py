from django.db import models
from django.contrib.auth.models import User


class Store(models.Model):
    """店铺配置"""
    name = models.CharField(max_length=100, verbose_name="店铺名称")
    app_id = models.CharField(max_length=64, unique=True, verbose_name="App ID")
    app_key = models.CharField(max_length=64, verbose_name="App Key")
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    can_login = models.BooleanField(default=True, verbose_name="允许登录")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "店铺"
        verbose_name_plural = "店铺"

    def __str__(self):
        return self.name


class NotificationConfig(models.Model):
    """通知配置"""
    CHANNEL_CHOICES = [
        ('telegram', 'Telegram'),
        ('dingtalk', '钉钉'),
    ]
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, verbose_name="通知渠道")
    bot_token = models.CharField(max_length=100, blank=True, verbose_name="Bot Token")
    chat_id = models.CharField(max_length=50, blank=True, verbose_name="Chat ID")
    webhook = models.URLField(max_length=200, blank=True, verbose_name="Webhook URL")
    secret = models.CharField(max_length=100, blank=True, verbose_name="密钥")
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "通知配置"
        verbose_name_plural = "通知配置"

    def __str__(self):
        return f"{self.get_channel_display()}"


class Clerk(models.Model):
    """店员"""
    job_number = models.CharField(max_length=20, unique=True, verbose_name="工号")
    name = models.CharField(max_length=50, verbose_name="姓名")
    password = models.CharField(max_length=128, verbose_name="密码")
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='clerks', verbose_name="所属门店")
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    can_view_price = models.BooleanField(default=False, verbose_name="能否查看价格")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "店员"
        verbose_name_plural = "店员"
        ordering = ['store', 'job_number']

    def __str__(self):
        return f"{self.name} ({self.job_number}) - {self.store.name}"


class PurchaseOrder(models.Model):
    """进货单记录"""
    clerk = models.ForeignKey(Clerk, on_delete=models.CASCADE, related_name='purchase_orders', verbose_name="店员")
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='purchase_orders', verbose_name="门店")
    order_id = models.CharField(max_length=50, verbose_name="订单ID")
    items = models.JSONField(verbose_name="商品明细")
    total_quantity = models.IntegerField(default=0, verbose_name="总数量")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="总金额")
    image = models.ImageField(upload_to='purchase_images/%Y/%m/', blank=True, null=True, verbose_name="图片")
    remarks = models.TextField(blank=True, verbose_name="备注")
    status = models.CharField(max_length=20, default='success', verbose_name="状态")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "进货单"
        verbose_name_plural = "进货单"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.store.name} - {self.order_id} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class SystemSettings(models.Model):
    """系统配置"""
    log_directory = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="日志文件目录",
        help_text="例如: /var/log/ppl 或 logs"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "系统配置"
        verbose_name_plural = "系统配置"

    def __str__(self):
        return f"日志目录: {self.log_directory or '未设置'}"
