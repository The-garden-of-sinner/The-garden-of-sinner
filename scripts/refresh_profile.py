#!/usr/bin/env python3
"""每日刷新 GitHub Profile README。

做三件事：
1. 用 GitHub API 抓三个仓库的真实 star 数，回写 README 里的 `⭐ N`
2. 从 ghchart 拉最新 52 周贡献数据，重画 assets/heatmap.svg
3. 任何外部请求失败都不破坏现有文件（保留旧值/旧图）

只用标准库，方便在 GitHub Actions 里直接跑。
"""
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

OWNER = 'The-garden-of-sinner'
REPOS = ['MDAP', 'token-trace', 'SuperV-cliphist']
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN = os.environ.get('GITHUB_TOKEN', '')

UA = {'User-Agent': 'profile-refresh'}


def http_get(url, timeout=30, extra_headers=None):
    headers = dict(UA)
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ---------- 1. star 数 ----------

def fetch_stars(repo):
    """返回 star 数，失败返回 None。"""
    url = 'https://api.github.com/repos/%s/%s' % (OWNER, repo)
    headers = {'Accept': 'application/vnd.github+json'}
    if TOKEN:
        headers['Authorization'] = 'Bearer ' + TOKEN
    try:
        data = json.loads(http_get(url, extra_headers=headers))
        if 'stargazers_count' not in data:
            print('  ! %s 返回缺少 stargazers_count' % repo)
            return None
        return int(data['stargazers_count'])
    except Exception as e:
        print('  ! stars 拉取失败 %s: %s' % (repo, e))
        return None


def update_readme_stars(path, stars):
    """按仓库名定位并替换 <sub>⭐ N</sub> 里的数字。"""
    if not os.path.exists(path):
        return False
    s = open(path, encoding='utf-8').read()
    orig = s
    for repo, n in stars.items():
        if n is None:
            continue
        # 定位该仓库标题链接之后紧跟的 ⭐ 数字
        pat = re.compile(
            r'(<a href="https://github\.com/%s/%s"><b>[^<]*</b></a>[^<>]*</td>'
            r'<td align="right"[^>]*><sub>)\u2b50 \d+(</sub>)' % (re.escape(OWNER), re.escape(repo)))
        s2, cnt = pat.subn(lambda m: m.group(1) + '\u2b50 %d' % n + m.group(2), s)
        if cnt:
            s = s2
        else:
            print('  ! %s 里没找到 %s 的 star 位置' % (path, repo))
    if s != orig:
        open(path, 'w', encoding='utf-8').write(s)
        return True
    return False


# ---------- 2. 贡献热力图 ----------

def fetch_contribution():
    """从 ghchart 拉 52 周贡献 SVG，返回 [(score, date, col, row), ...]。"""
    url = 'https://ghchart.rshah.org/38BDF8/%s' % OWNER
    raw = http_get(url, timeout=40).decode('utf-8', errors='replace')
    rects = re.findall(
        r'<rect[^>]*data-score="(\d+)"[^>]*data-date="([\d-]+)"[^>]*x="(\d+)"[^>]*y="(\d+)"', raw)
    if len(rects) < 100:
        raise RuntimeError('贡献数据异常，rect 数 = %d' % len(rects))
    return [(int(sc), dt, int(x), int(y)) for sc, dt, x, y in rects]


MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
          'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']


