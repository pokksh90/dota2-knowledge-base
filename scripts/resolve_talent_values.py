#!/usr/bin/env python3
"""解析机制型天赋的数值：从英雄脚本 AbilityValues 块里取 special_bonus 增量。

原理（公开文件，SteamDB GameTracking-Dota2）：
    "move_slow_min"
    {
        "value"                "12"
        "hero_levelup"         "+0.5"
        "special_bonus_unique_antimage_5"   "+9"
    }
即该天赋对 move_slow_min 的增量是 +9。把 {s:bonus_move_slow_min} 代入 +9（若文案里已有 "+"，不重复加号）。
通用天赋（special_bonus_hp_300 之类）的数值直接写在名字后缀里。

用法：python3 scripts/resolve_talent_values.py [缓存目录] [--dry-run]
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DC = "https://raw.githubusercontent.com/odota/dotaconstants/master/build/heroes.json"
NPC = ("https://raw.githubusercontent.com/SteamDatabase/GameTracking-Dota2/master/"
       "game/dota/pak01_dir/scripts/npc/heroes/npc_dota_hero_{}.txt")

PH = re.compile(r"\{s:([A-Za-z0-9_]+)\}")
GENERIC = re.compile(r"^special_bonus_(?!unique)([a-z_]+?)_(\d+)$")

INNER = re.compile(r'"(special_bonus_[0-9a-z_]+)"\s*"([+\-0-9.]+)"')


def fetch(url, path, opener):
    p = Path(path)
    if p.exists():
        return p.read_text(encoding="utf-8", errors="ignore")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 DotaKB"})
    try:
        with opener.open(req, timeout=60) as r:
            txt = r.read().decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001
        return ""
    p.write_text(txt, encoding="utf-8")
    return txt


def walk_blocks(s):
    """返回 [(key, content)]，含嵌套块；content 为块内原文。"""
    out, i, n = [], 0, len(s)
    while i < n:
        if s[i] == '"':
            j = s.find('"', i + 1)
            if j < 0:
                break
            key = s[i + 1:j]
            k = j + 1
            while k < n and s[k] in " \t\r\n":
                k += 1
            if k < n and s[k] == "{":
                depth, m = 0, k
                while m < n:
                    if s[m] == "{":
                        depth += 1
                    elif s[m] == "}":
                        depth -= 1
                        if depth == 0:
                            break
                    m += 1
                out.append((key, s[k + 1:m]))
                i = k + 1
                continue
            i = j + 1
        else:
            i += 1
    return out


def talent_key_map(txt):
    """talent name -> {ability_value_key: bonus}，只取带 value/hero_levelup 的数值块。"""
    out = {}
    for key, inner in walk_blocks(txt):
        if '"value"' not in inner and '"hero_levelup"' not in inner:
            continue
        for tname, val in INNER.findall(inner):
            out.setdefault(tname, {}).setdefault(key, val.strip())
    return out


def fmt(val, raw_text, start, end):
    """替换占位符时避免出现 "+ +9" 这类重复符号。"""
    prev = raw_text[start - 1] if start > 0 else ""
    sign = val[0]
    if sign in "+-" and prev in "+-":
        val = val[1:]
    return val


def main():
    cache = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp")
    dry = "--dry-run" in sys.argv
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    dch = json.loads(fetch(DC, cache / "dc_heroes.json", opener))
    dca = json.loads(fetch("https://raw.githubusercontent.com/odota/dotaconstants/master/build/abilities.json",
                           cache / "dc_abilities.json", opener))
    heroes = json.loads((DATA / "heroes.json").read_text(encoding="utf-8"))["heroes"]
    sid_of = {h["id"]: (h.get("base_stats") or {}).get("id") for h in heroes}

    t = json.loads((DATA / "talents.json").read_text(encoding="utf-8"))
    stats = {"resolved_text": 0, "resolved_value": 0, "still_pending": 0}

    for hid, entry in t["heroes"].items():
        info = dch.get(str(sid_of.get(hid)))
        if not info:
            continue
        npc = info["name"].replace("npc_dota_hero_", "")
        txt = fetch(NPC.format(npc), cache / f"h_{npc}.txt", opener)
        kmap = talent_key_map(txt)
        for L in entry["levels"]:
            for opt in L["options"]:
                name = opt["name"]
                raw = opt.get("text_raw") or opt.get("text") or ""
                vals = dict(kmap.get(name, {}))
                g = GENERIC.match(name)
                if g:
                    vals.setdefault("value", g.group(2))
                    opt["special_bonus_value"] = g.group(2)
                elif len(set(vals.values())) == 1 and vals:
                    opt["special_bonus_value"] = opt.get("special_bonus_value") or list(vals.values())[0]

                def pick(key):
                    return vals.get(key) or vals.get(key[6:] if key.startswith("bonus_") else key)

                def sub(m):
                    v = pick(m.group(1))
                    if v is None:
                        return m.group(0)
                    return fmt(v, raw, m.start(), m.end())

                if PH.search(raw):
                    new = PH.sub(sub, raw)
                    new = re.sub(r"(\+\+|-\+)|(--|\+-)", lambda m: "-" if m.group(0).endswith("-") else "+", new)
                    if "{" not in new:
                        opt["text"] = new
                        opt["value_pending"] = False
                        stats["resolved_text"] += 1
                    else:
                        opt["text"] = new
                if opt.get("special_bonus_value"):
                    stats["resolved_value"] += 1
                dname = (dca.get(name) or {}).get("dname")
                if dname:
                    opt["text"] = dname.strip()
                    nums = re.findall(r"[+\-]?\d+(?:\.\d+)?", dname)
                    opt["special_bonus_value"] = nums[0] if len(nums) == 1 else None
                if PH.search(opt.get("text") or ""):
                    opt["value_pending"] = True
                    stats["still_pending"] += 1
                else:
                    opt["value_pending"] = False

    total = sum(len(L["options"]) for e in t["heroes"].values() for L in e["levels"])
    withval = sum(1 for e in t["heroes"].values() for L in e["levels"] for o in L["options"] if o.get("special_bonus_value"))
    t["meta"]["text_source"] = "dotaconstants abilities.json 的 dname（官方 tooltip 成品文案）；special_bonus_value 取自英雄脚本 AbilityValues"
    t["meta"]["stats"] = {"options": total, "with_value": withval, "pending": total - withval,
                          "text_pending": sum(1 for e in t["heroes"].values() for L in e["levels"] for o in L["options"] if o.get("value_pending"))}
    if dry:
        print(json.dumps({"stats": stats, "with_value": withval, "total": total}, ensure_ascii=False, indent=2))
        return 0
    (DATA / "talents.json").write_text(json.dumps(t, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"stats": stats, "with_value": withval, "total": total}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
