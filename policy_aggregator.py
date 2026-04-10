#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政府政策聚合 RSS 生成器 - 完整版
聚合工信部、科技部、数据局、发改委、网信办等多个政策来源
"""

import requests
from datetime import datetime
import json
import os
import re
import time
import random
from urllib.parse import urljoin, urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============ 反爬配置 ============
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
]


def create_session():
    """创建带重试机制的 session"""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


def get_headers(url, source_url=None):
    """根据 URL 生成合适的请求头"""
    if source_url:
        referer = source_url
    else:
        referer = 'https://www.baidu.com/s?wd='

    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': referer,
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }


def smart_delay(base_delay=2.0):
    """智能延时"""
    delay = base_delay + random.uniform(0.5, 2.0)
    time.sleep(delay)


# ============ 数据源配置 ============
SOURCES = {
    # 工信部各司局
    'miit_txs': {
        'name': '工信部信息通信发展司',
        'type': 'html_list',
        'url': 'https://www.miit.gov.cn/jgsj/txs/wjfb/index.html',
        'list_selectors': ['.lmy_main_l3 li', '.lmy_main_tj li', 'ul li'],
        'title_selector': 'a',
        'date_selector': 'span',
        'link_attr': 'href',
        'encoding': 'utf-8',
    },
    'miit_kjs': {
        'name': '工信部科技司',
        'type': 'html_list',
        'url': 'https://www.miit.gov.cn/jgsj/kjs/wjfb/index.html',
        'list_selectors': ['.lmy_main_l3 li', '.lmy_main_tj li', 'ul li'],
        'title_selector': 'a',
        'date_selector': 'span',
        'link_attr': 'href',
        'encoding': 'utf-8',
    },
    'miit_gxjss': {
        'name': '工信部高新技术司',
        'type': 'html_list',
        'url': 'https://www.miit.gov.cn/gyhxxhb/jgsj/gxjss/wjfb/index.html',
        'list_selectors': ['.lmy_main_l3 li', '.lmy_main_tj li', 'ul li'],
        'title_selector': 'a',
        'date_selector': 'span',
        'link_attr': 'href',
        'encoding': 'utf-8',
    },
    'miit_waj': {
        'name': '工信部网络安全管理局',
        'type': 'html_list',
        'url': 'https://www.miit.gov.cn/jgsj/waj/wjfb/index.html',
        'list_selectors': ['.lmy_main_l3 li', '.lmy_main_tj li', 'ul li'],
        'title_selector': 'a',
        'date_selector': 'span',
        'link_attr': 'href',
        'encoding': 'utf-8',
    },
    'miit_xgj': {
        'name': '工信部信息通信管理局',
        'type': 'html_list',
        'url': 'https://www.miit.gov.cn/jgsj/xgj/wjfb/index.html',
        'list_selectors': ['.lmy_main_l3 li', '.lmy_main_tj li', 'ul li'],
        'title_selector': 'a',
        'date_selector': 'span',
        'link_attr': 'href',
        'encoding': 'utf-8',
    },
    'miit_policy': {
        'name': '工信部政策文件',
        'type': 'html_list',
        'url': 'https://www.miit.gov.cn/zwgk/index.html',
        'list_selectors': ['.lmy_main_l3 li', '.lmy_main_tj li', 'ul li'],
        'title_selector': 'a',
        'date_selector': 'span',
        'link_attr': 'href',
        'encoding': 'utf-8',
    },
    'miit_sme': {
        'name': '工信部中小企业促进中心',
        'type': 'html_list',
        'url': 'https://www.chinasme.org.cn/html/mcms/daohang/zhengcehuibian/index.html',
        'list_selectors': ['.list li', '.news-list li', '.content-list li', 'ul li'],
        'title_selector': 'a',
        'date_selector': 'span, .date',
        'link_attr': 'href',
        'encoding': 'utf-8',
    },
    # 科技部
    'most': {
        'name': '科技部科技政策',
        'type': 'html_list',
        'url': 'https://www.most.gov.cn/satp/',
        'list_selectors': ['.list_con li', '.news_list li', '.content_list li', '.list-box li', 'ul li'],
        'title_selector': 'a',
        'date_selector': 'span',
        'link_attr': 'href',
        'encoding': 'utf-8',
    },
    # 数据局
    'nda': {
        'name': '国家数据局',
        'type': 'html_list',
        'url': 'https://www.nda.gov.cn/sjj/zwgk/tzgg/list/index_pc_1.html',
        'list_selectors': ['.u-list li', '.list_con li', '.news-list li', 'ul li'],
        'title_selector': 'a',
        'date_selector': 'span',
        'link_attr': 'href',
        'encoding': 'utf-8',
    },
    # 发改委
    'ndrc': {
        'name': '国家发改委',
        'type': 'html_list',
        'url': 'https://www.ndrc.gov.cn/xxgk/',
        'list_selectors': ['.u-list li', '.list_con li', '.news_list li', 'ul li'],
        'title_selector': 'a',
        'date_selector': 'span',
        'link_attr': 'href',
        'encoding': 'utf-8',
    },
    # 网信办
    'cac': {
        'name': '国家网信办',
        'type': 'html_list',
        'url': 'https://www.cac.gov.cn/wxzw/A0937index_1.htm',
        'list_selectors': ['.news-normal li', '.list_box li', '.news_list li', 'ul li'],
        'title_selector': 'a',
        'date_selector': 'span',
        'link_attr': 'href',
        'encoding': 'utf-8',
    },
    # 人工智能学会
    'caai': {
        'name': '中国人工智能学会',
        'type': 'html_list',
        'url': 'https://www.caai.cn/site/term/14.html',
        'list_selectors': ['.news_list li', '.list_con li', '.content-list li', 'ul li'],
        'title_selector': 'a',
        'date_selector': 'span, .date',
        'link_attr': 'href',
        'encoding': 'utf-8',
    },
}


def fetch_url(url, session=None, encoding=None, source_url=None):
    """智能 URL 抓取"""
    if session is None:
        session = create_session()

    headers = get_headers(url, source_url)

    try:
        response = session.get(url, headers=headers, timeout=30, allow_redirects=True)
        response.raise_for_status()
        if encoding:
            response.encoding = encoding
        else:
            response.encoding = response.apparent_encoding
        return response.text
    except Exception as e:
        print(f"[ERROR] 抓取失败 {url}: {e}")
        return None


def extract_article_summary(html, max_length=300):
    """提取文章正文摘要，过滤导航等内容"""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        # 移除脚本、样式、导航、页头页脚等无关元素
        for elem in soup(["script", "style", "nav", "header", "footer",
                          ".breadcrumb", ".bread", ".nav", ".menu",
                          ".location", ".position", ".path"]):
            elem.decompose()

        # 优先选择正文区域
        content_selectors = [
            '.TRS_Editor',
            '.Custom_UnionStyle',
            '.article-content',
            '.content-detail',
            '#article-content',
            '.main-content',
            '.detail-content',
            '.text-content',
            '#content',
            '.content',
        ]

        content_elem = None
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                text = content_elem.get_text(separator=' ', strip=True)
                if len(text) > 100:
                    break
                content_elem = None

        if not content_elem:
            content_elem = soup.find('article') or soup.find('main')

        if content_elem:
            content_text = content_elem.get_text(separator=' ', strip=True)
        else:
            for elem in soup.find_all(['aside', '.sidebar', '.related', '.recommend']):
                elem.decompose()
            body = soup.find('body')
            content_text = body.get_text(separator=' ', strip=True) if body else ''

        # 清理文本
        content_text = re.sub(r'\s+', ' ', content_text).strip()

        # 过滤常见的导航/面包屑文本
        nav_patterns = [
            r'设为首页\s*加入收藏\s*',
            r'手机版\s*繁体\s*搜索\s*',
            r'首\s*页\s*时政要闻\s*网信政务\s*',
            r'当前位置[：:]\s*首页\s*[>]\s*正文\s*',
            r'首页\s*正文\s*',
            r'来源[：:]\s*.*?\[打印\]\s*\[纠错\]\s*',
            r'\[打印\]\s*\[纠错\]\s*',
        ]
        for pattern in nav_patterns:
            content_text = re.sub(pattern, '', content_text)

        content_text = re.sub(r'\s+', ' ', content_text).strip()

        if len(content_text) > max_length:
            return content_text[:max_length] + '...'
        return content_text

    except Exception as e:
        return ''


def parse_html_list(source_key, source_config, session):
    """HTML 列表解析"""
    items = []
    url = source_config['url']

    try:
        from bs4 import BeautifulSoup

        smart_delay(2.0)
        html = fetch_url(url, session, source_config.get('encoding'), source_url=url)
        if not html:
            return items

        soup = BeautifulSoup(html, 'html.parser')

        list_items = []
        for selector in source_config['list_selectors']:
            list_items = soup.select(selector)
            if list_items:
                print(f"[INFO] {source_config['name']}: 使用选择器 {selector}")
                break

        if not list_items:
            print(f"[WARN] {source_config['name']}: 未找到列表项")
            return items

        for li in list_items[:8]:  # 限制数量
            try:
                a_tag = li.select_one(source_config['title_selector'])
                if not a_tag:
                    continue

                title = a_tag.get_text(strip=True)
                link = a_tag.get(source_config['link_attr'], '')

                if link and not link.startswith('http'):
                    link = urljoin(url, link)

                date_text = ''
                date_elem = li.select_one(source_config['date_selector'])
                if date_elem:
                    date_text = date_elem.get_text(strip=True)

                if title and link and len(title) > 5:
                    item = {
                        'title': title,
                        'link': link,
                        'pub_date': parse_date(date_text) or datetime.now().isoformat(),
                        'source': source_config['name'],
                    }

                    # 获取正文摘要
                    print(f"[INFO] 正在获取正文: {title[:30]}...")
                    smart_delay(1.5)
                    article_html = fetch_url(link, session, source_url=url)
                    if article_html:
                        summary = extract_article_summary(article_html)
                        if summary:
                            item['description'] = f"📄 摘要：{summary}"

                    items.append(item)

            except Exception as e:
                continue

    except Exception as e:
        print(f"[ERROR] HTML 解析失败 {url}: {e}")

    return items


def parse_date(date_str):
    """解析各种日期格式"""
    if not date_str:
        return None

    formats = ['%Y-%m-%d', '%Y/%m/%d', '%Y年%m月%d日']
    date_str = date_str.strip()

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).isoformat()
        except:
            continue

    match = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', date_str)
    if match:
        try:
            return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()
        except:
            pass

    return None


def generate_rss(items):
    """生成 RSS XML"""
    items_xml = ''

    for item in items:
        pub_date = item.get('pub_date', datetime.now().isoformat())
        try:
            dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
            pub_date_str = dt.strftime('%a, %d %b %Y %H:%M:%S +0800')
        except:
            pub_date_str = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0800')

        guid = hash(f"{item['title']}{item['link']}") & 0xFFFFFFFF
        desc = item.get('description', f"来源：{item['source']}")

        items_xml += f"""
        <item>
            <title><![CDATA[{item['title']}]]></title>
            <link>{item['link']}</link>
            <guid isPermaLink="false">{guid}</guid>
            <pubDate>{pub_date_str}</pubDate>
            <description><![CDATA[{desc}]]></description>
            <category>{item['source']}</category>
        </item>
        """

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>政府政策聚合</title>
        <link>https://cherylchenxue-star.github.io/gov-rss/</link>
        <description>聚合工信部、科技部、数据局、发改委等多个政策来源</description>
        <language>zh-CN</language>
        <lastBuildDate>{datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0800')}</lastBuildDate>
        {items_xml}
    </channel>
</rss>"""


