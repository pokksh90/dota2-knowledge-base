#!/usr/bin/env python3
"""从 dotaconstants(公开数据) 构建基础数据层：
   data/hero_base.json    英雄基础属性 + 技能列表（名称/描述/蓝耗/CD/伤害类型/是否穿BKB）
   data/item_base.json    道具基础数据（价格/属性/合成件/主动效果）
   data/ability_base.json 技能基础数据（按技能 key 索引）
并给 data/heroes.json 补齐 aliases（中文绰号 + 英文缩写）。

用法: python3 scripts/build_base_data.py [--offline <缓存目录>]
数据源: https://raw.githubusercontent.com/odota/dotaconstants/master/build/
"""
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BASE = "https://raw.githubusercontent.com/odota/dotaconstants/master/build"
FILES = ["heroes", "items", "abilities", "hero_abilities"]

# 少数与 dotaconstants 命名不一致的英雄需要手工映射
NPC_OVERRIDE = {"outworld-destroyer": "76"}  # dotaconstants 里殁境神蚀者键名为数字 76

ZH_ALIASES = {
    "anti-mage": ["敌法", "AM", "阿敌"],
    "phantom-assassin": ["幻刺", "PA"],
    "juggernaut": ["剑圣", "Jugg"],
    "faceless-void": ["虚空", "FV"],
    "spectre": ["幽鬼", "Spec"],
    "medusa": ["大娜迦", "蛇女", "美杜莎"],
    "wraith-king": ["骷髅王", "WK"],
    "lifestealer": ["小狗", "食尸鬼", "LS"],
    "terrorblade": ["TB", "灵魂守卫", "恐怖"],
    "luna": ["月骑", "月光"],
    "slark": ["小鱼", "小鱼人"],
    "weaver": ["蚂蚁", "甲虫"],
    "drow-ranger": ["小黑", "Drow", "弓箭手"],
    "sven": ["流浪", "流浪剑客"],
    "naga-siren": ["小娜迦", "娜迦"],
    "troll-warlord": ["巨魔", "TW"],
    "morphling": ["水人", "Morph"],
    "storm-spirit": ["蓝猫", "ST"],
    "shadow-fiend": ["影魔", "SF", "影子"],
    "invoker": ["卡尔", "召唤师"],
    "templar-assassin": ["圣堂", "TA"],
    "queen-of-pain": ["女王", "QoP", "痛苦女王"],
    "zeus": ["宙斯", "天神"],
    "lina": ["火女", "秀逗"],
    "puck": ["精灵龙", "帕克"],
    "ember-spirit": ["火猫", "Ember"],
    "void-spirit": ["紫猫", "Void"],
    "sniper": ["火枪", "矮子", "狙击手"],
    "kunkka": ["船长", "昆卡"],
    "leshrac": ["拉席克", "TS", "灵魂"],
    "pugna": ["骨法", "骨弓法"],
    "axe": ["斧王", "老斧"],
    "centaur-warrunner": ["半人马", "CW"],
    "tidehunter": ["潮汐", "TH"],
    "slardar": ["大鱼", "大鱼人"],
    "legion-commander": ["军团", "LC"],
    "mars": ["玛尔斯", "战神"],
    "bristleback": ["钢背", "BB", "猪"],
    "timbersaw": ["伐木机", "Timber"],
    "underlord": ["大屁股", "深渊领主", "UL"],
    "doom": ["末日", "末日使者"],
    "night-stalker": ["夜魔", "NS"],
    "beastmaster": ["兽王", "BM"],
    "dark-seer": ["黑贤", "DS"],
    "sand-king": ["沙王", "SK"],
    "enigma": ["谜团", "黑洞"],
    "earth-spirit": ["土猫", "土灵"],
    "tusk": ["海民", "海象"],
    "mirana": ["白虎", "月女"],
    "pudge": ["屠夫", "胖子"],
    "rubick": ["拉比克", "大魔导师"],
    "skywrath-mage": ["天怒", "SM"],
    "bounty-hunter": ["赏金", "BH"],
    "spirit-breaker": ["白牛", "SB"],
    "crystal-maiden": ["冰女", "CM"],
    "dazzle": ["戴泽", "暗牧"],
    "witch-doctor": ["巫医", "WD"],
    "lich": ["巫妖", "Lich"],
    "disruptor": ["干扰者", "干扰"],
    "oracle": ["神谕", "神谕者"],
    "shadow-shaman": ["小Y", "暗影萨满", "SS"],
    "io": ["小精灵", "精灵"],
    "treant-protector": ["大树", "树精"],
    "vengeful-spirit": ["复仇", "VS", "魂女"],
    "warlock": ["术士", "WL"],
    "bane": ["祸乱", "祸乱之源"],
    "keeper-of-the-light": ["光法", "KOTL", "光守"],
    "grimstroke": ["墨客", "画师"],
    "phantom-lancer": ["长矛", "PL", "长矛手"],
    "chaos-knight": ["混沌", "CK"],
    "ursa": ["熊战", "大熊"],
    "bloodseeker": ["血魔", "BS"],
    "alchemist": ["炼金", "Alch"],
    "gyrocopter": ["飞机", "直升机"],
    "monkey-king": ["大圣", "猴子", "MK"],
    "riki": ["力丸", "隐刺"],
    "clinkz": ["骨弓", "小骷髅", "骷髅弓手"],
    "arc-warden": ["天穹", "AW"],
    "meepo": ["米波", "地卜师"],
    "lone-druid": ["德鲁伊", "熊德", "LD"],
    "lycan": ["狼人", "Lycan"],
    "viper": ["毒龙", "亚龙"],
    "batrider": ["蝙蝠", "Bat"],
    "windranger": ["风行", "WR", "风女"],
    "outworld-destroyer": ["黑鸟", "OD", "神蚀"],
    "death-prophet": ["死亡先知", "DP"],
    "natures-prophet": ["先知", "NP"],
    "visage": ["维萨吉", "佣兽"],
    "broodmother": ["蜘蛛", "育母"],
    "tinker": ["修补匠", "Tinker", "修补"],
    "huskar": ["神灵", "哈斯卡"],
    "necrophos": ["死灵法", "Necro"],
    "magnus": ["猛犸", "Magnus"],
    "tiny": ["小小", "山岭"],
    "earthshaker": ["神牛", "牛头", "ES"],
    "razor": ["电棍", "剃刀"],
    "venomancer": ["剧毒", "Veno"],
    "abaddon": ["亚巴顿", "死骑"],
    "undying": ["尸王", "不朽"],
    "pangolier": ["滚滚", "石鳞剑士"],
    "snapfire": ["老奶奶", "电炎"],
    "primal-beast": ["原始兽", "PB"],
    "dawnbreaker": ["破晓", "DB"],
    "dragon-knight": ["龙骑", "DK"],
    "ogre-magi": ["蓝胖", "食人魔"],
    "ancient-apparition": ["冰魄", "AA"],
    "chen": ["陈", "圣骑士"],
    "enchantress": ["小鹿", "Ench"],
    "omniknight": ["全能", "Omni"],
    "jakiro": ["双头龙", "冰火"],
    "winter-wyvern": ["冰龙", "WW"],
    "phoenix": ["凤凰", "火鸟"],
    "marci": ["玛西", "Marci"],
    "lion": ["莱恩", "恶魔巫师"],
    "silencer": ["沉默", "沉默术士"],
    "brewmaster": ["酒仙", "熊猫"],
    "clockwerk": ["发条", "Clock"],
    "shadow-demon": ["暗影魔", "SD"],
    "elder-titan": ["上古巨神", "ET", "巨神"],
    "dark-willow": ["花仙子", "DW"],
    "hoodwink": ["松鼠", "森海"],
    "techies": ["炸弹人", "地雷"],
    "nyx-assassin": ["司夜刺客", "夜刺客", "Nyx"],
}


