#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成项目导航页。

两个来源完全隔离，各自只列、只链各自平台的项目：

  NAV_SOURCE=github（默认）
      数据来自 GitHub API：账号下所有启用了 Pages 的仓库（排除用户站点仓库本身）
      链接 = https://<owner>.github.io/<repo>/

  NAV_SOURCE=cloudflare
      数据来自 Cloudflare Pages API：账号下所有 Pages 项目（排除导航页自身项目 hubiqi）
      链接 = https://<项目域名>/
      需要环境变量 CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID

用法：NAV_SOURCE=cloudflare python3 build_nav.py 输出路径
"""
import json, os, sys, urllib.request, urllib.error, datetime

GH_API = 'https://api.github.com'
OWNER = os.environ.get('NAV_OWNER') or 'hubiqi'
ROOT_REPO = OWNER + '.github.io'
SOURCE = (os.environ.get('NAV_SOURCE') or 'github').strip().lower()

CF_API = 'https://api.cloudflare.com/client/v4'
CF_ACCOUNT = (os.environ.get('CLOUDFLARE_ACCOUNT_ID') or '').strip()
CF_TOKEN = (os.environ.get('CLOUDFLARE_API_TOKEN') or '').strip()

# 导航页自身的 CF 项目名（不出现在列表里）
CF_SELF = 'hubiqi'

# CF 项目没有描述字段，这里手工补；键是 CF 项目名
CF_DESCS = {
    'rider-dashboard': '骑手超时绩效看板',
}

SOURCE_LABEL = {'github': 'GitHub Pages', 'cloudflare': 'Cloudflare Pages'}
SOURCE_HOME = {'github': 'https://%s.github.io/' % OWNER, 'cloudflare': 'https://%s.pages.dev/' % OWNER}
SOURCE_FOOT = {
    'github': '本页由 GitHub Actions 每天自动生成，新增 Pages 项目后入口会自动出现',
    'cloudflare': '本页由 GitHub Actions 每天自动生成并部署，新增 Cloudflare Pages 项目后入口会自动出现',
}


def get_json(url, headers, err_tag):
    req = urllib.request.Request(url)
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.stderr.write('%s -> HTTP %s\n' % (err_tag, e.code))
        return None
    except Exception as e:
        sys.stderr.write('%s -> %s\n' % (err_tag, e))
        return None


def parse_dt(s):
    if not s:
        return None
    t = s.replace('Z', '+00:00')
    if '.' in t:  # 截断到秒，避免 %f 位数问题
        head, rest = t.split('.', 1)
        off = ''
        for i, ch in enumerate(rest):
            if ch in '+-':
                off = rest[i:]
                break
        t = head + off
    try:
        dt = datetime.datetime.fromisoformat(t)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def human(dt):
    if not dt:
        return ''
    days = (datetime.datetime.now(datetime.timezone.utc) - dt).days
    if days <= 0:
        return '今天更新'
    if days == 1:
        return '昨天更新'
    if days < 30:
        return '%d 天前更新' % days
    return dt.strftime('%Y-%m-%d') + ' 更新'


# ---------------------------------------------------------------- GitHub

def list_github():
    out, page = [], 1
    while page <= 10:
        repos = get_json(
            '%s/users/%s/repos?per_page=100&page=%d&sort=pushed&direction=desc' % (GH_API, OWNER, page),
            {'Accept': 'application/vnd.github+json',
             'User-Agent': 'nav-builder',
             'Authorization': 'Bearer ' + (os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
                                           or os.environ.get('KEY') or '')},
            'GitHub /users/%s/repos p%d' % (OWNER, page))
        if not repos:
            break
        for r in repos:
            if r['name'] == ROOT_REPO or r.get('archived') or r.get('fork'):
                continue
            if not r.get('has_pages'):
                continue
            out.append({
                'name': r['name'],
                'desc': (r.get('description') or '').strip() or '暂无描述',
                'pill': '/%s/' % r['name'],
                'url': 'https://%s.github.io/%s/' % (OWNER, r['name']),
                'meta': human(parse_dt(r.get('pushed_at'))),
            })
        if len(repos) < 100:
            break
        page += 1
    return out


# ------------------------------------------------------------ Cloudflare

def list_cloudflare():
    if not (CF_ACCOUNT and CF_TOKEN):
        sys.stderr.write('缺少 CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN\n')
        return []
    d = get_json('%s/accounts/%s/pages/projects' % (CF_API, CF_ACCOUNT),
                 {'Authorization': 'Bearer ' + CF_TOKEN, 'User-Agent': 'nav-builder'},
                 'CF pages/projects')
    if not d or not d.get('success'):
        if d:
            for e in d.get('errors') or []:
                sys.stderr.write('CF error %s: %s\n' % (e.get('code'), e.get('message')))
        return []
    out = []
    for p in d.get('result') or []:
        name = p.get('name') or ''
        if name == CF_SELF:
            continue
        dom = (p.get('domains') or ['%s.pages.dev' % name])[0]
        ld = p.get('latest_deployment') or {}
        out.append({
            'name': name,
            'desc': CF_DESCS.get(name) or ('托管于 Cloudflare Pages · %s' % dom),
            'pill': dom,
            'url': 'https://%s/' % dom,
            'meta': human(parse_dt(ld.get('created_on'))),
        })
    return out


# ------------------------------------------------------------------ 页面

PALETTE = [
    ('#1d4ed8', '#3b82f6'), ('#7c3aed', '#a855f7'), ('#0e7490', '#06b6d4'),
    ('#b45309', '#f59e0b'), ('#be123c', '#f43f5e'), ('#15803d', '#22c55e'),
]


def esc(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;'))


def build_html(projects):
    cards = []
    for i, p in enumerate(projects):
        c1, c2 = PALETTE[i % len(PALETTE)]
        cards.append(
            '    <a class="card" href="%(url)s">\n'
            '      <div class="thumb" style="background:linear-gradient(135deg,%(c1)s,%(c2)s)">%(ini)s</div>\n'
            '      <div class="body">\n'
            '        <div class="name">%(name)s</div>\n'
            '        <div class="desc">%(desc)s</div>\n'
            '        <div class="meta"><span class="pill">%(pill)s</span><span class="time">%(meta)s</span></div>\n'
            '      </div>\n'
            '    </a>' % {
                'url': esc(p['url']), 'c1': c1, 'c2': c2,
                'ini': esc(p['name'][0].upper() if p['name'] else '?'),
                'name': esc(p['name']), 'desc': esc(p['desc']),
                'pill': esc(p['pill']), 'meta': esc(p['meta'])})

    if not cards:
        cards.append('    <div class="empty">这个平台上还没有已发布的项目。</div>')

    now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)
    host = SOURCE_HOME.get(SOURCE, SOURCE_HOME['github']).split('//')[-1].rstrip('/')
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
.pill{font-size:11px;color:#1d4ed8;background:#eef4ff;border-radius:6px;padding:2px 7px;
  max-width:100%%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
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
  <p>%(owner)s 的静态站点 · 托管于 %(label)s</p>
  <span class="count">共 %(n)d 个项目</span>
</div>
<div class="wrap">
  <div class="grid">
%(cards)s
  </div>
</div>
<div class="ft">
  %(foot)s<br>
  入口地址：%(host)s<br>
  最后更新：%(stamp)s
</div>
</body>
</html>
""" % {'owner': OWNER, 'n': len(projects), 'cards': '\n'.join(cards),
       'label': SOURCE_LABEL.get(SOURCE, 'GitHub Pages'),
       'foot': SOURCE_FOOT.get(SOURCE, SOURCE_FOOT['github']),
       'host': host, 'stamp': now.strftime('%Y-%m-%d %H:%M')}


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else 'index.html'
    projects = list_cloudflare() if SOURCE == 'cloudflare' else list_github()
    html = build_html(projects)
    old = ''
    if os.path.exists(out_path):
        old = open(out_path, encoding='utf-8').read()
    changed = old != html
    if changed:
        open(out_path, 'w', encoding='utf-8').write(html)
    print('来源: %s' % SOURCE)
    print('项目数: %d -> %s' % (len(projects), ', '.join(p['name'] for p in projects) or '(无)'))
    for p in projects:
        print('   %-22s %s' % (p['name'], p['url']))
    print('写入 %s（%s）' % (out_path, '有变化' if changed else '无变化'))


if __name__ == '__main__':
    main()
