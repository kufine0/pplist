import json
import hashlib
import time
import requests
from django.core.cache import cache
from .models import Store


BASE_URL = "https://area47-win.pospal.cn:443"

PRODUCT_CACHE_KEY = "all_products"
PRODUCT_CACHE_TIMEOUT = 7 * 24 * 60 * 60


def get_signature(app_key, data_json):
    return hashlib.md5((app_key + data_json).encode('utf-8')).hexdigest().upper()


def build_headers(app_key, payload_json):
    return {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "openApi",
        "time-stamp": str(int(time.time() * 1000)),
        "data-signature": get_signature(app_key, payload_json)
    }


def fetch_all_pages(url, base_payload, store):
    all_results = []
    post_back_parameter = None

    while True:
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


def fetch_all_products(store):
    url = f"{BASE_URL}/pospal-api2/openapi/v1/productOpenApi/queryProductPages"
    return fetch_all_pages(url, {"appId": store.app_id}, store)


def get_all_products_cached(store):
    cached = cache.get(PRODUCT_CACHE_KEY)
    if cached is not None:
        return cached

    products = fetch_all_products(store)
    products = [p for p in products if p.get('enable', 1) not in (0, '0')]
    cache.set(PRODUCT_CACHE_KEY, products, PRODUCT_CACHE_TIMEOUT)
    return products


def refresh_products_cache(store):
    products = fetch_all_products(store)
    products = [p for p in products if p.get('enable', 1) not in (0, '0')]
    cache.set(PRODUCT_CACHE_KEY, products, PRODUCT_CACHE_TIMEOUT)
    return len(products)


def clear_products_cache():
    cache.delete(PRODUCT_CACHE_KEY)


def search_products(store, keyword):
    all_products = get_all_products_cached(store)

    keyword = keyword.lower()
    results = []
    for product in all_products:
        name = product.get('name', '').lower()
        barcode = product.get('barcode', '').lower()
        if keyword in name or keyword in barcode:
            results.append(product)
    return results


def create_stock_flow(app_id, app_key, stock_flow_data):
    try:
        store = Store.objects.get(app_id=app_id)
    except Store.DoesNotExist:
        store = None

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
