#!/usr/bin/env python3
"""知识库一致性审查：结构、引用、重复、计数同步。

用法：python3 scripts/quality_audit.py [--write-report]
输出 data/quality_report.json（可选），退出码 0 表示无 error 级问题。
"""
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")

ERRORS = []
WARNINGS = []
INFO = []


def err(msg):
    ERRORS.append(msg)


def warn(msg):
    WARNINGS.append(msg)


def load(name):
    path = os.path.join(D, name)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:  # noqa: BLE001
        err(f"{name}: JSON 解析失败 {e}")
        return None


def main():
    heroes = load("heroes.json")
    rules = load("rules.json")
    inference = load("inference.json")
    matchups = load("matchups.json")
    items = load("items.json")
    tactics = load("tactics.json")
    talents = load("talents.json")
    neutral = load("neutral_items.json")

    # ---- 基础结构 ----
    hero_ids = set()
    if heroes:
        hs = heroes.get("heroes", [])
        if not isinstance(hs, list):
            err("heroes.json: heroes 不是数组")
            hs = []
        for h in hs:
            if not h.get("id"):
                err("heroes.json: 缺少 id 的条目")
                continue
            hero_ids.add(h["id"])
        dup = [k for k, v in Counter(h["id"] for h in hs).items() if v > 1]
        if dup:
            err(f"heroes.json: 重复 id {dup}")
        if len(hs) < 100:
            warn(f"heroes.json: 仅 {len(hs)} 个英雄，可能缺新英雄")
        # 别名重复（同一英雄内）
        for h in hs:
            al = h.get("aliases") or []
            d = [k for k, v in Counter(al).items() if v > 1]
            if d:
                err(f"heroes.json: {h['id']} aliases 重复 {d}")

    rule_ids = set()
    if rules:
        for r in rules.get("principles", []):
            if not r.get("id"):
                err("rules.json: 缺少 id")
                continue
            rule_ids.add(r["id"])
            for f in ("category", "title", "statement", "certainty"):
                if not r.get(f):
                    err(f"rules.json: {r['id']} 缺少字段 {f}")
            if r.get("certainty") not in ("verified", "reasoned", "assumption", "stable"):
                warn(f"rules.json: {r['id']} certainty={r.get('certainty')} 非标准值")
        dup = [k for k, v in Counter(x["id"] for x in rules["principles"]).items() if v > 1]
        if dup:
            err(f"rules.json: 重复 id {dup}")

    # ---- 推理层 ----
    inf_ids = set()
    if inference:
        for i in inference.get("inferences", []):
            if not i.get("id"):
                err("inference.json: 缺少 id")
                continue
            inf_ids.add(i["id"])
            for f in ("title", "derivation", "conclusion", "application", "confidence"):
                if not i.get(f):
                    err(f"inference.json: {i['id']} 缺少字段 {f}")
            if i.get("confidence") not in ("verified", "reasoned", "assumption"):
                err(f"inference.json: {i['id']} confidence={i.get('confidence')} 非法")
            for p in i.get("premises", []):
                if p not in rule_ids and p not in inf_ids:
                    err(f"inference.json: {i['id']} premise 引用不存在的 id: {p}")
            if not i.get("premises"):
                warn(f"inference.json: {i['id']} 无 premises")
        dup = [k for k, v in Counter(x["id"] for x in inference["inferences"]).items() if v > 1]
        if dup:
            err(f"inference.json: 重复 id {dup}")

    # ---- 克制层 ----
    if matchups:
        legend = set(matchups.get("meta", {}).get("basis_legend", {}))
        seen = {}
        for m in matchups.get("matchups", []):
            h, t, rel, basis = m.get("hero_id"), m.get("target_id"), m.get("relation"), m.get("basis")
            for f in ("hero_id", "target_id", "relation", "reason", "basis"):
                if not m.get(f):
                    err(f"matchups.json: 缺少字段 {f} -> {h} {t}")
            if rel not in ("counter", "countered_by", "synergy"):
                err(f"matchups.json: 非法 relation {rel} ({h}->{t})")
            if legend and basis not in legend:
                err(f"matchups.json: 非法 basis {basis} ({h}->{t})")
            if hero_ids and h not in hero_ids:
                err(f"matchups.json: hero_id 不存在 {h}")
            if hero_ids and t not in hero_ids:
                err(f"matchups.json: target_id 不存在 {t}")
            if h == t:
                err(f"matchups.json: 自指 {h}")
            key = (h, t)
            if key in seen:
                err(f"matchups.json: 重复 pair {h}->{t}")
            seen[key] = 1
            rev = (t, h)
            if rev in seen:
                INFO.append(f"matchups.json: 双向成对记录 {h}<->{t}（counter/countered_by 或 synergy 双写，属同一对关系的两种表述）")

        if hero_ids:  # 覆盖度：每英雄至少一条克制/配合记录
            cov = {h: 0 for h in hero_ids}
            for m in matchups.get("matchups", []):
                for k in (m.get("hero_id"), m.get("target_id")):
                    if k in cov:
                        cov[k] += 1
            zero = [h for h, c in cov.items() if c == 0]
            if zero:
                INFO.append(f"matchups.json: 覆盖度 {len(cov) - len(zero)}/{len(cov)} 英雄至少有 1 条记录；"
                            f"尚无覆盖({len(zero)}): {', '.join(sorted(zero))}")

    # ---- 装备层 ----
    if items:
        cats = set()
        allowed_extra = {"mobility", "consumable", "magic"}
        for it in items.get("items", []):
            for f in ("id", "name_zh", "name_en", "category", "purpose", "coach_note", "source"):
                if not it.get(f):
                    err(f"items.json: {it.get('id')} 缺少字段 {f}")
            cats.add(it.get("category"))
            for p in it.get("core_for", []):
                if not isinstance(p, int) or not 1 <= p <= 5:
                    err(f"items.json: {it.get('id')} core_for 值非法 {p}")
        dup = [k for k, v in Counter(x["id"] for x in items["items"]).items() if v > 1]
        if dup:
            err(f"items.json: 重复 id {dup}")
        unknown = cats - allowed_extra - {"defensive", "utility", "support", "damage", "offensive"}
        if unknown:
            warn(f"items.json: 未登记的 category {unknown}")

    # ---- 战术层 ----
    if tactics:
        tids = set(tactics)
        for sec in ("draft", "decisions"):
            if sec in tactics:
                for p in tactics[sec].get("premises", []):
                    if p not in rule_ids and p not in inf_ids:
                        err(f"tactics.json: {sec} premise 引用不存在 {p}")

    # ---- 天赋 / 中立 ----
    if talents:
        th = talents.get("heroes", {})
        if isinstance(th, dict):
            if hero_ids and set(th) - hero_ids:
                err(f"talents.json: 含 heroes.json 中没有的英雄 {sorted(set(th) - hero_ids)}")
            if hero_ids and hero_ids - set(th):
                warn(f"talents.json: 缺少英雄 {sorted(hero_ids - set(th))}")
            for hid, v in th.items():
                lv = v.get("levels", [])
                if len(lv) != 4:
                    err(f"talents.json: {hid} 层数 {len(lv)} != 4")
                for L in lv:
                    if len(L.get("options", [])) != 2:
                        err(f"talents.json: {hid} L{L.get('level')} 选项数 != 2")
    if neutral:
        cls = neutral.get("classes", {})
        for k, v in cls.items():
            n = sum(len(g.get("items", g)) if isinstance(g, dict) else len(g) for g in v.get("groups", [])) if isinstance(v, dict) else 0
            if isinstance(v, dict) and len(v.get("groups", [])) != 4:
                err(f"neutral_items.json: class {k} 组数 {len(v.get('groups', []))} != 4")
    # ---- index 计数同步 ----
    idx = json.loads((Path(ROOT) / "index.json").read_text(encoding="utf-8")) if os.path.exists(os.path.join(ROOT, "index.json")) else None
    if idx:
        actual = {
            "data/heroes.json": len(heroes.get("heroes", [])) if heroes else 0,
            "data/rules.json": len(rules.get("principles", [])) if rules else 0,
            "data/inference.json": len(inference.get("inferences", [])) if inference else 0,
            "data/matchups.json": len(matchups.get("matchups", [])) if matchups else 0,
            "data/items.json": len(items.get("items", [])) if items else 0,
            "data/tactics.json": len([k for k in tactics if k != "meta"]) if tactics else 0,
        }
        for mod in idx.get("modules", []):
            f = mod.get("file")
            if f in actual and mod.get("count") != actual[f]:
                err(f"index.json: {f} count={mod.get('count')} 实际 {actual[f]}")

    report = {
        "generated_by": "scripts/quality_audit.py",
        "error_count": len(ERRORS),
        "warning_count": len(WARNINGS),
        "info_count": len(INFO),
        "errors": ERRORS,
        "warnings": WARNINGS,
        "infos": INFO,
        "counts": {
            "heroes": len(hero_ids),
            "rules": len(rule_ids),
            "inference": len(inf_ids),
        },
    }
    if "--write-report" in sys.argv:
        with open(os.path.join(D, "quality_report.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not ERRORS else 1


if __name__ == "__main__":
    sys.exit(main())