def build_heatmap(rects):
    """生成等宽立方体热力图 SVG（与 gen_v9 同款：莫兰迪米灰、斜率 0、rise 动画）。"""
    cols = sorted(set(r[2] for r in rects))
    rows = sorted(set(r[3] for r in rects))   # 从数据推导行坐标，不硬编码 20/12
    cidx = {x: i for i, x in enumerate(cols)}
    ridx = {y: i for i, y in enumerate(rows)}
    NC, NR = len(cols), len(rows)

    # 月份标签：每个「年-月」的首列标注一次。
    # 52 周窗口跨年会出现两个同名月（如去年 11 月、今年 11 月），两者都保留：
    # 同一个月名的重复出现是跨年的正常表现，按年月去重即可，不能按月份名去重。
    month_at = []
    seen = set()
    for score, date, x, y in rects:
        ym = date[:7]
        if ym in seen:
            continue
        seen.add(ym)
        label = MONTHS[int(date[5:7]) - 1]
        month_at.append((label, cidx[x]))

    AX, AY = 17.0, 0.0
    BX, BY = 0.0, 13.0
    OX, OY = 70.0, 40.0

    def proj(ci, ri):
        return (OX + ci * AX + ri * BX, OY + ci * AY + ri * BY)

    pts = [proj(ci, ri) for ci in range(NC + 1) for ri in range(NR + 1)]
    minx = min(p[0] for p in pts); maxx = max(p[0] for p in pts)
    miny = min(p[1] for p in pts); maxy = max(p[1] for p in pts)
    CW = int(maxx - minx + 70); CH = int(maxy - miny + 95)
    SHX = 35 - minx; SHY = 28 - miny

    def P(ci, ri):
        x, y = proj(ci, ri)
        return (x + SHX, y + SHY)

    CH_H = 8.0
    PALETTE = [
        ('#DAD5C8', '#CBC5B6', '#BFB9AA', '#B8B2A2', '#cfc9bc'),
        ('#AFC2BC', '#9BB0AA', '#889D98', '#8fa8a2', '#c7d6d1'),
        ('#8FACAB', '#7A9998', '#688684', '#7a9c9a', '#b3cbc8'),
        ('#6E9898', '#5A8282', '#486F70', '#5c8785', '#9cbfbc'),
        ('#4F7E80', '#3D686A', '#305557', '#40736f', '#8ab4b1'),
    ]

    out = []
    out.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
               'viewBox="0 0 %d %d" fill="none">' % (CW, CH, CW, CH))
    out.append('''<style>
  .axis{stroke:#8A9A96;stroke-width:1.1;stroke-dasharray:1500;animation:draw 1600ms ease-out both}
  @keyframes draw{from{stroke-dashoffset:1500}to{stroke-dashoffset:0}}
  .grid{stroke:#CFC9BC;stroke-width:0.6;opacity:0;animation:fade 800ms ease-out both}
  .mlbl{fill:#6E6A60;font:10px ui-monospace,Menlo,Consolas,monospace;opacity:0;animation:fade 800ms ease-out both}
  @keyframes fade{to{opacity:1}}
  .cube{opacity:0;animation:rise 1700ms ease-out var(--d) infinite}
  @keyframes rise{0%,3%{opacity:0}12%,84%{opacity:1}97%,100%{opacity:0}}
  .glow{opacity:0;animation:sheen 1700ms ease-out var(--d) infinite}
  @keyframes sheen{0%,5%{opacity:0}14%{opacity:.45}36%,100%{opacity:0}}
</style>''')
    out.append('<rect width="100%" height="100%" fill="#EAE7DE" rx="10"/>')

    def corners(ci, ri):
        return P(ci, ri), P(ci + 1, ri), P(ci + 1, ri + 1), P(ci, ri + 1)

    for ci in range(NC):
        for ri in range(NR):
            A, B, C, D = corners(ci, ri)
            pts_s = ' '.join('%.1f,%.1f' % (x, y) for x, y in (A, B, C, D))
            out.append('<polygon class="grid" points="%s" style="animation-delay:%dms"/>'
                       % (pts_s, 500 + ci * 15 + ri * 18))

    bA, bB, bC, bD = corners(0, NR)
    out.append('<line class="axis" x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>'
               % (bD[0], bD[1], bC[0], bC[1]))
    lA, lB, lC, lD = corners(0, 0)
    out.append('<line class="axis" x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>'
               % (lA[0], lA[1], lD[0], lD[1]))
    for label, mc in month_at:
        _, bB2, bC2, _ = corners(mc, NR)
        out.append('<text class="mlbl" x="%.1f" y="%.1f" text-anchor="middle" '
                   'style="animation-delay:%dms">%s</text>' % (bC2[0], bC2[1] + 16, 1200 + mc * 10, label))
    wd = ['S', 'M', 'T', 'W', 'T', 'F', 'S']
    for ri, t in enumerate(wd):
        a, _, _, d = corners(0, ri)
        out.append('<text class="mlbl" x="%.1f" y="%.1f" text-anchor="end" '
                   'style="animation-delay:%dms">%s</text>'
                   % (a[0] - 8, (a[1] + d[1]) / 2 + 3, 1000 + ri * 45, t))

    for score, date, xg, yg in rects:
        ci = cidx[xg]; ri = ridx[yg]
        A, B, C, D = corners(ci, ri)
        top, left, right, edge, glow = PALETTE[min(score, 4)]
        Cp = (C[0], C[1] + CH_H); Bp = (B[0], B[1] + CH_H); Dp = (D[0], D[1] + CH_H)
        right_face = '%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f' % (
            B[0], B[1], C[0], C[1], Cp[0], Cp[1], Bp[0], Bp[1])
        left_face = '%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f' % (
            D[0], D[1], C[0], C[1], Cp[0], Cp[1], Dp[0], Dp[1])
        top_face = '%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f' % (
            A[0], A[1], B[0], B[1], C[0], C[1], D[0], D[1])
        d = 1250 + ci * 58 + ri * 8
        if score > 0:
            out.append('<g class="cube" style="--d:%dms"><polygon points="%s" fill="%s"/>'
                       '<polygon points="%s" fill="%s"/><polygon points="%s" fill="%s"/>'
                       '<polygon points="%s" fill="%s" class="glow" style="--d:%dms"/></g>'
                       % (d, left_face, left, right_face, right, top_face, top,
                          top_face, glow, d))
        else:
            out.append('<g class="cube" style="--d:%dms"><polygon points="%s" fill="#CDC7B9"/>'
                       '<polygon points="%s" fill="#C2BCAD"/>'
                       '<polygon points="%s" fill="%s" stroke="%s" stroke-width="0.6"/></g>'
                       % (d, left_face, right_face, top_face, top, edge))
    out.append('</svg>')
    return '\n'.join(out)


