#!/usr/bin/env python3
"""抓取英雄对位胜率（公开聚合统计），生成 data/matchup_stats.json。

数据源：OpenDota 公开 API
  GET https://api.opendota.com/api/heroes/{hero_id}/matchups
  返回 [{hero_id(对手), games_played, wins}, ...]

口径：
  raw win_rate = wins / games_played（该英雄 vs 指定对手的胜率）
  baseline     = 该英雄在全部对位样本上的总胜率（sum(wins)/sum(games_played)）
  delta        = raw - baseline（相对自身基线的强弱差，正=该对位更有利）

不含任何私密凭据；仅公开聚合数据，不涉及对手个人资料。
"""
import json, os, sys, time, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'matchup_stats.json')
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
BASE = 'https://api.opendota.com/api/heroes/%d/matchups'


def get(url, retry=2):
    for i in range(retry + 1):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'dota2-kb/1.0'})
            with OPENER.open(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if i == retry:
                raise
            time.sleep(2 + i * 3)


def main():
    heroes = json.load(open(os.path.join(ROOT, 'data', 'heroes.json'), encoding='utf-8'))['heroes']
    id2slug = {}
    for h in heroes:
        sid = (h.get('base_stats') or {}).get('id')
        if sid:
            id2slug[int(sid)] = h['id']

    out = {}
    for n, (sid, slug) in enumerate(sorted(id2slug.items()), 1):
        rows = get(BASE % sid)
        games = sum(r['games_played'] for r in rows)
        wins = sum(r['wins'] for r in rows)
        baseline = round(wins / games, 4) if games else None
        vs = []
        for r in rows:
            g, w = r['games_played'], r['wins']
            if g <= 0:
                continue
            vs.append([r['hero_id'], g, round(w / g, 4)])
        vs.sort(key=lambda x: -x[1])
        out[str(sid)] = {'slug': slug, 'games': games, 'baseline': baseline, 'vs': vs}
        print('%3d/%d hero %d %s games=%d' % (n, len(id2slug), sid, slug, games), file=sys.stderr)
        time.sleep(0.4)

    doc = build_validation(out, id2slug)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    print(json.dumps(doc['validation'], ensure_ascii=False, indent=1))
    print('size_kb', round(os.path.getsize(OUT) / 1024))


def build_validation(out, id2slug):
    """把人工克制条目与统计符号对齐；按样本门槛分别统计。"""
    slug2id = {v: k for k, v in id2slug.items()}
    m = json.load(open(os.path.join(ROOT, 'data', 'matchups.json'), encoding='utf-8'))['matchups']
    res = {}
    for min_games in (30, 50):
        checked, agree = 0, 0
        supported, weak, contradicted = [], [], []
        for x in m:
            if x['relation'] == 'synergy':
                continue
            aid, bid = slug2id.get(x['hero_id']), slug2id.get(x['target_id'])
            if not aid or not bid:
                continue
            row = next((r for r in out[str(aid)]['vs'] if r[0] == bid), None)
            if not row or row[1] < min_games:
                continue
            checked += 1
            n, wr = row[1], row[2]
            p0 = out[str(aid)]['baseline']
            delta = wr - p0
            expect_pos = x['relation'] == 'counter'
            ok = (delta > 0) == expect_pos
            agree += 1 if ok else 0
            # 二项 z 值：该对位胜率相对自身基线是否显著偏离（小样本下仅作弱证据）
            denom = (n * p0 * (1 - p0)) ** 0.5
            z = (delta * n) / denom if denom else 0.0
            item = {'hero': x['hero_id'], 'vs': x['target_id'], 'relation': x['relation'],
                    'games': n, 'win_rate': wr, 'baseline': p0,
                    'delta': round(delta, 4), 'z': round(z, 2)}
            if ok and z >= 1.5:
                supported.append(item)
            elif (not ok) and z <= -1.5:
                contradicted.append(item)
            else:
                weak.append(item)
        res[min_games] = {'checked': checked, 'sign_agree': agree,
                          'sign_agree_rate': round(agree / checked, 3) if checked else None,
                          'supported': len(supported), 'weak': len(weak),
                          'contradicted': len(contradicted),
                          'contradicted_list': sorted(contradicted, key=lambda i: i['z'])[:15],
                          'supported_sample': supported[:10]}

    doc = {
        'meta': {
            'title': '英雄对位胜率（公开聚合统计）',
            'description': '供教练端校验克制结论的外部统计层：每个英雄对各对手的样本量与胜率，以及与自身基线的差值。',
            'source': 'OpenDota 公开 API（api.opendota.com/api/heroes/{id}/matchups），公开比赛聚合统计，非对手个人资料',
            'fetched_at': time.strftime('%Y-%m-%d %H:%M'),
            'method': 'raw=wins/games_played；baseline=该英雄全部对位样本总胜率；delta=raw-baseline（正=该对位优于自身平均）',
            'caveats': [
                '样本量普遍偏小（常见 50~150 局），符号噪音大，delta 只能作为弱证据，不能单独推翻机制结论',
                '全分段公开比赛聚合，非顶级局；分段时间窗与具体补丁版本未逐条核实，patch 标 pending',
                'Stratz GraphQL（api.stratz.com/graphql）曾尝试接入，但共享出口触发「每 15 分钟 2 个 IP」限流且字段名与当前 schema 不符，本轮改用 OpenDota 同语义数据',
            ],
            'patch': 'pending',
            'count': len(out),
        },
        'validation': {
            'curated_matchups': len(m),
            'thresholds': res,
            'note': '只对 counter / countered_by 做符号一致性检查（synergy 与胜率差无关）；样本低于门槛的条目不计入。冲突不代表人工结论错，只说明统计层面不支持，需复核机制前提。',
        },
        'heroes': out,
    }
    return doc


if __name__ == '__main__':
    main()