def fetch(name, cache_dir):
    p = Path(cache_dir) / f"dc_{name}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    url = f"{BASE}/{name}.json"
    with urllib.request.urlopen(url, timeout=60) as r:
        raw = r.read().decode("utf-8")
    p.write_bytes(raw.encode("utf-8"))
    return json.loads(raw)


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def main():
    cache = sys.argv[sys.argv.index("--offline") + 1] if "--offline" in sys.argv else "/tmp"
    heroes_dc = fetch("heroes", cache)
    items_dc = fetch("items", cache)
    abilities_dc = fetch("abilities", cache)
    hero_ab_dc = fetch("hero_abilities", cache)

    ours = json.loads((DATA / "heroes.json").read_text(encoding="utf-8"))
    heroes = ours["heroes"]

    bykey = {norm(k): k for k in heroes_dc}
    bynpc = {norm(v["name"].replace("npc_dota_hero_", "")): k for k, v in heroes_dc.items()}
    byloc = {norm(v.get("localized_name", "")): k for k, v in heroes_dc.items() if v.get("localized_name")}

    hero_base, ability_base, missing = {}, {}, []
    for h in heroes:
        hid = h["id"]
        key = (NPC_OVERRIDE.get(hid) or bykey.get(norm(hid)) or bynpc.get(norm(hid))
               or byloc.get(norm(h.get("name_en", ""))))
        if not key:
            missing.append(hid)
            continue
        src = heroes_dc[key]
        stats = {k: src[k] for k in (
            "id", "primary_attr", "attack_type", "base_health", "base_health_regen", "base_mana",
            "base_mana_regen", "base_armor", "base_mr", "base_attack_min", "base_attack_max",
            "base_str", "base_agi", "base_int", "str_gain", "agi_gain", "int_gain",
            "attack_range", "attack_rate", "base_attack_time", "move_speed", "turn_rate",
            "day_vision", "night_vision", "legs") if k in src}
        ab_list = []  # 只存技能 key，明细见 ability_base.json，避免重复
        for ab_key in (hero_ab_dc.get(src["name"], {}) or {}).get("abilities", []):
            if ab_key.startswith("generic") or ab_key not in abilities_dc:
                continue
            a = abilities_dc[ab_key]
            attrib = [{"key": x["key"], "header": x.get("header") or x.get("display", ""), "value": x["value"]}
                      for x in a.get("attrib", []) if not x.get("generated")][:10]
            entry = {
                "key": ab_key,
                "name_en": a.get("dname", ""),
                "desc": re.sub(r"\s+", " ", a.get("desc", "")).strip(),
                "behavior": a.get("behavior"),
                "dmg_type": a.get("dmg_type"),
                "bkbpierce": a.get("bkbpierce"),
                "mana_cost": a.get("mc", False),
                "cooldown": a.get("cd", False),
                "attrib": attrib,
            }
            ab_list.append(ab_key)
            ability_base[ab_key] = entry
        hero_base[hid] = {"npc_key": key, **stats, "abilities": ab_list}

        # aliases：中文绰号 + dotaconstants 英文别名
        en = [x for x in (src.get("aliases") or [])
              if x and x[:1].isupper() and len(x) >= 3 and norm(x) != norm(h.get("name_en", ""))]
        h["aliases"] = sorted(set(ZH_ALIASES.get(hid, []) + en), key=len, reverse=True)
        h["base_stats"] = stats

    ours["heroes"] = heroes
    (DATA / "heroes.json").write_text(json.dumps(ours, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA / "hero_base.json").write_text(json.dumps(
        {"meta": {"source": "dotaconstants", "note": "数值为当前公开版本基础值，版本更新后需重新生成", "built_by": "scripts/build_base_data.py"},
         "heroes": hero_base}, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA / "ability_base.json").write_text(json.dumps(
        {"meta": {"source": "dotaconstants", "count": len(ability_base)}, "abilities": ability_base},
        ensure_ascii=False, indent=2), encoding="utf-8")

    # 道具
    items_out = {}
    for k, v in items_dc.items():
        cost = v.get("cost", 0)
        if not cost or v.get("qual") == "recipe":
            continue
        items_out[k] = {
            "name_en": v.get("dname", ""),
            "cost": cost,
            "qual": v.get("qual"),
            "behavior": v.get("behavior"),
            "components": v.get("components") or [],
            "attrib": [{"key": x["key"], "header": x.get("header") or x.get("display", ""), "value": x["value"]}
                       for x in v.get("attrib", []) if not x.get("generated")][:12],
            "abilities": [{"title": a.get("title"), "type": a.get("type"), "description": re.sub(r"\s+", " ", a.get("description", "")).strip()}
                          for a in v.get("abilities", []) if a.get("description")],
            "cd": v.get("cd", False),
            "mc": v.get("mc", False),
        }
    (DATA / "item_base.json").write_text(json.dumps(
        {"meta": {"source": "dotaconstants", "count": len(items_out), "note": "价格/属性为公开版本基础值"},
         "items": items_out}, ensure_ascii=False, indent=2), encoding="utf-8")

    print("hero_base:", len(hero_base), "abilities:", len(ability_base), "items:", len(items_out))
    if missing:
        print("未匹配英雄:", missing)


if __name__ == "__main__":
    main()
