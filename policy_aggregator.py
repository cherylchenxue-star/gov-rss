#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政府政策聚合 RSS 生成器
聚合工信部、科技部、数据局、发改委等多个政策来源
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
    'miit_txs': {
        'name': '工信部信息通信发展司',
        'type': 'html_list',
        'url': 'https://www.miit.gov.cn/jgsj/txs/wjfb/index.html',
        'base_url': 'https://www.miit.gov.cn',
        'list_selectors': ['.lmy_main_l3 li', '.lmy_main_tj li', '.clist_con li', '.gy_list li'],
        'title_selector': 'a',
        'date_selector': 'span',
        'link_attr': 'href',
        'encoding': 'utf-8',
    },
    'nda': {
        'name': '国家数据局',
        'type': 'html_list',
        'url': 'https://www.nda.gov.cn/sjj/zwgk/tzgg/list/index_pc_1.html',
        'base_url': 'https://www.nda.gov.cn',
        'list_selectors': ['.u-list li', '.list_con li', '.news-list li'],
        'title_selector': 'a',
        'date_selector': 'span',
        'link_attr': 'href',
        'encoding': 'utf-8',
    },
    'ndrc': {
        'name': '国家发改委',
        'type': 'html_list',
        'url': 'https://www.ndrc.gov.cn/xxgk/',
        'base_url': 'https://www.ndrc.gov.cn',
        'list_selectors': ['.u-list li', '.list_con li', '.news_list li'],
        'title_selector': 'a',
        'date_selector': 'span',
        'link_attr': 'href',
        'encoding': 'utf-8',
    },
    'cac': {
        'name': '国家网信办',
        'type': 'html_list',
        'url': 'https://www.cac.gov.cn/wxzw/A0937index_1.htm',
        'base_url': 'https://www.cac.gov.cn',
        'list_selectors': ['.news-normal li', '.list_box li', '.news_list li'],
        'title_selector': 'a',
        'date_selector': '.times',   # cac.gov.cn 用 <div class="times">
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
    """提取文章正文摘要"""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        # 移除所有非正文元素（包括用 div 实现的导航）
        NOISE_TAGS = ["script", "style", "nav", "header", "footer", "noscript"]
        NOISE_CLASSES = re.compile(
            r'nav|menu|header|footer|sidebar|breadcrumb|crumb|'
            r'search|tool|share|关注|收藏|繁体|手机版|设为首页|加入收藏',
            re.I
        )
        for tag in soup.find_all(True):
            # 注释节点、ProcessingInstruction 等没有 attrs，跳过
            if not hasattr(tag, 'attrs') or tag.attrs is None:
                continue
            cls = ' '.join(tag.get('class', []))
            tid = tag.get('id', '')
            if tag.name in NOISE_TAGS or NOISE_CLASSES.search(cls) or NOISE_CLASSES.search(tid):
                tag.decompose()

        # 政府网站常见正文容器，按优先级排列
        content_selectors = [
            '#BodyLabel',                           # cac.gov.cn
            '.TRS_Editor', '.Custom_UnionStyle',    # 通用政府 CMS
            '.content-detail', '.article-content', '.article_con',
            '.article_content', '.news_content', '.newscontent',
            '.zwcontent', '.pages_content', '.text_con',
            '.main-content', '#content', '#article', '#main-content',
            '.content',
        ]

        content_text = ''
        for selector in content_selectors:
            elem = soup.select_one(selector)
            if elem:
                t = elem.get_text(separator=' ', strip=True)
                if len(t) > 100:
                    content_text = t
                    break

        # fallback：找文字密度最高的 div（子标签少、文字多）
        if not content_text or len(content_text) < 50:
            best_elem, best_score = None, 0
            for div in soup.find_all(['div', 'td']):
                text = div.get_text(separator=' ', strip=True)
                child_tags = len(div.find_all(True))
                if child_tags == 0:
                    continue
                score = len(text) / (child_tags + 1)
                if score > best_score and len(text) > 80:
                    best_score = score
                    best_elem = div
            if best_elem:
                content_text = best_elem.get_text(separator=' ', strip=True)

        content_text = re.sub(r'\s+', ' ', content_text).strip()

        if len(content_text) > max_length:
            return content_text[:max_length] + '...'
        return content_text

    except Exception:
        return ''


def extract_date_from_article(html):
    """从文章详情页提取真实发布时间，优先级：meta标签 > 正文日期元素 > 全文正则扫描"""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        # 1. 标准 meta 标签
        meta_selectors = [
            ('meta[property="article:published_time"]', 'content'),
            ('meta[name="pubdate"]', 'content'),
            ('meta[name="publishdate"]', 'content'),
            ('meta[name="date"]', 'content'),
            ('meta[itemprop="datePublished"]', 'content'),
        ]
        for selector, attr in meta_selectors:
            tag = soup.select_one(selector)
            if tag and tag.get(attr):
                result = parse_date(tag[attr])
                if result:
                    return result

        # 2. 政府网站常见日期容器
        date_selectors = [
            '.date', '.time', '.pubdate', '.pub-date', '.publish-date',
            '.article-date', '.news-date', '.info-date',
            '[class*="date"]', '[class*="time"]',
            '.sub', '.source', '.origin',
        ]
        for selector in date_selectors:
            elem = soup.select_one(selector)
            if elem:
                result = parse_date(elem.get_text(strip=True))
                if result:
                    return result

        # 3. 全文正则扫描（取最早出现的完整日期）
        text = soup.get_text()
        matches = re.findall(r'(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})', text)
        for m in matches:
            result = parse_date(m)
            if result:
                return result

    except Exception:
        pass
    return None


def extract_date_from_list_item(li, date_selector):
    """从列表项中提取日期，尝试多个 span 直到找到可解析的日期"""
    # 1. 先用配置的选择器
    elem = li.select_one(date_selector)
    if elem:
        result = parse_date(elem.get_text(strip=True))
        if result:
            return result

    # 2. 遍历所有 span，找第一个能解析为日期的
    for span in li.find_all('span'):
        result = parse_date(span.get_text(strip=True))
        if result:
            return result

    # 3. 正则扫描整个 li 文本
    text = li.get_text()
    match = re.search(r'(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})', text)
    if match:
        result = parse_date(match.group(1))
        if result:
            return result

    return None


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

        for li in list_items[:10]:
            try:
                a_tag = li.select_one(source_config['title_selector'])
                if not a_tag:
                    continue

                title = a_tag.get_text(strip=True)
                link = a_tag.get(source_config['link_attr'], '')

                if link and not link.startswith('http'):
                    link = urljoin(source_config['url'], link)

                # 先从列表项提取日期
                pub_date = extract_date_from_list_item(li, source_config['date_selector'])

                if title and link and len(title) > 5:
                    item = {
                        'title': title,
                        'link': link,
                        'source': source_config['name'],
                    }

                    # 获取正文（摘要 + 日期兜底）
                    print(f"[INFO] 正在获取正文: {title[:30]}...")
                    smart_delay(1.5)
                    article_html = fetch_url(link, session, source_url=url)
                    if article_html:
                        summary = extract_article_summary(article_html)
                        if summary:
                            item['description'] = f"📄 摘要：{summary}"

                        # 列表页未能提取日期时，从详情页提取
                        if not pub_date:
                            pub_date = extract_date_from_article(article_html)
                            if pub_date:
                                print(f"[INFO] 从详情页提取到日期: {pub_date[:10]}")

                    if pub_date:
                        item['pub_date'] = pub_date
                    else:
                        # 真正兜底：标记为未知，避免用爬取时间误导
                        print(f"[WARN] 无法提取日期，跳过: {title[:30]}")
                        item['pub_date'] = '1970-01-01T00:00:00'

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
            dt = datetime.strptime(date_str, fmt)
            return dt.isoformat()
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
