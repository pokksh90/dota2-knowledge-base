# Dota2 专业知识库（LLM 可消费 · 三层可回溯）

一份面向大语言模型（LLM）应用的**结构化刀塔（Dota 2）领域知识库**。全部内容为公开通用的游戏知识与可复现的逻辑推导，不包含任何个人数据、玩家隐私或非公开信息。

设计取向只有一条：**不堆结论，先给规则，再由规则推出结论**。每条结论都能讲清「为什么」。

---

## 三层架构

```
① 公理层  rules.json      对局结构与底层机制：目标与人数、地图建筑、成长体系、伤害计算、护甲/魔抗、经济经验、视野与先手
        ↓  纯逻辑推导
② 定理层  inference.json  由公理推出的洞察：每条含 前提 → 推导 → 结论 → 应用，并标注 confidence
        ↓  落地到具体对象
③ 应用层  heroes / items / matchups / tactics      英雄定位、装备出装、克制搭配、战术节奏
```

- **`confidence` 分级**：`verified`（公式确定、推导可数学验证）、`reasoned`（逻辑成立但含定性假设）、`assumption`（假设较强，需实测）。
- **为什么这样分层**：网上攻略给的是结论，无法判断对错。把结论反推回底层规则——能从公理推出的才可信；推不出的标为待验证。既能自证正确，也能推出攻略里没有的推论。

## 目录结构

```
├── README.md
├── index.json                # 元数据：版本、板块、条目数、数据源、状态
├── backlog.json              # 完善进度清单与运行记录
├── schema/
│   └── knowledge-schema.json # 各数据文件的字段契约（JSON Schema）
├── data/
│   ├── rules.json            # ① 公理层：63 条底层机制（对局结构+机制细节）
│   ├── inference.json        # ② 定理层：89 条可回溯推导
│   ├── heroes.json           # ③ 英雄与定位（含 aliases 绰号）
│   ├── items.json            # ③ 装备与出装
│   ├── matchups.json         # ③ 克制与搭配
│   ├── patch_stats.json      # ③ 当前版本公开胜率/强度分档（127 英雄）
│   ├── tactics.json          # ③ 战术与节奏
│   ├── hero_base.json        # 基础数据层：英雄属性 + 技能索引
│   ├── ability_base.json     # 基础数据层：790 条技能明细
│   └── item_base.json        # 基础数据层：303 件道具价格与属性
└── scripts/
    ├── fetch_data.py         # 从公开 API 拉取数值并回填
    ├── build_base_data.py     # 从公开常量库重建基础数据层（可重复运行）
    ├── build_patch_stats.py   # 从 OpenDota heroStats 重建当前版本胜率/分档
    └── push_to_github.sh     # 一键建仓/推送
```

## 板块说明

| 文件 | 内容 | 典型用途 |
|------|------|---------|
| `rules.json` | 对局结构（目标/人数/地图/建筑/成长/物品栏/神符肉山/死亡结算/BP）+ 机制细节（伤害公式、护甲魔抗、攻速、经济、经验、视野、先手博弈）；带 `values` 的为逐值核对条款 | 解释类问答的底层依据 |
| `inference.json` | 由公理推导的洞察（前提→推导→结论→应用） | 「为什么该这样打」的推理链 |
| `heroes.json` | 英雄定位 1-5、主/副定位、玩法要点 | 选人、阵容分析 |
| `items.json` | 装备分类、用途、分位置核心出装与情境选择 | 出装建议 |
| `matchups.json` | 英雄 counter / synergy，每条带机制依据 `basis` | 对位与 BP 分析 |
| `patch_stats.json` | 当前版本公开对局胜率/选取率与 S/A/B/C/D 分档；标注样本、窗口与补丁纯度 | 「这版本强不强 / 胜率多少」的统计参考 |
| `tactics.json` | 分线职责、关键时间点、地图目标、团战决策 | 战术节奏建议 |
| `hero_base.json` | 英雄基础属性（三围/血量/护甲/移速/视野）+ 技能 key 索引 | 数值查询、对线强度估算 |
| `ability_base.json` | 每个技能的伤害类型、蓝耗、冷却、是否穿透 BKB、关键数值 | 「这招能不能被 BKB/驱散挡」 |
| `item_base.json` | 道具价格、合成件、属性、主动效果 | 出装成本与属性对比 |
| `talents.json` | 每英雄 4 层 × 2 天赋，含脚本数值 `special_bonus_value` | 10/15/20/25 级加点与强度判断 |
| `neutral_items.json` | 中立装备 T1–T5 候选池（48 件）与打造规则（疯狂石） | 中立装备选择与时间点 |