def main():
    print('== 刷新 star 数 ==')
    stars = {}
    star_fail = 0
    for repo in REPOS:
        n = fetch_stars(repo)
        stars[repo] = n
        if n is None:
            star_fail += 1
        print('  %-18s %s' % (repo, n))

    changed = False
    # 主 README 为同页双语（两处卡片），README.zh-CN.md 保留独立中文版
    for fn in ['README.md', 'README.zh-CN.md']:
        p = os.path.join(ROOT, fn)
        if update_readme_stars(p, stars):
            print('  已更新 %s' % fn)
            changed = True

    print('== 刷新贡献热力图 ==')
    heat_ok = False
    try:
        rects = fetch_contribution()
        svg = build_heatmap(rects)
        ET.fromstring(svg.encode('utf-8'))   # 先校验合法性，非法则不动旧文件
        heat = os.path.join(ROOT, 'assets', 'heatmap.svg')
        old = open(heat, encoding='utf-8').read() if os.path.exists(heat) else ''
        if svg != old:
            open(heat, 'w', encoding='utf-8').write(svg)
            print('  heatmap.svg 已更新（%d 字节, %d 格）' % (len(svg), len(rects)))
            changed = True
        else:
            print('  heatmap.svg 无变化')
        heat_ok = True
    except Exception as e:
        print('  ! 热力图更新失败，保留旧图: %s' % e)

    print('CHANGED=%s' % ('1' if changed else '0'))

    # star 全部拉取失败且热力图也失败 => 整体失败，让 Action 标红
    if star_fail == len(REPOS) and not heat_ok:
        print('!! 所有数据源均失败')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