def generate_html(items):
    """生成 HTML 预览页"""
    source_stats = {}
    for item in items:
        src = item['source']
        source_stats[src] = source_stats.get(src, 0) + 1

    html_items = ''
    for item in items[:50]:
        pub_time = item['pub_date'][:10] if len(item['pub_date']) > 10 else item['pub_date']
        summary = item.get('description', '')
        summary_html = f'<div class="summary">{summary[:150]}...</div>' if summary else ''

        html_items += f"""
        <div class="item">
            <a href="{item['link']}" target="_blank" class="title">{item['title']}</a>
            {summary_html}
            <div class="meta"><span class="source">{item['source']}</span> · {pub_time}</div>
        </div>
        """

    stats_html = ''
    for src, count in sorted(source_stats.items(), key=lambda x: -x[1]):
        stats_html += f'<div class="stat"><div class="stat-number">{count}</div><div class="stat-label">{src}</div></div>'

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>政府政策聚合 RSS</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; max-width: 900px; margin: 40px auto; padding: 20px; background: #f5f7fa; }}
        h1 {{ color: #1a1a1a; text-align: center; }}
        .info {{ background: white; padding: 25px; border-radius: 12px; margin: 20px 0; box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-align: center; }}
        .rss-link {{ background: #1a73e8; color: white; padding: 12px 24px; border-radius: 6px; display: inline-block; margin: 10px; text-decoration: none; font-weight: bold; }}
        .stats {{ display: flex; justify-content: center; gap: 20px; margin: 20px 0; flex-wrap: wrap; }}
        .stat {{ text-align: center; padding: 10px; }}
        .stat-number {{ font-size: 20px; font-weight: bold; color: #1a73e8; }}
        .stat-label {{ color: #666; font-size: 12px; max-width: 80px; }}
        .item {{ background: white; padding: 16px 20px; border-radius: 8px; margin: 12px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
        .title {{ font-size: 16px; color: #1a1a1a; text-decoration: none; display: block; margin-bottom: 8px; font-weight: 500; }}
        .title:hover {{ color: #1a73e8; }}
        .summary {{ color: #666; font-size: 14px; margin: 8px 0; line-height: 1.6; }}
        .meta {{ color: #888; font-size: 13px; }}
        .source {{ background: #e8f0fe; color: #1a73e8; padding: 2px 8px; border-radius: 4px; font-size: 12px; }}
        .footer {{ text-align: center; color: #999; margin-top: 40px; }}
    </style>
</head>
<body>
    <h1>📋 政府政策聚合 RSS</h1>
    <div class="info">
        <p>聚合工信部、科技部、数据局、发改委等多个政策来源</p>
        <a href="rss.xml" class="rss-link">📡 RSS 订阅</a>
        <p style="color: #888; font-size: 14px;">当前共 {len(items)} 条政策 · 最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    <h2>最新政策</h2>
    {html_items}
    <div class="footer">数据来源: 工信部、科技部、国家数据局、发改委等</div>
</body>
</html>"""


def main():
    print(f"[{datetime.now()}] 开始抓取政策数据...")
    print("=" * 60)

    all_items = []
    session = create_session()

    for source_key, source_config in SOURCES.items():
        try:
            print(f"[INFO] 正在抓取: {source_config['name']}")
            items = parse_html_list(source_key, source_config, session)
            all_items.extend(items)
            print(f"[OK] {source_config['name']}: 获取 {len(items)} 条")
        except Exception as e:
            print(f"[ERROR] {source_key}: {e}")

        time.sleep(random.uniform(3, 5))

    print("=" * 60)

    # 去重
    seen_links = set()
    unique_items = []
    for item in all_items:
        if item['link'] not in seen_links:
            seen_links.add(item['link'])
            unique_items.append(item)

    unique_items.sort(key=lambda x: x.get('pub_date', ''), reverse=True)
    print(f"[INFO] 去重后共 {len(unique_items)} 条")

    # 保存
    os.makedirs('public', exist_ok=True)

    with open('public/rss.xml', 'w', encoding='utf-8') as f:
        f.write(generate_rss(unique_items))

    with open('public/index.html', 'w', encoding='utf-8') as f:
        f.write(generate_html(unique_items))

    print(f"[OK] 已生成: public/rss.xml ({len(unique_items)} 条)")


if __name__ == '__main__':
    main()
