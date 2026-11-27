#!/usr/bin/env python3
"""生成当前版本公开胜率/强度分档 data/patch_stats.json。

数据源：
- OpenDota 公开 API /api/heroStats（最近 7 天滚动窗口）
- Builds Forge 7.42a Tier List（同源 OpenDota，用于档位阈值与方向交叉核对）

只使用公开聚合统计，不读取游戏内存、不注入、不涉及任何对手个人资料。
"""
import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36"
CST = timezone(timedelta(hours=8))

# 档位阈值来自 Builds Forge 7.42a Tier List（S 52.5%+ / A 51%+ / B 49%+ / C 47.5%+ / D 以下）
TIER_THRESHOLDS = [
    ("S", 52.5),
    ("A", 51.0),
    ("B", 49.0),
    ("C", 47.5),
    ("D", None),
]

# OpenDota 与知识库英文名的少量差异
NAME_ALIASES = {
    "outworld devourer": "outworld destroyer",
    "ring master": "ringmaster",
}


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=45) as r:
        return r.read().decode("utf-8", "ignore")


def fetch_json(url):
    return json.loads(fetch_text(url))


def norm_name(name):
    return NAME_ALIASES.get(name.strip().lower(), name.strip().lower())


def tier_for(win_rate):
    for tier, threshold in TIER_THRESHOLDS:
        if threshold is None or win_rate >= threshold:
            return tier
    return "D"


def buildsforge_crosscheck():
    """抓 Builds Forge 页面做方向/阈值交叉核对；失败不阻塞主数据。"""
    try:
        html = fetch_text("https://buildsforge.com/en/dota2/tier-list/").replace('\\"', '"')
        pattern = re.compile(
            r'\{"key":"([^"]+)","name":"([^"]+)","attr":"([^"]+)","melee":(true|false),'
            r'"complexity":(\d+),"roles":\[(.*?)\],"roleLevels":\[(.*?)\],'
            r'"winRate":([0-9.]+),"presence":([0-9.]+),"picks":(\d+),"tier":"([SABCD])"\}'
        )
        rows = pattern.findall(html)
        page_patch = re.search(r"Patch\s+(7\.42[a-z]?)", html)
        refreshed = re.search(r"refreshed\s+([A-Z][a-z]{2}\s+\d{1,2},\s+20\d{2})", html)
        return {
            "source": "Builds Forge 7.42a Tier List",
            "url": "https://buildsforge.com/en/dota2/tier-list/",
            "page_patch": page_patch.group(1) if page_patch else "unknown",
            "page_refreshed": refreshed.group(1) if refreshed else "unknown",
            "heroes": {
                norm_name(m[1]): {
                    "win_rate": float(m[-4]),
                    "pick_rate": float(m[-3]),
                    "picks": int(m[-2]),
                    "tier": m[-1],
                }
                for m in rows
            },
            "count": len(rows),
        }
    except Exception as e:  # noqa: BLE001
        return {"source": "Builds Forge 7.42a Tier List", "url": "https://buildsforge.com/en/dota2/tier-list/", "error": str(e), "heroes": {}, "count": 0}


