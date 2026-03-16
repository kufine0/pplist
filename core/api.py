import json
import hashlib
import time
import requests
import threading
import logging
from django.core.cache import cache
from .models import Store

logger = logging.getLogger(__name__)


BASE_URL = "https://area47-win.pospal.cn:443"

API_RATE_LIMIT = 100
API_CALLS_KEY = "api_calls_{store_id}_{minute}"

rate_limit_locks = {}


def get_rate_limit_lock(store_id):
    if store_id not in rate_limit_locks:
        rate_limit_locks[store_id] = threading.Lock()
    return rate_limit_locks[store_id]


def check_rate_limit(store_id):
    minute = int(time.time() // 60)
    key = API_CALLS_KEY.format(store_id=store_id, minute=minute)

    lock = get_rate_limit_lock(store_id)
    with lock:
        current_calls = cache.get(key, 0)
        if current_calls >= API_RATE_LIMIT:
            return False
        cache.set(key, current_calls + 1, timeout=120)
        return True


def get_remaining_calls(store_id):
    minute = int(time.time() // 60)
    key = API_CALLS_KEY.format(store_id=store_id, minute=minute)
    current_calls = cache.get(key, 0)
    return max(0, API_RATE_LIMIT - current_calls)


def get_signature(app_key, data_json):
    return hashlib.md5((app_key + data_json).encode('utf-8')).hexdigest().upper()


def build_headers(app_key, payload_json):
    return {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "openApi",
        "time-stamp": str(int(time.time() * 1000)),
        "data-signature": get_signature(app_key, payload_json)
    }


def fetch_all_pages(url, base_payload, store, use_rate_limit=True):
    all_results = []
    post_back_parameter = None

    while True:
        if use_rate_limit and not check_rate_limit(store.id):
            raise Exception(f"[{store.name}] API 调用次数超限，请稍后再试")

        payload = {**base_payload}
        if post_back_parameter:
            payload["postBackParameter"] = post_back_parameter

        payload_json = json.dumps(payload, separators=(',', ':'))
        headers = build_headers(store.app_key, payload_json)

        last_err = None
        for attempt in range(3):
            try:
                raw = requests.post(url, headers=headers, data=payload_json, timeout=60)
                res = raw.json()
                last_err = None
                break
            except Exception as e:
                last_err = e
                time.sleep(2)

        if last_err:
            raise Exception(f"[{store.name}] 连续3次请求失败: {last_err}")

        if res.get("status") != "success":
            raise Exception(f"[{store.name}] 请求失败: {res.get('messages', ['未知错误'])}")

        data = res.get("data", {})
        result = data.get("result", [])
        all_results.extend(result)

        post_back_parameter = data.get("postBackParameter")
        if not post_back_parameter or not result:
            break

    return all_results


def get_products(store):
    """获取商品列表（共用缓存，长期有效）"""
    cache_key = "pospal_products"

    cached = cache.get(cache_key)
    if cached is not None:
        logger.info(f"[{store.name}] 使用缓存，商品数: {len(cached)}")
        return cached

    logger.info(f"[{store.name}] 缓存为空，调用API获取商品...")
    url = f"{BASE_URL}/pospal-api2/openapi/v1/productOpenApi/queryProductPages"
    data = fetch_all_pages(url, {"appId": store.app_id}, store)

    cache.set(cache_key, data, timeout=None)
    cache.set("pospal_products_refresh_time", time.time(), timeout=None)
    logger.info(f"[{store.name}] API调用成功，商品数: {len(data)}，已缓存")
    return data


def search_products(store, keyword):
    """搜索商品（使用缓存）"""
    data = get_products(store)

    keyword = keyword.lower()
    results = []
    for product in data:
        enable = product.get('enable', 1)
        if enable == 0 or enable == '0':
            continue
        name = product.get('name', '').lower()
        barcode = product.get('barcode', '').lower()
        if keyword in name or keyword in barcode:
            results.append(product)
    return results


def refresh_product_cache(store):
    """刷新商品缓存（共用）"""
    cache_key = "pospal_products"
    cache.delete(cache_key)
    data = get_products(store)
    cache.set("pospal_products_refresh_time", time.time(), timeout=None)
    return data


def create_stock_flow(app_id, app_key, stock_flow_data):
    try:
        store = Store.objects.get(app_id=app_id)
    except Store.DoesNotExist:
        store = None

    if store and not check_rate_limit(store.id):
        raise Exception("API 调用次数超限，请稍后再试")

    url = f"{BASE_URL}/pospal-api2/openapi/v1/stockFlowOpenApi/createStockFlow"

    payload = {
        "appId": app_id,
        "stockFlow": stock_flow_data
    }

    payload_json = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
    headers = build_headers(app_key, payload_json)

    try:
        response = requests.post(url, headers=headers, data=payload_json.encode('utf-8'), timeout=30)
        result = response.json()

        return result
    except Exception as e:
        return {"status": "error", "messages": [str(e)]}


def create_purchase_order(store, to_user_app_id, items, paid=0, remarks=""):
    created_datetime = time.strftime("%Y-%m-%d %H:%M:%S")

    stock_flow = {
        "toUserAppId": to_user_app_id,
        "paid": paid,
        "createdDateTime": created_datetime,
        "stockflowTypeNumber": 12,
        "remarks": remarks,
        "items": items
    }

    return create_stock_flow(store.app_id, store.app_key, stock_flow)


def create_transfer_order(store, next_user_app_id, items, paid=0, remarks=""):
    created_datetime = time.strftime("%Y-%m-%d %H:%M:%S")

    stock_flow = {
        "toUserAppId": store.app_id,
        "nextStockFlowUserAppId": next_user_app_id,
        "paid": paid,
        "createdDateTime": created_datetime,
        "stockflowTypeNumber": 13,
        "remarks": remarks,
        "items": items
    }

    return create_stock_flow(store.app_id, store.app_key, stock_flow)


def create_return_order(store, to_user_app_id, items, paid=0, remarks=""):
    created_datetime = time.strftime("%Y-%m-%d %H:%M:%S")

    stock_flow = {
        "toUserAppId": to_user_app_id,
        "paid": paid,
        "createdDateTime": created_datetime,
        "stockflowTypeNumber": 14,
        "remarks": remarks,
        "items": items
    }

    return create_stock_flow(store.app_id, store.app_key, stock_flow)


def get_all_stores():
    return Store.objects.filter(is_active=True)
