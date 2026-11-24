#!/usr/bin/env python3
"""补齐 2023–2026 新英雄（dotaconstants 已有而知识库缺的 4 位）：
   ringmaster 百戏大王 / muerta 琼英碧灵 / kez 凯 / largo 朗戈
   产出：data/heroes.json 条目、hero_base 基础属性、ability_base 技能明细、talents 四层天赋。
数据源（公开）：dotaconstants build/{heroes,hero_abilities,abilities}.json
                Valve datafeed herodata（name_loc 中文名、天赋占位文案）
用法: python3 scripts/add_new_heroes.py [--offline 缓存目录]
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BASE = "https://raw.githubusercontent.com/odota/dotaconstants/master/build"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

HEROES = [
    {
        "id": "ringmaster", "npc": 131, "name_zh": "百戏大王", "name_en": "Ringmaster",
        "position": 5, "lane": "support", "roles": ["support"],
        "tags": ["远程", "强控", "救人", "反幻象", "操作复杂"],
        "coach_note": "远程辅助，一套技能给足控制与救人：驯兽术持续施法后甩鞭造成伤害并恐惧敌人（蓄力越久伤害与恐惧越久），逃生技把友方装进箱子（相位移动、额外魔抗与减速抗性、无法被指定），尖刀戏掷匕首造成即时伤害+按目标最大生命百分比流血，聚光灯让灯下敌人几率丢失攻击、隐身显形、幻象持续掉血，大招奇观轮滚出后击退并减速、敌人盯着轮子看会被迷住走向它、首个着迷者触发爆炸倒计时。被动暗黑狂欢主持让附近敌方英雄阵亡时随机获得一次性纪念品（幻象/力量/推人/独轮车等）。定位是功能型 5 号：靠控制链和救人保核，不靠输出。",
        "strengths": ["控制与恐惧时长可蓄力", "唯一能装箱救人的辅助", "聚光灯天然反幻象反隐身"],
        "weaknesses": ["技能多、操作门槛高", "本体脆、怕被打断持续施法", "清线推塔能力弱"],
        "aliases": ["百戏大王", "百戏", "Ringmaster", "RM"],
    },
    {
        "id": "muerta", "npc": 138, "name_zh": "琼英碧灵", "name_en": "Muerta",
        "position": 1, "lane": "safe", "roles": ["carry"],
        "tags": ["远程", "智力核心", "混伤", "虚无", "后期"],
        "coach_note": "智力远程核心（也可中单）。输出靠普攻+技能混伤：弹无虚发向单位或树开枪、命中后沿矢量方向跳弹并对穿过的单位造成伤害、击中英雄停下并恐惧；唤魂召亡魂环绕区域，减速+穿越时伤害与沉默；神枪在手开启后普攻有几率再射一枪（后期主要 DPS 来源）；幽魂子弹把目标打成虚无并击退（对物理免疫、不能攻击、受魔法伤害增加），是保命/开团工具。大招越界让自身进入虚无并获得攻击力与相位移动，被动使她始终能攻击虚无目标。被动超自然按附近敌方英雄阵亡叠技能增强。怕高爆发法系与长手消耗，需要 BKB/魔抗撑过中期。",
        "strengths": ["普攻与技能双线输出", "虚无机制克制纯物理", "后期叠层带来技能增强"],
        "weaknesses": ["身板脆、怕爆发法系", "前期刷钱与对线都偏弱", "依赖装备成型"],
        "aliases": ["琼英碧灵", "Muerta", "muerta"],
    },
    {
        "id": "kez", "npc": 145, "name_zh": "凯", "name_en": "Kez",
        "position": 1, "lane": "safe", "roles": ["carry"],
        "tags": ["近战", "敏捷核心", "双形态", "高操作", "爆发"],
        "coach_note": "高操作敏捷近战核心。核心是流派变换：长刀形态偏持续伤害与控制（回音重斩直线两段斩击并减速、制敌爪钩钩单位或树摆荡过去、影武长刀给攻击和技能叠可叠加持续伤害并可主动引爆定身、猛禽之舞短暂无敌并斩出按最大生命百分比的辐射斩击带吸血）；双钗形态偏暴击与反打（翔影之钗普攻几率暴击、可主动缴械自己并锁定朝向招架该方向攻击、利爪飞掷掷钗沉默、天隼冲击冲向目标并重复一次攻击、渡鸦之纱隐身+提速+削弱敌方视野）。切换武器后首次攻击/技能有额外收益。操作量大、连招依赖熟练度，怕硬控与范围伤害，需要 BKB 与吸血续航。",
        "strengths": ["两套武器覆盖持续输出与反打", "猛禽之舞提供无敌窗口", "自带沉默、招架、隐身多种应对手段"],
        "weaknesses": ["操作与连招要求极高", "近战贴身，怕硬控和 AOE", "技能多，容易打空/浪费冷却"],
        "aliases": ["凯", "Kez", "kez"],
    },
    {
        "id": "largo", "npc": 155, "name_zh": "朗戈", "name_en": "Largo",
        "position": 5, "lane": "support", "roles": ["support"],
        "tags": ["近战", "力量辅助", "治疗", "增幅", "节奏型"],
        "coach_note": "力量近战辅助，玩法围绕大招两栖狂想曲：开启后被缴械、技能栏切换成三首乐曲（巨腹闪电战：范围魔法伤害并给友军技能增强与攻击附加魔法伤害；疾步生风：给附近友军提速与减速抗性；大屿灵药：治疗附近友军），只有踩在节拍上弹奏才生效，成功一次叠一层律动（加护甲、降乐曲蓝耗），漏拍掉一层。小技能提供拉人与控制：动人之舐舔目标并拉回一小段、附弱驱散、击杀或驱散后自身回血；蛙力千钧扔小青蛙落地反复践踏（伤害+短晕+减速）；灵呱一闪给友方英雄降蓝耗并让伤害在后续时间里回响（该英雄耗蓝会缩短增益时长）。被动安可延长自身/队友增益持续时间。定位是节奏型 5 号，价值在治疗+增幅+控制，不是输出。",
        "strengths": ["三首乐曲覆盖伤害/提速/治疗", "给核心降蓝耗+伤害回响的增幅", "舔人弱驱散+拉回的先手小控制"],
        "weaknesses": ["大招缴械自己、弹奏需节拍操作", "近战辅助身板一般、怕被集火", "增幅依赖队友配合"],
        "aliases": ["朗戈", "Largo", "largo"],
    },
]

STAT_KEYS = (
    "id", "primary_attr", "attack_type", "base_health", "base_health_regen", "base_mana",
    "base_mana_regen", "base_armor", "base_mr", "base_attack_min", "base_attack_max",
    "base_str", "base_agi", "base_int", "str_gain", "agi_gain", "int_gain",
    "attack_range", "attack_rate", "base_attack_time", "move_speed", "turn_rate",
    "day_vision", "night_vision", "legs",
)


def fetch_json(url, cache):
    p = cache / url.rsplit("/", 1)[-1].replace("herodata", "herodata")
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 DotaKB"})
    raw = OPENER.open(req, timeout=120).read().decode("utf-8")
    p.write_text(raw, encoding="utf-8")
    return json.loads(raw)


def fetch_datafeed(npc, lang, cache):
    p = cache / f"datafeed_{npc}_{lang}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    url = f"https://www.dota2.com/datafeed/herodata?language={lang}&hero_id={npc}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 DotaKB"})
    d = json.load(OPENER.open(req, timeout=120))
    h = d["result"]["data"]["heroes"][0]
    p.write_text(json.dumps(h, ensure_ascii=False), encoding="utf-8")
    return h


def ability_entry(key, ab):
    attrib = [{"key": x["key"], "header": x.get("header") or x.get("display", ""), "value": x["value"]}
              for x in ab.get("attrib", []) if x.get("key") and not x.get("generated")][:10]
    return {
        "key": key,
        "name_en": ab.get("dname", ""),
        "desc": re.sub(r"\s+", " ", ab.get("desc", "")).strip(),
        "behavior": ab.get("behavior"),
        "dmg_type": ab.get("dmg_type"),
        "bkbpierce": ab.get("bkbpierce"),
        "mana_cost": ab.get("mc", False),
        "cooldown": ab.get("cd", False),
        "attrib": attrib,
    }


NUM = re.compile(r"[+\-]?\d+(?:\.\d+)?")


def main():
    cache = Path(sys.argv[sys.argv.index("--offline") + 1] if "--offline" in sys.argv else "/tmp")
    dc_heroes = fetch_json(f"{BASE}/heroes.json", cache)
    dc_ab = fetch_json(f"{BASE}/abilities.json", cache)
    dc_ha = fetch_json(f"{BASE}/hero_abilities.json", cache)

    heroes_doc = json.loads((DATA / "heroes.json").read_text(encoding="utf-8"))
    have = {h["id"] for h in heroes_doc["heroes"]}
    hb_doc = json.loads((DATA / "hero_base.json").read_text(encoding="utf-8"))
    ab_doc = json.loads((DATA / "ability_base.json").read_text(encoding="utf-8"))
    tal_doc = json.loads((DATA / "talents.json").read_text(encoding="utf-8"))

    added = []
    for spec in HEROES:
        hid = spec["id"]
        if hid in have:
            continue
        src = dc_heroes[str(spec["npc"])]
        if src["name"].replace("npc_dota_hero_", "") != hid:
            raise SystemExit(f"id 不一致: {hid} vs {src['name']}")
        zh_feed = fetch_datafeed(spec["npc"], "schinese", cache)
        en_feed = fetch_datafeed(spec["npc"], "english", cache)

        stats = {k: src[k] for k in STAT_KEYS if k in src}
        entry = {"id": hid, "name_zh": zh_feed["name_loc"].strip(), "name_en": spec["name_en"],
                 "position": spec["position"], "lane": spec["lane"], "roles": spec["roles"],
                 "tags": spec["tags"], "coach_note": spec["coach_note"],
                 "strengths": spec["strengths"], "weaknesses": spec["weaknesses"],
                 "source": "verified", "aliases": spec["aliases"], "base_stats": stats}

        ab_keys = [k for k in (dc_ha.get(src["name"], {}) or {}).get("abilities", [])
                   if not k.startswith("generic") and k in dc_ab]
        base = {"npc_key": str(spec["npc"])}
        base.update({k: src[k] for k in STAT_KEYS if k in src})
        base["abilities"] = ab_keys

        talents = []
        feed_talents = {t["name"]: t for t in zh_feed.get("talents", [])}
        feed_en = {t["name"]: t for t in en_feed.get("talents", [])}
        names = [t["name"] for t in zh_feed.get("talents", [])]
        if len(names) != 8:  # 兜底：用 hero_abilities（按 level 排序，可能含额外条目）
            raw = (dc_ha.get(src["name"], {}) or {}).get("talents", [])
            names = [x["name"] if isinstance(x, dict) else x for x in raw][:8]
        for i in range(0, len(names), 2):
            level = 10 * (i // 2 + 1)
            opts = []
            for nm in names[i:i + 2]:
                dname = (dc_ab.get(nm) or {}).get("dname") or ""
                nums = NUM.findall(dname)
                zt = feed_talents.get(nm, {})
                et = feed_en.get(nm, {})
                raw_text = et.get("name_loc") or zt.get("name_loc") or None
                opts.append({
                    "name": nm,
                    "text": dname.strip() or (zt.get("name_loc") or "").replace("{", "").replace("}", ""),
                    "text_raw": raw_text,
                    "value_pending": bool(dname and "{" in dname) or not dname,
                    "special_bonus_value": nums[0] if len(nums) == 1 else None,
                })
            talents.append({"level": level, "options": opts})

        for nm in names:
            if nm not in dc_ab:
                print(f"  警告: 天赋 {nm} 不在 abilities.json")

        heroes_doc["heroes"].append(entry)
        hb_doc["heroes"][hid] = base
        for k in ab_keys:
            ab_doc["abilities"][k] = ability_entry(k, dc_ab[k])
        tal_doc["heroes"][hid] = {"levels": talents}
        added.append((hid, len(talents), len(ab_keys)))
        print(f"+ {hid} {entry['name_zh']}: 天赋 {len(talents)} 层 / 技能 {len(ab_keys)} 个")

    heroes_doc["meta"]["count"] = len(heroes_doc["heroes"])
    ab_doc["meta"]["count"] = len(ab_doc["abilities"])
    tal_doc["meta"]["stats"] = {
        "options": sum(len(L["options"]) for e in tal_doc["heroes"].values() for L in e["levels"]),
        "with_value": sum(1 for e in tal_doc["heroes"].values() for L in e["levels"] for o in L["options"] if o["special_bonus_value"]),
        "pending": sum(1 for e in tal_doc["heroes"].values() for L in e["levels"] for o in L["options"] if not o["special_bonus_value"]),
        "text_pending": sum(1 for e in tal_doc["heroes"].values() for L in e["levels"] for o in L["options"] if o["value_pending"]),
    }

    for fn, doc in (("heroes.json", heroes_doc), ("hero_base.json", hb_doc),
                    ("ability_base.json", ab_doc), ("talents.json", tal_doc)):
        (DATA / fn).write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        json.loads((DATA / fn).read_text(encoding="utf-8"))
        print(f"  ok {fn}")

    print(json.dumps({"added": added, "talents_total": tal_doc["meta"]["stats"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