def main():
    kb_heroes = json.loads((DATA / "heroes.json").read_text(encoding="utf-8"))["heroes"]
    by_en = {norm_name(h["name_en"]): h for h in kb_heroes}

    raw = fetch_json("https://api.opendota.com/api/heroStats")
    rows = []
    for h in raw:
        picks = h.get("pub_pick") or 0
        wins = h.get("pub_win") or 0
        if picks <= 0:
            continue
        name = h.get("localized_name") or ""
        kh = by_en.get(norm_name(name))
        if not kh:
            raise SystemExit(f"未匹配到知识库英雄: {name}")
        rows.append({
            "id": kh["id"],
            "hero_id": int(kh.get("base_stats", {}).get("id") or h.get("id")),
            "name_zh": kh["name_zh"],
            "name_en": kh["name_en"],
            "win_rate_raw": wins / picks * 100,
            "picks": picks,
            "wins": wins,
        })

    if len(rows) != 127:
        raise SystemExit(f"英雄数异常: {len(rows)}（期望 127）")

    total_picks = sum(r["picks"] for r in rows)
    sample_matches = round(total_picks / 10)
    rows.sort(key=lambda r: (-r["win_rate_raw"], -r["picks"]))
    for rank, r in enumerate(rows, 1):
        r["win_rate"] = round(r["win_rate_raw"], 2)
        r["pick_rate"] = round(r["picks"] / sample_matches * 100, 2)
        r["tier"] = tier_for(r["win_rate"])
        r["rank"] = rank
        r["delta_vs_50"] = round(r["win_rate"] - 50.0, 2)
        r.pop("win_rate_raw", None)

    cross = buildsforge_crosscheck()
    matched = 0
    deltas = []
    for r in rows:
        c = cross.get("heroes", {}).get(norm_name(r["name_en"]))
        if c:
            matched += 1
            deltas.append(abs(c["win_rate"] - r["win_rate"]))
    crosscheck = {
        "source": cross["source"],
        "url": cross["url"],
        "page_patch": cross.get("page_patch", "unknown"),
        "page_refreshed": cross.get("page_refreshed", "unknown"),
        "matched_heroes": matched,
        "max_abs_delta_pp": round(max(deltas), 2) if deltas else None,
        "mean_abs_delta_pp": round(sum(deltas) / len(deltas), 2) if deltas else None,
        "note": f"Builds Forge 页面标注 7.42a、约 3.7M 场；页脚刷新日期为 {cross.get('page_refreshed', 'unknown')}，与本文件抓取时间不同，故仅用于档位阈值与方向交叉核对，具体数值以 OpenDota 为准。",
    }
    if cross.get("error"):
        crosscheck["error"] = cross["error"]

    tiers = {t: [] for t, _ in TIER_THRESHOLDS}
    for r in rows:
        tiers[r["tier"]].append(r["id"])

    def top_list(key, limit=10):
        ordered = sorted(rows, key=lambda r: (-r[key], -r["picks"]))[:limit]
        return [
            {"id": r["id"], "name_zh": r["name_zh"], "win_rate": r["win_rate"], "pick_rate": r["pick_rate"], "tier": r["tier"]}
            for r in ordered
        ]

    now = datetime.now(CST).strftime("%Y-%m-%d %H:%M")
    payload = {
        "meta": {
            "title": "7.42a 公开对局英雄胜率与强度分档",
            "description": "供教练端回答「这版本强不强 / 胜率多少」的公开统计层。按公开对局胜率阈值分 S/A/B/C/D；只代表全分段公开对局，不代表职业 BP 强度。",
            "source": "OpenDota 公开 API /api/heroStats（最近 7 天滚动窗口）",
            "source_url": "https://api.opendota.com/api/heroStats",
            "fetched_at": now,
            "patch": "7.42a",
            "mechanism_patch": "7.42",
            "patch_purity": "mixed",
            "patch_released": "2026-11-25",
            "patch_note": "OpenDota match_patch 只标 7.42；7.42a 是 2026-11-25 的字母平衡补丁，最近 7 天窗口覆盖 7.42 与 7.42a 混合样本。",
            "window": "最近 7 天滚动（截至抓取时间）",
            "sample_matches": sample_matches,
            "sample_picks": total_picks,
            "method": "win_rate=pub_win/pub_pick；pick_rate=pub_pick/sample_matches*100；tier 按 win_rate 阈值 S≥52.5 / A≥51 / B≥49 / C≥47.5 / D<47.5",
            "tier_thresholds": {"S": 52.5, "A": 51.0, "B": 49.0, "C": 47.5, "D": None},
            "crosscheck": crosscheck,
            "caveats": [
                "全分段公开对局，不是职业/顶分局强度；胜率不等于 BP 优先级或选手强度。",
                "7.42a 与 7.42 混合样本，不能声称纯 7.42a；机制层仍是 7.42，7.42a 的逐项数值改动未回填。",
                "未按分段拆分；高分段/职业局可能反转。",
                "样本量约 351 万场，但仍是公开对局聚合，不覆盖比赛 BP 与队伍配合。",
                f"Builds Forge 页面标注 7.42a、约 3.7M 场；其页脚刷新日期为 {cross.get('page_refreshed', 'unknown')}，与本文件抓取时间不同，故仅用于交叉核对，具体数值以 OpenDota 为准。",
            ],
        },
        "heroes": rows,
        "tiers": tiers,
        "top": {
            "by_winrate": top_list("win_rate"),
            "by_pick_rate": top_list("pick_rate"),
        },
    }
    out = DATA / "patch_stats.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out} | heroes={len(rows)} | matches={sample_matches} | S/A/B/C/D={len(tiers['S'])}/{len(tiers['A'])}/{len(tiers['B'])}/{len(tiers['C'])}/{len(tiers['D'])}")
    print(f"crosscheck: matched={matched} max_delta={crosscheck['max_abs_delta_pp']} mean_delta={crosscheck['mean_abs_delta_pp']}")


if __name__ == "__main__":
    main()
