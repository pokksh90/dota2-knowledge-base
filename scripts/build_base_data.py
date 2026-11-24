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
    "anti-mage": ["敌法", "敌法师", "AM", "阿敌", "魔抗刺客"],
    "phantom-assassin": ["幻刺", "PA", "幻影刺客", "大幻刺"],
    "juggernaut": ["剑圣", "Jugg", "主宰", "剑刃风暴"],
    "faceless-void": ["虚空", "FV", "虚空假面", "虚空大"],
    "spectre": ["幽鬼", "Spec", "鬼影", "幽鬼大"],
    "medusa": ["大娜迦", "蛇女", "美杜莎", "梅杜莎", "Medu"],
    "wraith-king": ["骷髅王", "WK", "骷髅", "冥魂大帝"],
    "lifestealer": ["小狗", "食尸鬼", "LS", "小狗人", "噬魂鬼"],
    "terrorblade": ["TB", "恐怖", "灵魂守卫", "恐怖利刃"],
    "luna": ["月骑", "Luna", "月光", "露娜"],
    "slark": ["小鱼", "小鱼人", "Slark", "斯拉克", "夜叉鱼"],
    "weaver": ["蚂蚁", "甲虫", "编织者", "Weaver"],
    "drow-ranger": ["小黑", "Drow", "弓箭手", "卓尔", "黑暗游侠"],
    "sven": ["流浪", "流浪剑客", "斯温", "SVEN"],
    "naga-siren": ["小娜迦", "娜迦", "Naga", "娜迦海妖", "海妖"],
    "troll-warlord": ["巨魔", "TW", "巨魔战将"],
    "morphling": ["水人", "Morph", "变体精灵"],
    "storm-spirit": ["蓝猫", "ST", "风暴之灵", "风暴"],
    "shadow-fiend": ["影魔", "SF", "影子", "影魔大"],
    "invoker": ["卡尔", "召唤师", "Invoker"],
    "templar-assassin": ["圣堂", "TA", "圣堂刺客", "隐匿"],
    "queen-of-pain": ["女王", "痛苦女王", "QoP", "痛苦"],
    "zeus": ["宙斯", "Zeus", "天神", "雷神"],
    "lina": ["火女", "秀逗", "Lina", "莉娜"],
    "puck": ["精灵龙", "帕克", "Puck"],
    "ember-spirit": ["火猫", "Ember", "灰烬之灵"],
    "void-spirit": ["紫猫", "Void", "虚无之灵"],
    "sniper": ["火枪", "矮子", "狙击手", "Sniper", "矮人狙击手"],
    "kunkka": ["船长", "昆卡", "Kunkka"],
    "leshrac": ["拉席克", "TS", "灵魂", "受折磨的灵魂"],
    "pugna": ["骨法", "Pugna", "帕格纳", "骨法男"],
    "axe": ["斧王", "Axe", "老斧", "斧头"],
    "centaur-warrunner": ["半人马", "CW", "人马", "半人马战行者"],
    "tidehunter": ["潮汐", "TH", "潮汐猎人", "大潮汐"],
    "slardar": ["大鱼", "大鱼人", "Slardar", "斯拉达", "鱼人守卫"],
    "legion-commander": ["军团", "LC", "军团指挥官", "军团令"],
    "mars": ["玛尔斯", "Mars", "战神", "马尔斯"],
    "bristleback": ["钢背", "BB", "猪", "钢背猪", "钢背兽"],
    "timbersaw": ["伐木机", "Timber", "伐木"],
    "underlord": ["大屁股", "深渊领主", "UL", "大屁股男"],
    "doom": ["末日", "Doom", "末日使者"],
    "night-stalker": ["夜魔", "NS", "暗夜魔王", "暗夜"],
    "beastmaster": ["兽王", "BM", "野性之心"],
    "dark-seer": ["黑贤", "DS", "黑暗贤者"],
    "sand-king": ["沙王", "SK", "沙王王"],
    "enigma": ["谜团", "Enigma", "黑洞", "大谜团"],
    "earth-spirit": ["土猫", "Earth", "大地之灵", "土灵"],
    "tusk": ["海民", "Tusk", "海象", "巨牙海民"],
    "mirana": ["白虎", "Mirana", "月女", "米拉娜"],
    "pudge": ["屠夫", "Pudge", "胖子", "帕吉"],
    "rubick": ["拉比克", "Rubick", "大魔导师", "偷技能"],
    "skywrath-mage": ["天怒", "SM", "天怒法师", "天怒女"],
    "bounty-hunter": ["赏金", "BH", "赏金猎人"],
    "spirit-breaker": ["白牛", "SB", "裂魂人"],
    "crystal-maiden": ["冰女", "CM", "水晶室女", "冰妹"],
    "dazzle": ["戴泽", "暗牧", "Dazzle", "暗影牧师"],
    "witch-doctor": ["巫医", "WD", "巫医男"],
    "lich": ["巫妖", "Lich", "老巫妖"],
    "disruptor": ["干扰者", "干扰", "Disruptor"],
    "oracle": ["神谕", "Oracle", "神谕者"],
    "shadow-shaman": ["小Y", "暗影萨满", "SS", "萨满"],
    "io": ["小精灵", "精灵", "IO", "艾欧"],
    "treant-protector": ["大树", "Treant", "树精", "树精卫士"],
    "vengeful-spirit": ["复仇", "VS", "魂女", "复仇之魂"],
    "warlock": ["术士", "WL", "大术士"],
    "bane": ["祸乱", "Bane", "祸乱之源"],
    "keeper-of-the-light": ["光法", "KOTL", "光守", "光之守卫"],
    "grimstroke": ["墨客", "Grim", "画师", "天涯墨客"],
    "phantom-lancer": ["长矛", "PL", "长矛手", "幻影长矛手"],
    "chaos-knight": ["混沌", "CK", "混沌骑士"],
    "ursa": ["熊战", "Ursa", "大熊", "熊战士"],
    "bloodseeker": ["血魔", "BS", "嗜血狂魔"],
    "alchemist": ["炼金", "Alch", "炼金术士"],
    "gyrocopter": ["飞机", "Gyro", "直升机", "矮人直升机"],
    "monkey-king": ["大圣", "猴子", "MK", "齐天大圣", "悟空"],
    "riki": ["力丸", "隐刺", "Riki", "隐形刺客"],
    "clinkz": ["骨弓", "Clinkz", "小骷髅", "骷髅弓手", "克林克兹"],
    "arc-warden": ["天穹", "AW", "天穹守望者", "天穹守卫"],
    "meepo": ["米波", "Meepo", "地卜师", "地卜"],
    "lone-druid": ["德鲁伊", "熊德", "LD", "德鲁伊大师"],
    "lycan": ["狼人", "Lycan", "狼王"],
    "viper": ["毒龙", "Viper", "亚龙", "冥界亚龙"],
    "batrider": ["蝙蝠", "Bat", "蝙蝠骑士"],
    "windranger": ["风行", "WR", "风女", "风行者"],
    "outworld-destroyer": ["黑鸟", "OD", "神蚀", "殁境神蚀者", "毁灭者"],
    "death-prophet": ["死亡先知", "DP", "死先知"],
    "natures-prophet": ["先知", "NP", "自然先知", "预言者"],
    "visage": ["维萨吉", "Visage", "佣兽", "鸟人"],
    "broodmother": ["蜘蛛", "Brood", "育母", "育母蜘蛛", "蛛母"],
    "tinker": ["修补匠", "Tinker", "修补", "补匠"],
    "huskar": ["神灵", "Huskar", "哈斯卡", "神灵武士"],
    "necrophos": ["死灵法", "Necro", "死灵法师", "瘟疫法师"],
    "magnus": ["猛犸", "Magnus", "马格纳斯"],
    "tiny": ["小小", "Tiny", "山岭巨人", "山岭"],
    "earthshaker": ["神牛", "牛头", "ES", "撼地神牛", "撼地"],
    "razor": ["电棍", "剃刀", "Razor", "闪电男"],
    "venomancer": ["剧毒", "Veno", "剧毒术士"],
    "abaddon": ["亚巴顿", "Abaddon", "死骑", "地狱领主"],
    "undying": ["尸王", "Undying", "不朽尸王", "不朽"],
    "pangolier": ["滚滚", "Pan", "石鳞剑士", "穿山甲"],
    "snapfire": ["老奶奶", "Snap", "电炎", "电炎绝手"],
    "primal-beast": ["原始兽", "PB", "野兽", "原始野兽"],
    "dawnbreaker": ["破晓", "DB", "破晓辰星", "晨曦"],
    "dragon-knight": ["龙骑", "DK", "龙骑士"],
    "ogre-magi": ["蓝胖", "Ogre", "食人魔", "食人魔魔法师"],
    "ancient-apparition": ["冰魄", "AA", "远古冰魄", "远古"],
    "chen": ["陈", "Chen", "圣骑士"],
    "enchantress": ["小鹿", "Ench", "魅惑魔女", "魅惑"],
    "omniknight": ["全能", "Omni", "全能骑士"],
    "jakiro": ["双头龙", "Jakiro", "冰火", "杰奇洛"],
    "winter-wyvern": ["冰龙", "WW", "寒冬", "寒冬飞龙"],
    "phoenix": ["凤凰", "Phoenix", "火鸟", "火凤凰"],
    "marci": ["玛西", "Marci"],
    "lion": ["莱恩", "Lion", "恶魔巫师", "狮王"],
    "silencer": ["沉默", "Silencer", "沉默术士"],
    "brewmaster": ["酒仙", "Panda", "熊猫", "熊猫酒仙"],
    "clockwerk": ["发条", "Clock", "发条技师", "发条男"],
    "shadow-demon": ["暗影魔", "SD", "暗影恶魔"],
    "elder-titan": ["上古巨神", "ET", "巨神", "上古"],
    "dark-willow": ["花仙子", "DW", "邪影芳灵", "花仙"],
    "hoodwink": ["松鼠", "Hood", "森海", "森海飞霞"],
    "techies": ["炸弹人", "Techies", "地雷", "工程师"],
    "nyx-assassin": ["司夜刺客", "Nyx", "夜刺客", "夜神刺客"],
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
        zh = [h["name_zh"]] + ZH_ALIASES.get(hid, []) if h.get("name_zh") else ZH_ALIASES.get(hid, [])
        h["aliases"] = sorted(set(zh + en), key=len, reverse=True)
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
