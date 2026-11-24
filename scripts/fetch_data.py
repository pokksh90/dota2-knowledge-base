#!/usr/bin/env python3
"""
fetch_data.py —— 从 OpenDota 公开 API 拉取英雄基础属性与装备价格，回填知识库数值。

用法：
    python3 fetch_data.py

输出：
    data/stats.json —— 版本数值（英雄基础属性 + 装备价格），source=official，通过 id 与 heroes.json / items.json 关联。

说明：
    - 只拉公开静态数据，不涉及玩家个人隐私。
    - 数值会随版本变动，每次版本更新后重跑本脚本即可刷新。
    - 依赖 Python 标准库，无需第三方包；需能访问 api.opendota.com（国内可能需要代理）。
"""

import json
import sys
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent   # 知识库根目录
DATA = BASE / "data"

CONSTANTS_URL = "https://api.opendota.com/api/constants"
HEADERS = {"User-Agent": "Dota2Master/0.2 (+local coach tool)"}


def fetch_json(url, timeout=40):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def load_local(name):
    with open(DATA / name, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    print("拉取 OpenDota constants ...")
    const = fetch_json(CONSTANTS_URL)

    # ---------- 英雄基础属性 ----------
    local_heroes = load_local("heroes.json")["heroes"]
    # 建立 name_en -> 本地 id 的映射
    name_to_id = {h["name_en"]: h["id"] for h in local_heroes}

    heroes_out = {}
    matched = 0
    for od_id, h in const.get("heroes", {}).items():
        name_en = h.get("localized_name")
        if not name_en or name_en not in name_to_id:
            continue
        matched += 1
        heroes_out[name_to_id[name_en]] = {
            "name_en": name_en,
            "open_dota_id": od_id,
            "primary_attr": h.get("primary_attr"),
            "attack_type": h.get("attack_type"),
            "roles": h.get("roles"),
            "base_health": h.get("base_health"),
            "base_mana": h.get("base_mana"),
            "base_armor": h.get("base_armor"),
            "base_attack_min": h.get("base_attack_min"),
            "base_attack_max": h.get("base_attack_max"),
            "move_speed": h.get("move_speed"),
            "base_str": h.get("base_str"),
            "base_agi": h.get("base_agi"),
            "base_int": h.get("base_int"),
        }

    # ---------- 装备价格 ----------
    local_items = load_local("items.json")["items"]
    item_name_to_id = {i["name_en"]: i["id"] for i in local_items}

    items_out = {}
    item_matched = 0
    for od_id, it in const.get("items", {}).items():
        dname = it.get("dname")
        if not dname or dname not in item_name_to_id:
            continue
        item_matched += 1
        items_out[item_name_to_id[dname]] = {
            "name_en": dname,
            "open_dota_id": od_id,
            "cost": it.get("cost"),
        }

    out = {
        "meta": {
            "title": "版本数值（OpenDota 回填）",
            "source": "official",
            "source_url": CONSTANTS_URL,
            "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "note": "由 scripts/fetch_data.py 自动生成，数值随版本变动，重跑脚本可刷新。英雄按 name_en 匹配，装备按 dname 匹配。",
        },
        "match_report": {
            "heroes_total_local": len(local_heroes),
            "heroes_matched": matched,
            "items_total_local": len(local_items),
            "items_matched": item_matched,
        },
        "heroes": heroes_out,
        "items": items_out,
    }

    out_path = DATA / "stats.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"完成：写入 {out_path}")
    print(f"英雄匹配 {matched}/{len(local_heroes)}，装备匹配 {item_matched}/{len(local_items)}")
    print("提示：若匹配数偏低，说明 heroes.json 的 name_en 与 OpenDota localized_name 不一致，需核对。")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[错误] {type(e).__name__}: {e}", file=sys.stderr)
        print("若为网络错误：请确认能访问 api.opendota.com（国内可能需代理/VPN）。", file=sys.stderr)
        sys.exit(1)
