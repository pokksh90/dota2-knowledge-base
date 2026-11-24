# Dota2 专业知识库（LLM 可消费 · 三层可回溯）

一份面向大语言模型（LLM）应用的**结构化刀塔（Dota 2）领域知识库**。全部内容为公开通用的游戏知识与可复现的逻辑推导，不包含任何个人数据、玩家隐私或非公开信息。

设计取向只有一条：**不堆结论，先给规则，再由规则推出结论**。每条结论都能讲清「为什么」。

---

## 三层架构

```
① 公理层  rules.json      底层机制与公式：伤害计算、护甲/魔抗、攻速、经济与经验、地图资源、先手博弈
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
│   ├── rules.json            # ① 公理层：35 条底层机制
│   ├── inference.json        # ② 定理层：26 条可回溯推导
│   ├── heroes.json           # ③ 英雄与定位（含 aliases 绰号）
│   ├── items.json            # ③ 装备与出装
│   ├── matchups.json         # ③ 克制与搭配
│   ├── tactics.json          # ③ 战术与节奏
│   ├── hero_base.json        # 基础数据层：英雄属性 + 技能索引
│   ├── ability_base.json     # 基础数据层：759 条技能明细
│   └── item_base.json        # 基础数据层：303 件道具价格与属性
└── scripts/
    ├── fetch_data.py         # 从公开 API 拉取数值并回填
    ├── build_base_data.py     # 从公开常量库重建基础数据层（可重复运行）
    └── push_to_github.sh     # 一键建仓/推送
```

## 板块说明

| 文件 | 内容 | 典型用途 |
|------|------|---------|
| `rules.json` | 伤害公式、护甲/魔抗、攻速、经济、经验、地图、先手博弈 | 解释类问答的底层依据 |
| `inference.json` | 由公理推导的洞察（前提→推导→结论→应用） | 「为什么该这样打」的推理链 |
| `heroes.json` | 英雄定位 1-5、主/副定位、玩法要点 | 选人、阵容分析 |
| `items.json` | 装备分类、用途、分位置核心出装与情境选择 | 出装建议 |
| `matchups.json` | 英雄 counter / synergy，每条带机制依据 `basis` | 对位与 BP 分析 |
| `tactics.json` | 分线职责、关键时间点、地图目标、团战决策 | 战术节奏建议 |
| `hero_base.json` | 英雄基础属性（三围/血量/护甲/移速/视野）+ 技能 key 索引 | 数值查询、对线强度估算 |
| `ability_base.json` | 每个技能的伤害类型、蓝耗、冷却、是否穿透 BKB、关键数值 | 「这招能不能被 BKB/驱散挡」 |
| `item_base.json` | 道具价格、合成件、属性、主动效果 | 出装成本与属性对比 |

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

## 数据来源与核对原则

定位与机制类知识属稳定常识；权威数值取自公开常量库，可重复刷新：

- **dotaconstants**（公开的英雄/技能/道具常量库，由 Valve 官方本地化数据构建）：`hero_base.json`、`ability_base.json`、`item_base.json`
- OpenDota API / Stratz GraphQL：动态统计（胜率、出场率）需要时另行核对

```bash
python3 scripts/build_base_data.py    # 重建基础数据层（需访问公开常量库）
python3 scripts/fetch_data.py         # 回填动态统计
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