## 字段契约（摘要）

完整约束见 `schema/knowledge-schema.json`。

- **`id`**：稳定英文小写标识（如 `anti-mage`），供程序索引，**不可随意更改**。
- **`name_zh` / `name_en`**：中文名 / 英文名。
- **`aliases`**：常见中文绰号与英文缩写（如 `敌法`、`AM`、`火枪`），用于把玩家口语对上具体英雄 id。
- **`base_stats`**：基础属性快照，字段含义与 `hero_base.json` 一致。
- **`source`**：`official`（已核对权威源）、`stable`（稳定领域常识）、`pending`（待按当前版本核对）。
- **数值类字段**：来自公开常量库的数值标 `official`；动态统计（胜率、热度）核对前留空或省略，不填猜测值。

## 如何加载与使用

知识库是纯 JSON，任何语言都能读。建议不要在提示词里塞整库，而是**按当前场景检索几条拼进上下文**：

1. 启动时拉取全部 JSON，写入本地缓存，并用 `id` 建立索引（`heroById`、`itemById`）。
2. 按当前局面状态（阶段、阵容、经济等）取 top-k 相关条目。
3. 生成回答时附一条对应的 `inference` / `rules` 机制，让建议「讲得出依据」。

```js
const base = 'https://raw.githubusercontent.com/pokksh90/dota2-knowledge-base/main';
const heroes = await (await fetch(`${base}/data/heroes.json`)).json();
const heroById = Object.fromEntries(heroes.heroes.map(h => [h.id, h]));
const heroByAlias = {};  // 口语 → 英雄 id
heroes.heroes.forEach(h => h.aliases.forEach(a => (heroByAlias[a.toLowerCase()] = h.id)));

// 例：玩家说「虚空这把怎么打」，先解析成英雄 id，再取上下文
const hid = heroByAlias['虚空'];
const ctx = {
  hero: heroById[hid]?.coach_note,
  counters: matchups.matchups.filter(m => m.hero_id === hid).slice(0, 4),
};
```

## 数值核对（precision）

`rules.json` 里带 `values` 字段的条目是**逐值核对**过的硬条款，可用 `meta.sources` 回溯到具体 wiki 页面与补丁号（当前 7.42）。

已核对的核心数值（节选）：

