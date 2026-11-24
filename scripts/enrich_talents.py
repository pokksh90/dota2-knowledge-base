#!/usr/bin/env python3
"""补全并校验英雄天赋：修复层级缺失、解析 special_bonus 数值与占位符。

数据源（均为公开文件）：
- dotaconstants build/hero_abilities.json：10/15/20/25 四层左右配对与层级
- dotaconstants build/heroes.json：英雄 slug → npc 名
- SteamDB GameTracking-Dota2：heroes/npc_dota_hero_<npc>.txt（天赋数值与 tooltip 增强）
- SteamDB resource/localization/abilities_english.txt：天赋文案

用法：python3 scripts/enrich_talents.py [缓存目录] [--dry-run]
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BASE = "https://raw.githubusercontent.com/odota/dotaconstants/master/build"
NPC = ("https://raw.githubusercontent.com/SteamDatabase/GameTracking-Dota2/master/"
       "game/dota/pak01_dir/scripts/npc/heroes/npc_dota_hero_{}.txt")
LOC = ("https://raw.githubusercontent.com/SteamDatabase/GameTracking-Dota2/master/"
       "game/dota/pak01_dir/resource/localization/abilities_english.txt")
TIER_LEVELS = {1: 10, 2: 15, 3: 20, 4: 25}
PAIR_RE = re.compile(r'"(special_bonus_[0-9a-z_]+)"\s*"([+\-0-9. %]+)"')
PH_RE = re.compile(r"\{s:([A-Za-z0-9_]+)\}")


def fetch(url, path, opener):
    path = Path(path)
    if path.exists():
        return path.read_text(encoding="utf-8", errors="ignore")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 DotaKB"})
    try:
        with opener.open(req, timeout=60) as r:
            txt = r.read().decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001
        return ""
    path.write_text(txt, encoding="utf-8")
    return txt


def main():
    cache = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp")
    dry = "--dry-run" in sys.argv
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    ha = json.loads(fetch(f"{BASE}/hero_abilities.json", cache / "dc_hero_abilities.json", opener))
    dch = json.loads(fetch(f"{BASE}/heroes.json", cache / "dc_heroes.json", opener))
    loc_raw = fetch(LOC, cache / "ab_en.txt", opener)
    loc = {}
    for k, v in re.findall(r'"([^"]+)"\s+"([^"]*)"', loc_raw):
        loc.setdefault(k.lower(), v)

    slug_of = {}
    for v in dch.values():
        npc = v.get("name", "")
        if npc.startswith("npc_dota_hero_"):
            slug_of[npc[len("npc_dota_hero_"):]] = v

    t = json.loads((DATA / "talents.json").read_text(encoding="utf-8"))
    heroes = json.loads((DATA / "heroes.json").read_text(encoding="utf-8"))["heroes"]
    sid_of = {h["id"]: (h.get("base_stats") or {}).get("id") for h in heroes}
    stats = {"heroes_rebuilt": 0, "options_rebuilt": 0, "values_filled": 0, "text_resolved": 0}
    problems = []

    for hid, entry in t["heroes"].items():
        sid = sid_of.get(hid)
        info = dch.get(str(sid)) if sid else None
        broken = any(len(L.get("options", [])) != 2 for L in entry.get("levels", []))

        # 定位 hero_abilities 键
        key = None
        if info:
            cand = "npc_dota_hero_" + info["name"].replace("npc_dota_hero_", "")
            if cand in ha:
                key = cand
        if key is None:
            # 用 heroes.json 的 base_stats.id 与 npc 名后缀匹配
            sid = sid_of.get(hid)
            for k in ha:
                if sid and k.endswith(str(sid)):
                    key = k
                    break
        if key is None:
            problems.append(f"{hid}: 未定位 hero_abilities 键")
            continue
        npc_name = key.replace("npc_dota_hero_", "")
        txt = fetch(NPC.format(npc_name), cache / f"h_{npc_name}.txt", opener)
        pairs = {}
        for name, val in PAIR_RE.findall(txt):
            pairs.setdefault(name, []).append(val.strip())

        def build(opt_name):
            raw = loc.get(f"dota_tooltip_ability_{opt_name}".lower(), "")
            text_raw = raw or opt_name
            vals = pairs.get(opt_name, [])
            uniq = sorted(set(vals))
            value = uniq[0] if len(uniq) == 1 else None
            out = {"name": opt_name, "text": text_raw, "text_raw": text_raw,
                   "value_pending": bool(PH_RE.search(text_raw)),
                   "special_bonus_value": value}
            if PH_RE.search(text_raw) and value:
                n_ph = len(PH_RE.findall(text_raw))
                if n_ph == 1:
                    out["text"] = PH_RE.sub(value, text_raw)
                    out["value_pending"] = False
            return out

        if broken:
            tiers = {1: [], 2: [], 3: [], 4: []}
            for item in ha[key].get("talents", []):
                tiers[item["level"]].append(build(item["name"]))
            entry["levels"] = [{"level": TIER_LEVELS[i], "options": tiers[i]} for i in (1, 2, 3, 4)]
            stats["heroes_rebuilt"] += 1
            stats["options_rebuilt"] += sum(len(v) for v in tiers.values())
            for i in (1, 2, 3, 4):
                if len(tiers[i]) != 2:
                    problems.append(f"{hid}: L{TIER_LEVELS[i]} 仍为 {len(tiers[i])} 个选项")
        else:
            for L in entry["levels"]:
                for opt in L.get("options", []):
                    if not opt.get("special_bonus_value"):
                        opt2 = build(opt["name"])
                        if opt2["special_bonus_value"]:
                            opt["special_bonus_value"] = opt2["special_bonus_value"]
                            stats["values_filled"] += 1
                        if opt2["value_pending"] is False and opt.get("value_pending"):
                            opt["text"] = opt2["text"]
                            opt["value_pending"] = False
                            stats["text_resolved"] += 1

    # 全局占位符归一：凡 text 中仍有 {s:xxx} 且该天赋只有一个可解析数值，直接代入
    fixed = 0
    for hid, entry in t["heroes"].items():
        sid = sid_of.get(hid)
        info = dch.get(str(sid)) if sid else None
        if not info:
            continue
        npc_name = info["name"].replace("npc_dota_hero_", "")
        txt = fetch(NPC.format(npc_name), cache / f"h_{npc_name}.txt", opener)
        pairs = {}
        for name, val in PAIR_RE.findall(txt):
            pairs.setdefault(name, []).append(val.strip())
        for L in entry["levels"]:
            for opt in L["options"]:
                raw = opt.get("text_raw") or opt.get("text") or ""
                uniq = sorted(set(pairs.get(opt["name"], [])))
                if PH_RE.search(raw) and len(uniq) == 1 and len(PH_RE.findall(raw)) == 1:
                    opt["text"] = PH_RE.sub(uniq[0], raw)
                    opt["special_bonus_value"] = opt.get("special_bonus_value") or uniq[0]
                    fixed += 1
                opt["value_pending"] = bool(PH_RE.search(opt.get("text") or ""))
    stats["text_resolved"] += fixed

    total = sum(len(L["options"]) for e in t["heroes"].values() for L in e["levels"])
    withval = sum(1 for e in t["heroes"].values() for L in e["levels"]
                  for o in L["options"] if o.get("special_bonus_value"))
    t["meta"]["note"] = ("每级天赋二选一；special_bonus_value 为英雄脚本中解析到的天赋数值，"
                        "text 中残留 <...> 占位表示该天赋为机制型（改目标/改穿透等）或无统一数值，value_pending=true")
    t["meta"]["stats"] = {"options": total, "with_value": withval, "pending": total - withval,
                        "text_pending": sum(1 for e in t["heroes"].values() for L in e["levels"] for o in L["options"] if o.get("value_pending"))}

    if dry:
        print(json.dumps({"stats": stats, "total": total, "withval": withval,
                          "problems": problems[:20]}, ensure_ascii=False, indent=2))
        return 0
    (DATA / "talents.json").write_text(json.dumps(t, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"stats": stats, "total": total, "withval": withval,
                      "problems": problems[:20]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
