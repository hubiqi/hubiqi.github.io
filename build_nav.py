#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 <user>.github.io 根路径的项目导航页。

规则：账号下任何「启用了 Pages 的项目仓库」都自动出现在导航里，
站点地址 = https://<user>.github.io/<repo>/。仓库描述作为卡片副标题。

用法：python3 build_nav.py [输出路径，默认 index.html]
环境变量：GITHUB_TOKEN / GH_TOKEN / KEY 任一即可（Actions 里用 secrets.GITHUB_TOKEN）
"""
import json, os, sys, urllib.request, urllib.error, datetime

API = 'https://api.github.com'
TOKEN = (os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
         or os.environ.get('KEY') or '').strip()
OWNER = os.environ.get('NAV_OWNER') or 'hubiqi'
ROOT_REPO = OWNER + '.github.io'


def api(path):
    req = urllib.request.Request(API + path)
    req.add_header('Accept', 'application/vnd.github+json')
    req.add_header('User-Agent', 'nav-builder')
    if TOKEN:
        req.add_header('Authorization', 'Bearer ' + TOKEN)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.stderr.write('API %s -> %s\n' % (path, e.code))
        return None


def list_projects():
    """列出所有启用了 Pages 的项目仓库（排除用户站点仓库本身）。"""
    out, page = [], 1
    while page <= 10:
        repos = api('/users/%s/repos?per_page=100&page=%d&sort=pushed&direction=desc' % (OWNER, page))
        if not repos:
            break
        for r in repos:
            if r['name'] == ROOT_REPO:
                continue
            if r.get('archived') or r.get('fork'):
                continue
            if not r.get('has_pages'):
                continue
            out.append(r)
        if len(repos) < 100:
            break
        page += 1
    return out


def human_time(iso):
    if not iso:
        return ''
    try:
        dt = datetime.datetime.strptime(iso, '%Y-%m-%dT%H:%M:%SZ').replace(
            tzinfo=datetime.timezone.utc)
    except ValueError:
        return ''
    now = datetime.datetime.now(datetime.timezone.utc)
    days = (now - dt).days
    if days <= 0:
        return '今天更新'
    if days == 1:
        return '昨天更新'
    if days < 30:
        return '%d 天前更新' % days
    return dt.strftime('%Y-%m-%d') + ' 更新'


PALETTE = [
    ('#1d4ed8', '#3b82f6'), ('#7c3aed', '#a855f7'), ('#0e7490', '#06b6d4'),
    ('#b45309', '#f59e0b'), ('#be123c', '#f43f5e'), ('#15803d', '#22c55e'),
]


def build_html(projects):
    cards = []
    for i, p in enumerate(projects):
        name = p['name']
        desc = (p.get('description') or '').strip() or '暂无描述'
        c1, c2 = PALETTE[i % len(PALETTE)]
        initial = name[0].upper() if name else '?'
        url = 'https://%s.github.io/%s/' % (OWNER, name)
        meta = human_time(p.get('pushed_at'))
        cards.append(
            '    <a class="card" href="%s">\n'
            '      <div class="thumb" style="background:linear-gradient(135deg,%s,%s)">%s</div>\n'
            '      <div class="body">\n'
            '        <div class="name">%s</div>\n'
            '        <div class="desc">%s</div>\n'
            '        <div class="meta"><span class="pill">/%s/</span><span class="time">%s</span></div>\n'
            '      </div>\n'
            '    </a>' % (url, c1, c2, esc(initial), esc(name), esc(desc), esc(name), esc(meta)))

    if not cards:
        cards.append('    <div class="empty">还没有已发布的项目。在任意仓库里开启 Pages 后，'
                     '这里会自动出现入口。</div>')

    now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)
    stamp = now.strftime('%Y-%m-%d %H:%M')

    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>项目导航 · %(owner)s</title>
<style>
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;background:#f4f6fa;color:#101828;
  font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",Roboto,sans-serif}
.hd{background:linear-gradient(120deg,#1e3a8a 0%%,#2563eb 45%%,#7c3aed 100%%);
  color:#fff;padding:34px 20px 30px;position:relative;overflow:hidden}
.hd:after{content:"";position:absolute;right:-50px;top:-60px;width:200px;height:200px;
  border-radius:50%%;background:rgba(255,255,255,.10)}
.hd h1{margin:0;font-size:23px;letter-spacing:.4px;position:relative}
.hd p{margin:9px 0 0;font-size:13px;opacity:.88;position:relative}
.hd .count{display:inline-block;margin-top:14px;background:rgba(255,255,255,.18);
  border-radius:20px;padding:4px 13px;font-size:12px;position:relative}
.wrap{max-width:1000px;margin:0 auto;padding:18px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(268px,1fr));gap:14px}
.card{display:flex;gap:13px;align-items:flex-start;background:#fff;border-radius:15px;
  padding:15px;text-decoration:none;color:inherit;box-shadow:0 1px 3px rgba(16,24,40,.07);
  border:1px solid #eef1f6;transition:.16s}
.card:active,.card:hover{transform:translateY(-2px);box-shadow:0 7px 18px rgba(16,24,40,.11);
  border-color:#dbe4f5}
.thumb{flex:0 0 auto;width:46px;height:46px;border-radius:12px;color:#fff;font-size:19px;
  font-weight:700;display:flex;align-items:center;justify-content:center}
.body{min-width:0;flex:1 1 auto}
.name{font-size:15px;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.desc{margin-top:5px;font-size:12.5px;color:#667085;line-height:1.55;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.meta{margin-top:10px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.pill{font-size:11px;color:#1d4ed8;background:#eef4ff;border-radius:6px;padding:2px 7px}
.time{font-size:11px;color:#98a2b3}
.empty{grid-column:1/-1;text-align:center;color:#98a2b3;font-size:13px;padding:44px 20px;
  background:#fff;border-radius:15px;border:1px dashed #d0d5dd}
.ft{text-align:center;color:#98a2b3;font-size:11.5px;padding:22px 16px 30px;line-height:1.7}
@media(max-width:420px){.wrap{padding:13px}.grid{grid-template-columns:1fr;gap:11px}
  .hd{padding:26px 16px 24px}.hd h1{font-size:20px}}
</style>
</head>
<body>
<div class="hd">
  <h1>项目导航</h1>
  <p>%(owner)s 的静态站点集合</p>
  <span class="count">共 %(n)d 个项目</span>
</div>
<div class="wrap">
  <div class="grid">
%(cards)s
  </div>
</div>
<div class="ft">
  本页由 GitHub Actions 自动生成，新增子路径项目后会自动出现入口<br>
  最后更新：%(stamp)s
</div>
</body>
</html>
""" % {'owner': OWNER, 'n': len(projects), 'cards': '\n'.join(cards), 'stamp': stamp}


def esc(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;'))


if __name__ == '__main__':
    out_path = sys.argv[1] if len(sys.argv) > 1 else 'index.html'
    projects = list_projects()
    html = build_html(projects)
    old = ''
    if os.path.exists(out_path):
        old = open(out_path, encoding='utf-8').read()
    changed = old != html
    if changed:
        open(out_path, 'w', encoding='utf-8').write(html)
    print('项目数: %d -> %s' % (len(projects), ', '.join(p['name'] for p in projects) or '(无)'))
    print('写入 %s（%s）' % (out_path, '有变化' if changed else '无变化'))
    sys.exit(0)