| 主题 | 数值 |
|---|---|
| 肉山复活窗 | 8:00–11:00 / 7:00–10:00 / 6:00–9:00 / 5:00–8:00，下限 5:00 |
| 不朽之守护 | 拾取后 5 分钟失效；每次必掉 |
| 强化符 / 赏金符 | 6:00 首刷，之后每 2:00 / 每 4:00，基础 40 金 |
| 野怪刷新 | 1:00 首刷，之后每整分钟；堆叠收益 -20%，堆叠者得 30% |
| 补刀 / 反补 | 小兵 50%、英雄 25%、塔 10%；反补小兵对方仅得 50% 经验 |
| 兵线 | 0:00 起每 30s；旗手 2:00、攻城 5:00；每 7:30 升级（上限 30 次） |
| 击杀金钱 | 125 + 等级×8 + 连杀赏金 + 首杀 135 |
| 死亡损失 | 净值 / 40（只扣不可靠金钱） |
| 买活 | ⌊200 + 净值/13⌋，冷却 480s，下次复活 +25s |
| 复活时间 | 12s（1 级）→ 100s（25 级） |
| 视野 | 英雄 1800/800，小兵 750，上限 4000 |
| 攻速 / 移速 | 总攻速 20–700，移速 100–550 |
| 塔防（7.42） | 建筑 7s、小兵 3s；2 点能量、6 分钟充能、使用间隔 7s，拆建筑不再重置 |
| 背门保护 | 减伤 75%、每 0.1s 自愈 18 |
| 天赋 | 8 个，10/15/20/25 四级各二选一，不占技能点、不可重置 |
| 中立装备（7.42） | 四级制：0:00/15:00/30:00/50:00 解锁，65:00 疯狂石无上限；花费 5/10/10/14；每级 4 组×3 件、开局定死、每级 4 个选项；**不再由野怪掉落** |
| 观察者守卫 | 0 金、库存 2/4、补货 135s、视野 1600、持续 360s、赏金 +4 金/分 |
| 哨兵守卫 | 50 金（卖 25）、库存 3/8、补货 70s、真视 1050、持续 420s |
| 守卫拆除 | 英雄 2 下、非英雄 10 下；两守卫放置范围均 500 |
| 痛苦魔方（7.42） | 15:00 首现；护盾 4000；反伤 15%+5%/次（上限 30%）；每死掉「大战号角」，第 2 次起掉魔晶 |
| 拉野 / 封野 | 堆叠窗口 XX:53–XX:55；兵线每 30s 一波，拉线窗口约 +15s；刷新框内有任何单位即不刷新 |

不含 `values` 的条目是纯逻辑规则（判断依据而非具体数字），补丁换代后只需重跑 `scripts/build_base_data.py` 与重核数值条款。

## 数据来源与核对原则

定位与机制类知识属稳定常识；权威数值取自公开常量库，可重复刷新：

- **dotaconstants**（公开的英雄/技能/道具常量库，由 Valve 官方本地化数据构建）：`hero_base.json`、`ability_base.json`、`item_base.json`
- OpenDota API：动态统计（胜率、出场率）；`patch_stats.json` 用 `/api/heroStats` 最近 7 天滚动窗口，补当前版本公开胜率/强度分档（7.42a/7.42 混合，非纯补丁）
- Builds Forge 7.42a Tier List：仅用于档位阈值与方向交叉核对，不作为数值主源

```bash
python3 scripts/build_base_data.py    # 重建基础数据层（需访问公开常量库）
python3 scripts/fetch_data.py         # 回填动态统计
python3 scripts/build_patch_stats.py  # 重建当前版本公开胜率/强度分档（OpenDota heroStats）
```

版本更新后重新运行即可刷新；基础数据不带任何统计口径，纯为「这个技能/道具本身是什么」。

## GitHub 托管与在线读取

仓库：https://github.com/pokksh90/dota2-knowledge-base （Public）

**raw 基址（地址固定，内容更新不改地址）**：

```
https://raw.githubusercontent.com/pokksh90/dota2-knowledge-base/main
```

- `.../main/index.json`
- `.../main/data/heroes.json`、`data/items.json`、`data/matchups.json`
- `.../main/data/rules.json`、`data/inference.json`、`data/tactics.json`
- `.../main/data/hero_base.json`、`data/ability_base.json`、`data/item_base.json`

**更新流程**：

```bash
git add -A && git commit -m "更新说明"
GITHUB_TOKEN=ghp_xxx bash scripts/push_to_github.sh   # 或直接 git push origin main
```

`scripts/push_to_github.sh` 也支持从零建仓并推送：`GITHUB_TOKEN=ghp_xxx GITHUB_USER=你的用户名 bash scripts/push_to_github.sh`。

**加载策略（务必缓存）**：启动时 `fetch` raw → 本地缓存 → 运行期间只读缓存（零网络依赖）→ 按更新周期或版本变化刷新 → 刷新失败回落缓存。

> 请使用上面的 raw 地址作为数据源；带签名、短期过期的临时下载链接不适合长期引用。

## 版本与状态

见 `index.json` 的 `meta` 与各条目的 `source` 标记。当前为持续增量完善的框架版：结构完整、稳定知识已填，数值字段留待核对；完善进度见 `backlog.json`。
