#!/usr/bin/env python3
"""构建 data/talents.json（英雄天赋树）与 data/neutral_items.json（中立装备）。

天赋来源: Valve 官方 datafeed (https://www.dota2.com/datafeed/herodata?hero_id=N)
         + dotaconstants hero_abilities（提供 10/15/20/25 四层的左右配对）
中立装备来源: Liquipedia Neutral Items 页的分档清单 + dotaconstants 道具数值
用法: python3 scripts/build_talents.py [缓存目录]
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BASE = "https://raw.githubusercontent.com/odota/dotaconstants/master/build"
FEED = "https://www.dota2.com/datafeed/herodata?language=english&hero_id={}"
TIER_LEVELS = {1: 10, 2: 15, 3: 20, 4: 25}

# Liquipedia Neutral Items（7.42）分档清单
NEUTRAL = {
    1: ["Ash Legion Shield", "Chipped Vest", "Dagger of Ristul", "Dormant Curio", "Duelist Gloves",
        "Forager's Kit", "Kobold Cup", "Occult Bracelet", "Pollywog Charm", "Possessed Mask",
        "Stonefeather Satchel", "Weighted Dice"],
    2: ["Crippling Crossbow", "Defiant Shell", "Essence Ring", "Mana Draught", "Medallion of Courage",
        "Poor Man's Shield", "Searing Signet", "Seeds of Serenity", "Tumbler's Toy"],
    3: ["Cloak of Flames", "Gunpowder Gauntlet", "Jidi Pollen Bag", "Partisan's Brand", "Psychic Headband",
        "Serrated Shiv", "Spellslinger", "Stormcrafter", "Unrelenting Eye"],
    4: ["Conjurer's Catalyst", "Dandelion Amulet", "Enchanter's Bauble", "Flayer's Bota", "Giant's Maul",
        "Idol of Scree'Auk", "Rattlecage", "Metamorphic Mandible"],
    5: ["Book of the Dead", "Dezun Bloodrite", "Divine Regalia", "Fallen Sky", "Harmonizer", "Minotaur Horn",
        "Riftshadow Prism", "Spider Legs", "Stygian Desolator", "Witchbane"],
}


def get(url, cache_path):
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 DotaKB"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 直连，避免环境代理
    with opener.open(req, timeout=40) as r:
        raw = r.read().decode("utf-8")
    cache_path.write_text(raw, encoding="utf-8")
    return json.loads(raw)


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def clean_talent_text(s):
    """把 {s:bonus_x} 之类的占位符替换成 <x>，并保留原文。"""
    return re.sub(r"\{s:(\w+)\}", lambda m: "<" + m.group(1) + ">", s or "")


NPC_BASE = ("https://raw.githubusercontent.com/SteamDatabase/GameTracking-Dota2/master/"
            "game/dota/pak01_dir/scripts/npc/heroes/npc_dota_hero_{}.txt")
SB_RE = re.compile(r'"(special_bonus_[0-9a-z_]+)"\s*"([+\-0-9. ]+)"')


def talent_bonus_values(hero_id, cache):
    """从英雄脚本文件里抓天赋的 special_bonus 数值（天赋实际加的数值）。"""
    fname = f"h_{hero_id}.txt"
    path = cache / fname
    if not path.exists():
        url = NPC_BASE.format(hero_id.replace("-", "_"))
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 DotaKB"})
        try:
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=40) as r:
                path.write_text(r.read().decode("utf-8", "ignore"), encoding="utf-8")
        except Exception:
            return {}
    txt = path.read_text(encoding="utf-8", errors="ignore")
    return {m.group(1): m.group(2).strip() for m in SB_RE.finditer(txt)}


def main():
    cache = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp")
    ha = get(f"{BASE}/hero_abilities.json", cache / "dc_hero_abilities.json")
    items_dc = get(f"{BASE}/items.json", cache / "dc_items.json")
    heroes = json.loads((DATA / "heroes.json").read_text(encoding="utf-8"))["heroes"]

    # 英雄 id -> npc key（与 heroes.json 的 base_stats.id 对应）
    npc_of = {}
    for h in heroes:
        sid = (h.get("base_stats") or {}).get("id")
        if sid:
            npc_of[h["id"]] = sid

    talents_out, unresolved = {}, 0
    for hid, sid in npc_of.items():
        feed = get(FEED.format(sid), cache / f"hd_{sid}.json")
        data = feed.get("result", {}).get("data", {})
        if not data or not data.get("heroes"):
            continue
        hfeed = data["heroes"][0]
        bonus = talent_bonus_values(hid, cache)
        by_name = {t["name"]: t for t in hfeed.get("talents", [])}
        # 从 hero_abilities 拿左右配对与层级
        key = None
        for k in ha:
            if ha[k].get("talents") and k.endswith(str(sid)) or k.endswith(norm(hid)):
                key = k
                break
        if not key:
            for k in ha:
                hits = [t["name"] for t in ha[k].get("talents", [])]
                if hits and hits[0] in by_name:
                    key = k
                    break
        tiers = {1: [], 2: [], 3: [], 4: []}
        for t in (ha.get(key, {}) or {}).get("talents", []):
            name = t["name"]
            if name not in by_name:
                continue
            loc = by_name[name].get("name_loc", "")
            cleaned = clean_talent_text(loc)
            pending = bool(re.search(r"<", cleaned))
            if pending:
                unresolved += 1
            tiers[t["level"]].append({"name": name, "text": cleaned, "text_raw": loc,
                                      "value_pending": pending, "special_bonus_value": bonus.get(name)})
        talents_out[hid] = {
            "levels": [{"level": TIER_LEVELS[i], "options": tiers[i]} for i in (1, 2, 3, 4)]
        }

    out = {
        "meta": {
            "source": "Valve datafeed + dotaconstants",
            "note": "每级天赋二选一；text 中的 <...> 为尚未解析的具体数值占位（value_pending=true），解析需补丁级 ability values",
            "tier_levels": [10, 15, 20, 25],
        },
        "heroes": talents_out,
    }
    (DATA / "talents.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- 中立装备 ----------
    byname = {norm(v.get("dname", "")): (k, v) for k, v in items_dc.items()}
    neu, missing = {}, []
    for tier, names in NEUTRAL.items():
        lst = []
        for n in names:
            hit = byname.get(norm(n))
            if not hit:
                missing.append(n)
                continue
            k, v = hit
            lst.append({
                "id": k,
                "name_en": v.get("dname", n),
                "tier": tier,
                "behavior": v.get("behavior"),
                "attrib": [{"key": x["key"], "value": x["value"]} for x in v.get("attrib", []) if not x.get("generated")][:10],
                "abilities": [{"title": a.get("title"), "type": a.get("type"),
                               "description": re.sub(r"\s+", " ", a.get("description", "")).strip()}
                              for a in v.get("abilities", []) if a.get("description")],
            })
        neu[tier] = lst
    (DATA / "neutral_items.json").write_text(json.dumps({
        "meta": {
            "source": "Liquipedia Neutral Items (7.42) + dotaconstants",
            "craft": {"resource": "Madstone", "unlock_time": {"1": "05:00", "2": "15:00", "3": "25:00", "4": "35:00", "5": "60:00"},
                      "madstone_cap": {"5:00": 5, "15:00": 15, "25:00": 25, "35:00": 35, "60:00": 45, "70:00": "unlimited"},
                      "cost": {"1": 6, "2": 10, "3": 10, "4": 10, "5": 10},
                      "note": "必须先做低一档；每人同时只有 1 件，不可掉落/出售/进背包，重铸会替换"},
            "note": "中立装备每档为随机候选（4~5 选 1，可保留上一档），本文件为候选池清单",
        },
        "tiers": neu,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print("talents heroes:", len(talents_out), "unresolved placeholders:", unresolved)
    print("neutral items:", {t: len(v) for t, v in neu.items()}, "missing:", missing)


if __name__ == "__main__":
    main()
