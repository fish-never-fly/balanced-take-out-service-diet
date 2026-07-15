"""根据用户当前位置生成确定性的多平台附近商家模拟数据。

该模块不调用真实平台，也不执行网络采集。商家距离、坐标、配送费和起送价均由
平台与商家名称的稳定哈希生成，同一位置与参数会得到相同结果。
"""

from dataclasses import dataclass
from hashlib import sha256
from math import cos, pi, sin
from typing import Any


SUPPORTED_PLATFORMS = ("meituan", "eleme", "jd")


class NearbyRequestError(ValueError):
    """表示定位坐标、搜索半径或平台参数不合法。"""

    pass


@dataclass(frozen=True, slots=True)
class NearbyRequest:
    """保存一次附近模拟查询所需的标准化参数。"""

    latitude: float
    longitude: float
    radius_m: int = 3000
    platforms: tuple[str, ...] = SUPPORTED_PLATFORMS
    store_limit: int = 30
    items_per_store: int = 8

    def __post_init__(self) -> None:
        if not -90 <= self.latitude <= 90:
            raise NearbyRequestError("latitude must be between -90 and 90")
        if not -180 <= self.longitude <= 180:
            raise NearbyRequestError("longitude must be between -180 and 180")
        if not 100 <= self.radius_m <= 20000:
            raise NearbyRequestError("radius_m must be between 100 and 20000")
        if not self.platforms:
            raise NearbyRequestError("at least one platform must be selected")
        if any(platform not in SUPPORTED_PLATFORMS for platform in self.platforms):
            raise NearbyRequestError("platforms must contain only meituan, eleme, or jd")
        if not 1 <= self.store_limit <= 100:
            raise NearbyRequestError("store_limit must be between 1 and 100")
        if not 1 <= self.items_per_store <= 50:
            raise NearbyRequestError("items_per_store must be between 1 and 50")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NearbyRequest":
        """把接口 JSON 转换为经过范围检查的查询对象。"""

        try:
            raw_platforms = payload.get("platforms", list(SUPPORTED_PLATFORMS))
            if not isinstance(raw_platforms, list):
                raise NearbyRequestError("platforms must be a list")
            platforms = tuple(dict.fromkeys(str(value).lower() for value in raw_platforms))
            return cls(
                latitude=float(payload["latitude"]),
                longitude=float(payload["longitude"]),
                radius_m=int(payload.get("radius_m", 3000)),
                platforms=platforms,
                store_limit=int(payload.get("store_limit", 30)),
                items_per_store=int(payload.get("items_per_store", 8)),
            )
        except NearbyRequestError:
            # 保留平台、半径等业务校验产生的具体错误信息。
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise NearbyRequestError("latitude and longitude are required numbers") from exc


def platform_summary(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """统计每个平台的模拟菜品数量和商家数量。"""

    result: list[dict[str, Any]] = []
    for platform in SUPPORTED_PLATFORMS:
        platform_items = [item for item in items if item["platform"] == platform]
        stores = {item["store_name"] for item in platform_items}
        result.append(
            {
                "platform": platform,
                "item_count": len(platform_items),
                "store_count": len(stores),
            }
        )
    return result


def simulate_nearby_stores(
    items: list[dict[str, Any]],
    request: NearbyRequest,
) -> dict[str, Any]:
    """将模拟菜单按平台和商家分组，并生成当前位置附近的商家结果。"""

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in items:
        if item["platform"] in request.platforms:
            grouped.setdefault((item["platform"], item["store_name"]), []).append(item)

    stores: list[dict[str, Any]] = []
    for (platform, store_name), store_items in grouped.items():
        seed = _stable_seed(f"{platform}:{store_name}")
        distance_m = 150 + seed % 9850
        if distance_m > request.radius_m:
            continue

        latitude, longitude = _offset_coordinate(
            request.latitude,
            request.longitude,
            distance_m,
            seed,
        )
        sorted_items = sorted(store_items, key=lambda item: (item["price_yuan"], item["id"]))
        stores.append(
            {
                "store_id": sha256(f"{platform}:{store_name}".encode("utf-8")).hexdigest()[:12],
                "platform": platform,
                "store_name": store_name,
                "latitude": round(latitude, 6),
                "longitude": round(longitude, 6),
                "distance_m": distance_m,
                "delivery_fee_yuan": round(2 + seed % 61 / 10, 1),
                "minimum_order_yuan": float(15 + seed % 26),
                "items": [_item_summary(item) for item in sorted_items[: request.items_per_store]],
                "total_item_count": len(store_items),
            }
        )

    stores.sort(key=lambda store: (store["distance_m"], store["platform"], store["store_name"]))
    selected = stores[: request.store_limit]
    return {
        "source": "simulated-nearby",
        "notice": "商家位置与配送信息为模拟数据，不代表真实平台或真实门店。",
        "location": {
            "latitude": request.latitude,
            "longitude": request.longitude,
            "radius_m": request.radius_m,
        },
        "platforms": list(request.platforms),
        "matched_store_count": len(stores),
        "returned_store_count": len(selected),
        "stores": selected,
    }


def _stable_seed(value: str) -> int:
    """将字符串转换为跨进程稳定的整数种子。"""

    return int.from_bytes(sha256(value.encode("utf-8")).digest()[:8], "big")


def _offset_coordinate(
    latitude: float,
    longitude: float,
    distance_m: int,
    seed: int,
) -> tuple[float, float]:
    """按距离和哈希角度生成用户位置附近的模拟商家坐标。"""

    angle = seed % 3600 / 3600 * 2 * pi
    latitude_delta = distance_m * cos(angle) / 111_320
    longitude_scale = max(abs(cos(latitude * pi / 180)), 0.05)
    longitude_delta = distance_m * sin(angle) / (111_320 * longitude_scale)
    store_latitude = max(-90.0, min(90.0, latitude + latitude_delta))
    store_longitude = (longitude + longitude_delta + 180) % 360 - 180
    return store_latitude, store_longitude


def _item_summary(item: dict[str, Any]) -> dict[str, Any]:
    """提取附近商家接口需要展示的菜品字段。"""

    return {
        "id": item["id"],
        "dish_name": item["dish_name"],
        "category": item["category"],
        "price_yuan": item["price_yuan"],
        "nutrition": item["nutrition"],
    }
