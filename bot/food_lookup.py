"""Open Food Facts first, then USDA; cache in storage."""
from __future__ import annotations

import re
from typing import Any

import requests

import config
from bot.parser import MealItem
from bot.storage import JsonStorage
from utils.helpers import now_local_iso


def _cache_key(food: str, quantity: str) -> str:
    return f"{food.strip().lower()} {quantity.strip().lower()}"


def _extract_grams(quantity: str) -> float | None:
    q = quantity.lower().replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(g|gram|grams|gr)\b", q)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)\s*(kg|kilogram)\b", q)
    if m:
        return float(m.group(1)) * 1000.0
    m = re.search(r"(\d+(?:\.\d+)?)\s*(ml|milliliter|milliliters)\b", q)
    if m:
        return float(m.group(1))  # treat ml ~ g for liquids rough
    m = re.search(r"(\d+(?:\.\d+)?)\s*(oz|ounce|ounces)\b", q)
    if m:
        return float(m.group(1)) * 28.35
    m = re.search(r"(\d+(?:\.\d+)?)\s*(lb|pound|pounds)\b", q)
    if m:
        return float(m.group(1)) * 453.59
    m = re.search(r"\b(\d+(?:\.\d+)?)\s*(piece|pieces|pc|slice|slices|egg|eggs|banana|bananas)\b", q)
    if m:
        n = float(m.group(1))
        return n * 100.0  # rough 100g per unit for produce/eggs
    m = re.search(r"^\s*(\d+(?:\.\d+)?)\s*$", q.strip())
    if m:
        return float(m.group(1)) * 100.0
    return None


def _kcal_from_per_100g(per_100g: float, grams: float) -> int:
    return max(0, int(round(per_100g * grams / 100.0)))


def _openfoodfacts_lookup(food: str, quantity: str) -> tuple[int, str] | None:
    url = "https://world.openfoodfacts.org/cgi/search.pl"
    params = {"search_terms": food, "json": "true", "page_size": "5", "fields": "code,product_name,nutriments"}
    try:
        r = requests.get(url, params=params, timeout=12)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError):
        return None
    products = data.get("products") or []
    grams = _extract_grams(quantity) or 100.0
    for p in products:
        nut = p.get("nutriments") or {}
        kcal_100 = nut.get("energy-kcal_100g") or nut.get("energy-kcal_value") or nut.get("energy-kcal")
        if kcal_100 is None:
            kj = nut.get("energy-kj_100g") or nut.get("energy-kj_value")
            if kj is not None:
                try:
                    kcal_100 = float(kj) / 4.184
                except (TypeError, ValueError):
                    continue
            else:
                continue
        try:
            per = float(kcal_100)
        except (TypeError, ValueError):
            continue
        total = _kcal_from_per_100g(per, grams)
        if total <= 0:
            continue
        return total, "OpenFoodFacts"
    return None


def _usda_lookup(food: str, quantity: str) -> tuple[int, str] | None:
    if not config.USDA_API_KEY:
        return None
    search_url = "https://api.nal.usda.gov/fdc/v1/foods/search"
    params = {"query": food, "pageSize": 3, "api_key": config.USDA_API_KEY}
    try:
        r = requests.get(search_url, params=params, timeout=12)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError):
        return None
    foods = data.get("foods") or []
    fdc_id = None
    for f in foods:
        if f.get("fdcId"):
            fdc_id = f["fdcId"]
            break
    if not fdc_id:
        return None
    detail_url = f"https://api.nal.usda.gov/fdc/v1/food/{fdc_id}"
    try:
        r = requests.get(detail_url, params={"api_key": config.USDA_API_KEY}, timeout=12)
        r.raise_for_status()
        detail = r.json()
    except (requests.RequestException, ValueError):
        return None
    per_100 = None
    for n in detail.get("foodNutrients", []):
        nut = n.get("nutrient") or {}
        if nut.get("id") == 1008 or (nut.get("name") or "").lower().startswith("energy"):
            amt = n.get("amount")
            if amt is not None:
                try:
                    per_100 = float(amt)
                    break
                except (TypeError, ValueError):
                    continue
    if per_100 is None:
        return None
    grams = _extract_grams(quantity) or 100.0
    total = _kcal_from_per_100g(per_100, grams)
    return total, "USDA"


def resolve_meal_items(items: list[MealItem], storage: JsonStorage | None = None) -> list[MealItem]:
    storage = storage or JsonStorage.get()
    data = storage.load()
    cache: dict[str, Any] = data.setdefault("food_cache", {})
    out: list[MealItem] = []
    for it in items:
        key = _cache_key(it.food, it.quantity)
        if key in cache:
            c = cache[key]
            out.append(
                MealItem(food=it.food, quantity=it.quantity, calories=int(c["calories"]))
            )
            continue
        resolved = _openfoodfacts_lookup(it.food, it.quantity)
        source = "OpenFoodFacts"
        if not resolved:
            resolved = _usda_lookup(it.food, it.quantity)
            source = "USDA" if resolved else source
        if not resolved:
            # fallback estimate so logging still works
            grams = _extract_grams(it.quantity) or 100
            est = max(50, int(grams * 1.5))
            out.append(MealItem(food=it.food, quantity=it.quantity, calories=est))
            storage.set_food_cache_entry(
                key,
                {"calories": est, "source": "estimate", "cached_at": now_local_iso()},
            )
            continue
        cal, src = resolved
        out.append(MealItem(food=it.food, quantity=it.quantity, calories=cal))
        storage.set_food_cache_entry(
            key,
            {"calories": cal, "source": src, "cached_at": now_local_iso()},
        )
    return out
