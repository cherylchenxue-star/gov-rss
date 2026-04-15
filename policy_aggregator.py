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


# ============ 智能标签词库 ============
INDUSTRY_KEYWORDS = {
    "人工智能": ["人工智能", "大模型", "算力", "算法", "智能计算", "智算中心", "深度学习", "机器学习"],
    "数字经济": ["数字经济", "数字化转型", "数字中国", "数据要素", "大数据", "云计算", "区块链"],
    "网络安全": ["网络安全", "数据安全", "信息安全", "关键信息基础设施", "安全审查", "密码技术"],
    "通信技术": ["5G", "6G", "工业互联网", "物联网", "车联网", "卫星互联网", "通信"],
    "集成电路": ["集成电路", "芯片", "半导体", "晶圆", "EDA", "光刻"],
    "新能源汽车": ["新能源汽车", "智能网联汽车", "电动汽车", "动力电池", "氢能", "充电设施"],
    "企业资质": ["专精特新", "小巨人", "瞪羚", "独角兽", "中小企业", "高新技术企业"],
    "资金支持": ["专项资金", "补贴", "退税", "产业扶持", "资金", "奖补", "财政支持"],
    "人才项目": ["人才引进", "高层次人才", "揭榜挂帅", "研发投入", "创新团队", "人才计划"],
    "绿色低碳": ["碳达峰", "碳中和", "绿色低碳", "节能减排", "循环经济", "清洁生产"],
    "质量标准": ["质量", "标准", "认证", "检测", "计量", "质量管理"],
    "对外开放": ["对外开放", "外商投资", "进出口", "一带一路", "自贸区", "国际合作"],
}


def extract_industry_tags(text: str) -> list:
    """基于关键词匹配提取行业/分类标签"""
    if not text:
        return []
    tags = []
    for category, keywords in INDUSTRY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                tags.append(category)
                break
    return tags


# ============ 数据源配置 ============
MIIT_LIST_SELECTORS = ['.page-content li', '.lmy_main_l3 li', '.lmy_main_tj li', '.clist_con li', '.gy_list li', 'ul.list li', '.news_list li']
MIIT_COMMON = {
    'type': 'html_list',
    'base_url': 'https://www.miit.gov.cn',
    'list_selectors': MIIT_LIST_SELECTORS,
    'title_selector': 'a',
    'date_selector': 'span',
    'link_attr': 'href',
    'encoding': 'utf-8',
    'build_unit': True,
    'max_items': 10,
}

SOURCES = {
    'miit_txs': {**MIIT_COMMON,
        'name': '工信部信息通信发展司',
        'url': 'https://www.miit.gov.cn/jgsj/txs/wjfb/index.html',
    },
    'miit_kjs': {**MIIT_COMMON,
        'name': '工信部科技司',
        'url': 'https://www.miit.gov.cn/jgsj/kjs/wjfb/index.html',
    },
    'miit_gxjs': {**MIIT_COMMON,
        'name': '工信部高新技术司',
        'url': 'https://www.miit.gov.cn/gyhxxhb/jgsj/gxjss/wjfb/index.html',
    },
    'miit_waj': {**MIIT_COMMON,
        'name': '工信部网络安全管理局',
        'url': 'https://www.miit.gov.cn/jgsj/waj/wjfb/index.html',
    },
    'miit_zwgk': {
        'name': '工信部政策文件',
        'type': 'search_api',
        'url': 'https://www.miit.gov.cn/search/zcwjk.html',
        'base_url': 'https://www.miit.gov.cn',
        'api_url': 'https://www.miit.gov.cn/search-front-server/api/search/info',
        'api_params': {
            'websiteid': '110000000000000',
            'scope': 'basic',
            'q': '',
            'pg': '10',
            'cateid': '196',
            'pos': 'title_text,infocontent,titlepy',
            'dateField': 'deploytime',
            'sortFields': '[{"name":"deploytime","type":"desc"}]',
            'p': '1',
        },
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


def fetch_build_unit_html(url, session):
    """对工信部 build/unit 接口：先请求原始页面提取参数，再请求接口返回列表 HTML"""
    page_html = fetch_url(url, session, encoding='utf-8', source_url=url)
    if not page_html:
        return None

    # 提取 pageId
    page_id_match = re.search(r'pageId[\'"]?\s*[:=]\s*[\'"]([a-f0-9-]+)[\'"]', page_html)
    if not page_id_match:
        print(f"[WARN] 未提取到 pageId: {url}")
        return None
    page_id = page_id_match.group(1)

    # 提取 queryData 中的参数
    query_match = re.search(r'queryData=[\'"](\{.*?\})[\'"]', page_html)
    if not query_match:
        print(f"[WARN] 未提取到 queryData: {url}")
        return None

    query_raw = query_match.group(1).replace("'", '"')
    try:
        query_data = json.loads(query_raw)
    except json.JSONDecodeError as e:
        print(f"[WARN] queryData JSON 解析失败: {e}")
        return None

    api_url = 'https://www.miit.gov.cn/api-gateway/jpaas-publish-server/front/page/build/unit'
    params = {
        'parseType': query_data.get('parseType', 'buildstatic'),
        'webId': query_data.get('webId'),
        'tplSetId': query_data.get('tplSetId'),
        'pageType': query_data.get('pageType', 'column'),
        'tagId': query_data.get('tagId'),
        'pageId': page_id,
    }
    # 移除 None 值
    params = {k: v for k, v in params.items() if v is not None}

    try:
        resp = session.get(api_url, params=params, headers=get_headers(api_url, source_url=url), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        html = data.get('data', {}).get('html', '')
        if html:
            return html
        print(f"[WARN] build/unit 接口无 html: {url}")
    except Exception as e:
        print(f"[ERROR] build/unit 请求失败 {url}: {e}")
    return None


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

        if source_config.get('build_unit'):
            print(f"[INFO] 使用 build/unit 接口: {url}")
            html = fetch_build_unit_html(url, session)
        else:
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

        max_items = source_config.get('max_items', 10)
        list_items = list_items[:max_items]

        for li in list_items[:max_items]:
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
                        'source_id': source_key,
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

                    # 最后兜底：从 URL 路径提取日期（如 /2026-04/13/ 或 /2026/0413/）
                    if not pub_date:
                        pub_date = parse_date(link)
                        if pub_date:
                            print(f"[INFO] 从 URL 提取到日期: {pub_date[:10]}")
                        else:
                            print(f"[WARN] 无法提取日期: {title[:30]}")

                    if pub_date:
                        item['pub_date'] = pub_date

                    # 智能标签
                    summary_text = item.get('description', '').replace('📄 摘要：', '')
                    item['tags'] = extract_industry_tags(f"{title} {summary_text}")

                    items.append(item)

            except Exception as e:
                continue

    except Exception as e:
        print(f"[ERROR] HTML 解析失败 {url}: {e}")

    return items


def parse_search_api(source_key, source_config, session):
    """解析工信部搜索 API"""
    items = []
    api_url = source_config['api_url']
    params = source_config.get('api_params', {}).copy()
    base_url = source_config['base_url']

    try:
        smart_delay(1.5)
        resp = session.get(api_url, params=params, headers=get_headers(api_url, source_url=source_config['url']), timeout=30)
        resp.raise_for_status()
        data = resp.json(strict=False)

        results = data.get('data', {}).get('searchResult', {}).get('dataResults', [])
        print(f"[INFO] {source_config['name']}: API 返回 {len(results)} 条")

        for result in results[:source_config.get('max_items', 10)]:
            item_data = result.get('data', {})
            title = item_data.get('title', '')
            link = item_data.get('url', '')
            pub_time = item_data.get('deploytime', '') or item_data.get('publishtime', '')

            if not title or not link:
                continue

            if not link.startswith('http'):
                link = urljoin(base_url, link)

            pub_date = parse_date(pub_time) or parse_date(link)

            item = {
                'title': title,
                'link': link,
                'source': source_config['name'],
                'source_id': source_key,
            }
            if pub_date:
                item['pub_date'] = pub_date

            # 获取摘要
            print(f"[INFO] 正在获取正文: {title[:30]}...")
            smart_delay(1.5)
            article_html = fetch_url(link, session, source_url=source_config['url'])
            if article_html:
                summary = extract_article_summary(article_html)
                if summary:
                    item['description'] = f"📄 摘要：{summary}"
                if not pub_date:
                    pub_date = extract_date_from_article(article_html)
                    if pub_date:
                        item['pub_date'] = pub_date

            # 智能标签
            summary_text = item.get('description', '').replace('📄 摘要：', '')
            item['tags'] = extract_industry_tags(f"{title} {summary_text}")

            items.append(item)

    except Exception as e:
        print(f"[ERROR] 搜索 API 解析失败 {api_url}: {e}")

    return items


def parse_date(date_str):
    """解析各种日期格式"""
    if not date_str:
        return None

    date_str = date_str.strip()

    # 固定格式（含点号分隔，如 nda.gov.cn 的 2026.04.10）
    formats = ['%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d', '%Y年%m月%d日']
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.isoformat()
        except:
            continue

    # 通用正则：支持 - / . 三种分隔符
    match = re.search(r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})', date_str)
    if match:
        try:
            return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()
        except:
            pass

    # URL 中的紧凑格式，如 20260410
    match = re.search(r'(\d{4})(\d{2})(\d{2})', date_str)
    if match:
        try:
            dt = datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            # 合理性校验：年份在 2000-2099 之间
            if 2000 <= dt.year <= 2099:
                return dt.isoformat()
        except:
            pass

    return None


def generate_rss(items):
    """生成 RSS XML"""
    items_xml = ''
    rss_link = 'https://cherylchenxue-star.github.io/gov-rss/rss.xml'

    for item in items:
        pub_date_str = ''
        if 'pub_date' in item:
            try:
                dt = datetime.fromisoformat(item['pub_date'].replace('Z', '+00:00'))
                pub_date_str = dt.strftime('%a, %d %b %Y %H:%M:%S +0800')
            except:
                pass

        guid = hash(f"{item['title']}{item['link']}") & 0xFFFFFFFF
        summary = item.get('description', '').replace('📄 摘要：', '').strip()
        desc = f"来源: {item['source']}<br/>{summary}" if summary else f"来源: {item['source']}"
        tags = item.get('tags', [])
        tags_xml = ''.join([f'\n            <category><![CDATA[{tag}]]></category>' for tag in tags])

        pub_date_tag = f'<pubDate>{pub_date_str}</pubDate>' if pub_date_str else ''
        items_xml += f"""
        <item>
            <title><![CDATA[{item['title']}]]></title>
            <link>{item['link']}</link>
            <guid isPermaLink="false">{guid}</guid>
            {pub_date_tag}
            <description><![CDATA[{desc}]]></description>
            <source>{item['source']}</source>{tags_xml}
        </item>
        """

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
    <channel>
        <title>政府政策聚合</title>
        <link>https://cherylchenxue-star.github.io/gov-rss/</link>
        <description>聚合工信部（5个司局及政策文件）、国家数据局、国家发改委、国家网信办等多个政策来源</description>
        <language>zh-CN</language>
        <lastBuildDate>{datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0800')}</lastBuildDate>
        <atom:link href="{rss_link}" rel="self" type="application/rss+xml" />
        {items_xml}
    </channel>
</rss>"""


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
  <title>政府政策聚合 RSS</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/font-awesome@4.7.0/css/font-awesome.min.css">
  <link rel="alternate" type="application/rss+xml" title="政府政策聚合" href="{rss_link}">
  <style>
    .line-clamp-2 { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
    .line-clamp-3 { display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
    .no-scrollbar::-webkit-scrollbar { display: none; }
    .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
  </style>
</head>
<body class="bg-gray-50 min-h-screen">
  <div id="app" class="max-w-5xl mx-auto px-4 py-6 sm:py-8">
    <!-- Header -->
    <header class="mb-6">
      <h1 class="text-2xl sm:text-3xl font-bold text-slate-800 mb-2">政府政策聚合 RSS</h1>
      <p class="text-slate-600 mb-4 text-sm sm:text-base">聚合工信部、国家数据局、国家发改委、国家网信办等多个政策来源。</p>
      <div class="flex flex-wrap gap-3">
        <a id="rss-btn" href="{rss_link}" class="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition min-h-[44px]">
          <i class="fa fa-rss mr-2"></i>订阅 RSS
        </a>
        <button type="button" id="refresh-btn" class="inline-flex items-center px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition min-h-[44px]">
          <i class="fa fa-refresh mr-2" id="refresh-icon"></i>刷新数据
        </button>
        <a href="https://github.com/cherylchenxue-star/gov-rss" class="inline-flex items-center px-4 py-2 bg-slate-800 text-white rounded-lg hover:bg-slate-900 transition min-h-[44px]">
          <i class="fa fa-github mr-2"></i>GitHub 仓库
        </a>
      </div>
    </header>

    <!-- Stats Bar -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-4">
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div class="flex items-center gap-3 flex-wrap">
          <span class="text-slate-700 font-medium">共 <span id="stat-total" class="text-blue-600 font-bold">{total}</span> 条政策</span>
          <span class="text-slate-400 hidden sm:inline">|</span>
          <span class="text-sm text-slate-500">更新时间：<span id="stat-updated">{updated_at}</span></span>
        </div>
        <div id="source-badges" class="flex flex-wrap gap-2">
          <!-- badges injected by JS -->
        </div>
      </div>
    </div>

    <!-- Filter Bar -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-4 sticky top-0 z-30">
      <div class="flex flex-col gap-3">
        <div class="relative flex-1">
          <i class="fa fa-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"></i>
          <input id="search-input" type="text" placeholder="搜索标题、摘要、来源..." class="w-full pl-10 pr-9 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-base">
          <button id="search-clear" class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 hidden" aria-label="清除搜索">
            <i class="fa fa-times-circle"></i>
          </button>
        </div>
        <div class="flex flex-wrap gap-2 pb-1 sm:pb-0">
          <div class="relative">
            <button type="button" id="source-dropdown-btn" class="px-3 py-2 border border-gray-200 rounded-lg hover:bg-gray-50 active:bg-gray-100 flex items-center gap-2 min-h-[44px] whitespace-nowrap cursor-pointer select-none">
              来源<i class="fa fa-chevron-down text-xs text-gray-400 pointer-events-none"></i>
              <span id="source-badge" class="ml-1 bg-blue-600 text-white text-xs px-1.5 rounded-full hidden pointer-events-none">0</span>
            </button>
            <div id="source-dropdown-panel" class="hidden absolute left-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg p-2 min-w-[200px] z-40">
              <div class="max-h-64 overflow-y-auto" id="source-options">
                <!-- checkboxes injected by JS -->
              </div>
              <div class="border-t border-gray-100 mt-2 pt-2 flex gap-2">
                <button type="button" id="source-select-all" class="flex-1 px-2 py-1 text-xs text-blue-600 hover:bg-blue-50 rounded cursor-pointer">全选</button>
                <button type="button" id="source-clear" class="flex-1 px-2 py-1 text-xs text-gray-600 hover:bg-gray-100 rounded cursor-pointer">清空</button>
              </div>
            </div>
          </div>

          <div class="relative">
            <button type="button" id="tag-dropdown-btn" class="px-3 py-2 border border-gray-200 rounded-lg hover:bg-gray-50 active:bg-gray-100 flex items-center gap-2 min-h-[44px] whitespace-nowrap cursor-pointer select-none">
              标签<i class="fa fa-chevron-down text-xs text-gray-400 pointer-events-none"></i>
              <span id="tag-badge" class="ml-1 bg-blue-600 text-white text-xs px-1.5 rounded-full hidden pointer-events-none">0</span>
            </button>
            <div id="tag-dropdown-panel" class="hidden absolute left-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg p-2 min-w-[200px] z-40">
              <div class="space-y-1 max-h-64 overflow-y-auto" id="tag-options">
                <!-- tag buttons injected by JS -->
              </div>
            </div>
          </div>

          <div class="relative">
            <button type="button" id="date-dropdown-btn" class="px-3 py-2 border border-gray-200 rounded-lg hover:bg-gray-50 active:bg-gray-100 flex items-center gap-2 min-h-[44px] whitespace-nowrap cursor-pointer select-none">
              日期<i class="fa fa-chevron-down text-xs text-gray-400 pointer-events-none"></i>
            </button>
            <div id="date-dropdown-panel" class="hidden absolute left-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg p-2 min-w-[200px] z-40">
              <div class="space-y-1">
                <button type="button" data-value="all" class="date-option w-full text-left px-3 py-2 rounded hover:bg-gray-100 text-sm cursor-pointer">全部时间</button>
                <button type="button" data-value="7d" class="date-option w-full text-left px-3 py-2 rounded hover:bg-gray-100 text-sm cursor-pointer">近7天</button>
                <button type="button" data-value="30d" class="date-option w-full text-left px-3 py-2 rounded hover:bg-gray-100 text-sm cursor-pointer">近30天</button>
                <button type="button" data-value="90d" class="date-option w-full text-left px-3 py-2 rounded hover:bg-gray-100 text-sm cursor-pointer">近90天</button>
                <div class="border-t border-gray-100 pt-2 mt-1">
                  <div class="px-3 py-1 text-xs text-gray-500">自定义</div>
                  <div class="flex gap-2 px-3 py-1">
                    <input id="custom-start" type="date" class="border border-gray-200 rounded px-2 py-1 text-sm w-full">
                    <span class="text-gray-400 self-center">-</span>
                    <input id="custom-end" type="date" class="border border-gray-200 rounded px-2 py-1 text-sm w-full">
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="relative">
            <button type="button" id="sort-dropdown-btn" class="px-3 py-2 border border-gray-200 rounded-lg hover:bg-gray-50 active:bg-gray-100 flex items-center gap-2 min-h-[44px] whitespace-nowrap cursor-pointer select-none">
              排序<i class="fa fa-chevron-down text-xs text-gray-400 pointer-events-none"></i>
            </button>
            <div id="sort-dropdown-panel" class="hidden absolute left-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg p-2 min-w-[140px] z-40">
              <button type="button" data-value="desc" class="sort-option w-full text-left px-3 py-2 rounded hover:bg-gray-100 text-sm bg-blue-50 text-blue-700 cursor-pointer">日期倒序</button>
              <button type="button" data-value="asc" class="sort-option w-full text-left px-3 py-2 rounded hover:bg-gray-100 text-sm cursor-pointer">日期正序</button>
            </div>
          </div>

          <button type="button" id="reset-btn" class="px-3 py-2 text-gray-600 hover:bg-gray-100 active:bg-gray-200 border border-gray-200 rounded-lg min-h-[44px] whitespace-nowrap cursor-pointer select-none">
            <i class="fa fa-refresh mr-1"></i>重置
          </button>
        </div>
      </div>

      <!-- Active Filters -->
      <div id="active-filters" class="hidden flex flex-wrap items-center gap-2 mt-3 pt-3 border-t border-gray-100">
        <span class="text-xs text-gray-500">已筛选：</span>
        <div id="active-filters-list" class="flex flex-wrap gap-2"></div>
        <button id="clear-all-filters" class="text-xs text-gray-500 hover:text-gray-700 underline ml-auto">清除全部</button>
      </div>
    </div>

    <!-- Policy List -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      <div class="px-4 sm:px-6 py-3 border-b border-gray-100 flex items-center justify-between">
        <h2 class="font-semibold text-slate-800 text-sm sm:text-base">最新政策</h2>
        <span id="result-count" class="text-sm text-slate-500"></span>
      </div>
      <ul id="policy-list" class="divide-y divide-gray-100">
        <!-- items injected by JS -->
      </ul>
      <div id="load-more-container" class="px-4 py-4 border-t border-gray-100 text-center hidden">
        <button id="load-more-btn" class="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition min-h-[44px]">加载更多</button>
      </div>
    </div>

    <!-- Empty State -->
    <div id="empty-state" class="hidden py-16 text-center">
      <div class="w-16 h-16 mx-auto mb-4 rounded-full bg-gray-100 flex items-center justify-center">
        <i class="fa fa-search text-2xl text-gray-400"></i>
      </div>
      <h3 class="text-lg font-medium text-slate-700 mb-1">未找到匹配的政策</h3>
      <p class="text-sm text-slate-500 mb-4">请尝试调整筛选条件或更换搜索关键词</p>
      <button id="empty-clear-btn" class="px-4 py-2 text-sm text-blue-600 hover:bg-blue-50 rounded-lg transition border border-blue-200">清除全部筛选</button>
    </div>

    <!-- Footer -->
    <footer class="mt-8 text-center text-sm text-slate-500">
      <p class="mb-2">数据来源：工信部信息通信发展司、工信部科技司、工信部高新技术司、工信部网络安全管理局、工信部政策文件、国家数据局、国家发改委、国家网信办</p>
      <p class="flex justify-center gap-4">
        <a href="{rss_link}" class="hover:text-blue-600">RSS 订阅</a>
        <a href="https://github.com/cherylchenxue-star/gov-rss" class="hover:text-slate-800">GitHub 仓库</a>
      </p>
    </footer>
  </div>

  <script>
    window.POLICY_DATA = {policy_data_json};
  </script>
  <script>
    (function() {
      const data = window.POLICY_DATA;

      const state = {
        filters: {
          search: '',
          sources: data.sources.map(s => s.id),
          tag: 'all',
          dateRange: 'all',
          customStart: '',
          customEnd: '',
        },
        sort: 'desc',
        pagination: {
          page: 1,
          pageSize: 20,
        },
      };

      function debounce(fn, ms) {
        let t;
        return function(...args) {
          clearTimeout(t);
          t = setTimeout(() => fn.apply(this, args), ms);
        };
      }

      function formatDateLabel(range) {
        const map = { 'all': '全部时间', '7d': '近7天', '30d': '近30天', '90d': '近90天', 'custom': '自定义' };
        return map[range] || range;
      }

      function getFilteredPolicies() {
        return data.policies.filter(p => {
          if (!state.filters.sources.includes(p.sourceId)) return false;
          if (state.filters.tag !== 'all' && !p.tags.includes(state.filters.tag)) return false;
          if (state.filters.dateRange !== 'all') {
            if (!p.date) return false;
            const policyDate = new Date(p.date + 'T00:00:00');
            const now = new Date();
            if (state.filters.dateRange === 'custom') {
              if (state.filters.customStart && policyDate < new Date(state.filters.customStart + 'T00:00:00')) return false;
              if (state.filters.customEnd && policyDate > new Date(state.filters.customEnd + 'T23:59:59')) return false;
            } else {
              const days = { '7d': 7, '30d': 30, '90d': 90 }[state.filters.dateRange];
              const cutoff = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
              cutoff.setHours(0,0,0,0);
              if (policyDate < cutoff) return false;
            }
          }
          if (state.filters.search) {
            const q = state.filters.search.toLowerCase();
            const text = (p.title + ' ' + p.source + ' ' + p.summary + ' ' + p.tags.join(' ')).toLowerCase();
            if (!text.includes(q)) return false;
          }
          return true;
        }).sort((a, b) => {
          const da = a.date ? new Date(a.date + 'T00:00:00') : new Date(0);
          const db = b.date ? new Date(b.date + 'T00:00:00') : new Date(0);
          return state.sort === 'desc' ? db - da : da - db;
        });
      }

      function renderStats() {
        const badgeContainer = document.getElementById('source-badges');
        badgeContainer.innerHTML = '';
        data.sources.forEach(s => {
          const count = data.policies.filter(p => p.sourceId === s.id).length;
          if (count > 0) {
            const badge = document.createElement('span');
            badge.className = 'inline-flex items-center px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-700 border border-gray-200';
            badge.textContent = s.name + ' ' + count;
            badgeContainer.appendChild(badge);
          }
        });
      }

      function renderSourceDropdown() {
        const container = document.getElementById('source-options');
        container.innerHTML = '';
        data.sources.forEach(s => {
          const label = document.createElement('label');
          label.className = 'flex items-center gap-2 px-3 py-2 hover:bg-gray-50 cursor-pointer rounded';
          label.innerHTML = `<input type="checkbox" value="${s.id}" class="source-checkbox w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500" ${state.filters.sources.includes(s.id) ? 'checked' : ''}> <span class="text-sm text-gray-700">${s.name}</span>`;
          const checkbox = label.querySelector('input');
          checkbox.addEventListener('change', (e) => {
            const val = e.target.value;
            if (e.target.checked) {
              if (!state.filters.sources.includes(val)) state.filters.sources.push(val);
            } else {
              state.filters.sources = state.filters.sources.filter(id => id !== val);
            }
            state.pagination.page = 1;
            renderAll();
          });
          container.appendChild(label);
        });
      }

      function renderTagDropdown() {
        const container = document.getElementById('tag-options');
        container.innerHTML = '';
        const allBtn = document.createElement('button');
        allBtn.className = 'tag-option w-full text-left px-3 py-2 rounded text-sm ' + (state.filters.tag === 'all' ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-100');
        allBtn.textContent = '全部标签';
        allBtn.dataset.value = 'all';
        container.appendChild(allBtn);
        data.allTags.forEach(tag => {
          const btn = document.createElement('button');
          btn.className = 'tag-option w-full text-left px-3 py-2 rounded text-sm ' + (state.filters.tag === tag ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-100');
          btn.textContent = tag;
          btn.dataset.value = tag;
          container.appendChild(btn);
        });
      }

      function renderActiveFilters() {
        const container = document.getElementById('active-filters');
        const list = document.getElementById('active-filters-list');
        list.innerHTML = '';
        let hasAny = false;

        if (state.filters.search) {
          hasAny = true;
          list.appendChild(createFilterTag('搜索: ' + state.filters.search, () => { state.filters.search = ''; document.getElementById('search-input').value = ''; renderAll(); }));
        }
        const isPartialSourceFilter = state.filters.sources.length > 0 && state.filters.sources.length < data.sources.length;
        if (isPartialSourceFilter) {
          hasAny = true;
          const sourceNames = state.filters.sources.map(id => {
            const s = data.sources.find(x => x.id === id);
            return s ? s.name : id;
          });
          list.appendChild(createFilterTag('来源: ' + sourceNames.join('、'), () => {
            state.filters.sources = data.sources.map(s => s.id);
            renderSourceDropdown();
            renderAll();
          }));
        }
        if (state.filters.tag !== 'all') {
          hasAny = true;
          list.appendChild(createFilterTag('标签: ' + state.filters.tag, () => { state.filters.tag = 'all'; renderTagDropdown(); renderAll(); }));
        }
        if (state.filters.dateRange !== 'all') {
          hasAny = true;
          let label = formatDateLabel(state.filters.dateRange);
          if (state.filters.dateRange === 'custom' && (state.filters.customStart || state.filters.customEnd)) {
            label += ' (' + (state.filters.customStart || '') + ' ~ ' + (state.filters.customEnd || '') + ')';
          }
          list.appendChild(createFilterTag(label, () => { state.filters.dateRange = 'all'; document.getElementById('custom-start').value = ''; document.getElementById('custom-end').value = ''; renderAll(); }));
        }

        container.classList.toggle('hidden', !hasAny);
        const sourceBadge = document.getElementById('source-badge');
        sourceBadge.textContent = state.filters.sources.length;
        sourceBadge.classList.toggle('hidden', !isPartialSourceFilter);
        const tagBadge = document.getElementById('tag-badge');
        tagBadge.textContent = state.filters.tag === 'all' ? '0' : '1';
        tagBadge.classList.toggle('hidden', state.filters.tag === 'all');
      }

      function createFilterTag(text, onRemove) {
        const span = document.createElement('span');
        span.className = 'inline-flex items-center gap-1 px-2 py-1 bg-blue-50 text-blue-700 text-xs rounded-full';
        span.innerHTML = `<span>${text}</span><button class="hover:text-blue-900 leading-none" aria-label="移除"><i class="fa fa-times"></i></button>`;
        span.querySelector('button').addEventListener('click', onRemove);
        return span;
      }

      function renderPolicyList() {
        const filtered = getFilteredPolicies();
        const sorted = filtered;
        const pageSize = state.pagination.page * state.pagination.pageSize;
        const paginated = sorted.slice(0, pageSize);
        const hasMore = sorted.length > paginated.length;

        const listEl = document.getElementById('policy-list');
        listEl.innerHTML = '';

        document.getElementById('result-count').textContent = `共 ${sorted.length} 条`;
        document.getElementById('empty-state').classList.toggle('hidden', paginated.length > 0);
        document.getElementById('load-more-container').classList.toggle('hidden', !hasMore);

        if (paginated.length === 0) return;

        paginated.forEach(item => {
          const li = document.createElement('li');
          li.className = 'px-4 sm:px-6 py-4 hover:bg-gray-50 transition';
          const summary = item.summary || '';
          const summaryHtml = summary ? `<p class="text-sm text-slate-600 line-clamp-2 sm:line-clamp-3 mt-1">${escapeHtml(summary)}</p>` : '';
          const tagsHtml = (item.tags && item.tags.length) ? `<div class="flex flex-wrap gap-1 mt-1">${item.tags.map(t => `<span class="tag-pill cursor-pointer inline-flex items-center px-2 py-0.5 rounded text-xs bg-emerald-50 text-emerald-700 border border-emerald-100 hover:bg-emerald-100 transition" data-tag="${escapeHtml(t)}">${escapeHtml(t)}</span>`).join('')}</div>` : '';
          li.innerHTML = `
            <div class="flex flex-col gap-1">
              <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-1 sm:gap-2">
                <a href="${item.link}" target="_blank" class="text-base font-medium text-slate-800 hover:text-blue-600 transition line-clamp-2">${escapeHtml(item.title)}</a>
                <span class="text-sm text-slate-400 whitespace-nowrap shrink-0">${item.date || '日期未知'}</span>
              </div>
              <div class="flex items-center gap-2 text-sm">
                <span class="inline-flex items-center px-2 py-0.5 rounded text-xs bg-blue-50 text-blue-700 border border-blue-100">${escapeHtml(item.source)}</span>
              </div>
              ${summaryHtml}
              ${tagsHtml}
            </div>
          `;
          listEl.appendChild(li);
        });
        // Bind tag click events
        listEl.querySelectorAll('.tag-pill').forEach(pill => {
          pill.addEventListener('click', () => {
            state.filters.tag = pill.dataset.tag;
            state.pagination.page = 1;
            renderTagDropdown();
            renderAll();
          });
        });
      }

      function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
      }

      function renderAll() {
        renderStats();
        renderActiveFilters();
        renderPolicyList();
      }

      function showToast(message, type = 'success') {
        let toast = document.getElementById('page-toast');
        if (!toast) {
          toast = document.createElement('div');
          toast.id = 'page-toast';
          toast.className = 'fixed top-4 left-1/2 -translate-x-1/2 px-4 py-2 rounded-lg shadow-lg text-sm font-medium z-50 transition-opacity duration-300 opacity-0';
          document.body.appendChild(toast);
        }
        toast.className = 'fixed top-4 left-1/2 -translate-x-1/2 px-4 py-2 rounded-lg shadow-lg text-sm font-medium z-50 transition-opacity duration-300 ' + (type === 'success' ? 'bg-emerald-600 text-white' : 'bg-red-600 text-white');
        toast.textContent = message;
        toast.style.opacity = '1';
        setTimeout(() => { toast.style.opacity = '0'; }, 2500);
      }

      async function refreshFromRSS() {
        const icon = document.getElementById('refresh-icon');
        icon.classList.add('fa-spin');
        try {
          const res = await fetch(data.rssLink + '?t=' + Date.now());
          if (!res.ok) throw new Error('HTTP ' + res.status);
          const xmlText = await res.text();
          const parser = new DOMParser();
          const doc = parser.parseFromString(xmlText, 'application/xml');
          const parserError = doc.querySelector('parsererror');
          if (parserError) throw new Error('XML parse error');

          const sourceNameToId = {};
          data.sources.forEach(s => sourceNameToId[s.name] = s.id);

          const items = Array.from(doc.querySelectorAll('item'));
          const policies = [];
          const allTags = new Set();

          items.forEach(item => {
            const title = item.querySelector('title')?.textContent?.trim() || '';
            const link = item.querySelector('link')?.textContent?.trim() || '';
            const pubDate = item.querySelector('pubDate')?.textContent?.trim() || '';
            const description = item.querySelector('description')?.textContent?.trim() || '';
            const sourceName = item.querySelector('source')?.textContent?.trim() || '';

            let summary = '';
            const brIdx = description.indexOf('<br/>');
            if (brIdx !== -1) {
              summary = description.slice(brIdx + 5).trim();
            } else if (description.startsWith('来源:')) {
              const lines = description.split(/[\\n\\r]+/);
              summary = lines.slice(1).join(' ').trim();
            } else {
              summary = description;
            }

            const d = new Date(pubDate);
            const dateStr = isNaN(d) ? '' : d.toISOString().slice(0, 10);

            const tags = Array.from(item.querySelectorAll('category')).map(c => c.textContent.trim()).filter(Boolean);
            tags.forEach(t => allTags.add(t));

            policies.push({
              id: link + '-' + hashCode(title),
              title,
              link,
              date: dateStr,
              sourceId: sourceNameToId[sourceName] || '',
              source: sourceName,
              summary,
              tags,
            });
          });

          data.policies = policies;
          data.allTags = Array.from(allTags).sort();
          data.meta.totalCount = policies.length;
          data.meta.updatedAt = new Date().toLocaleString('zh-CN', { hour12: false, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).split('/').join('-');

          state.filters.sources = data.sources.map(s => s.id);
          state.filters.tag = 'all';
          state.filters.dateRange = 'all';
          state.filters.search = '';
          state.pagination.page = 1;

          document.getElementById('search-input').value = '';
          document.getElementById('search-clear').classList.add('hidden');
          document.getElementById('custom-start').value = '';
          document.getElementById('custom-end').value = '';

          renderTagDropdown();
          updateDateDropdownUI();
          updateSortDropdownUI();
          renderAll();
          showToast('数据已刷新', 'success');
        } catch (e) {
          console.error(e);
          showToast('刷新失败：' + (e.message || '无法加载 RSS'), 'error');
        } finally {
          icon.classList.remove('fa-spin');
        }
      }

      function hashCode(str) {
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
          const char = str.charCodeAt(i);
          hash = ((hash << 5) - hash) + char;
          hash = hash & hash;
        }
        return hash;
      }

      function bindEvents() {
        const searchInput = document.getElementById('search-input');
        const searchClear = document.getElementById('search-clear');
        const sourceBtn = document.getElementById('source-dropdown-btn');
        const sourcePanel = document.getElementById('source-dropdown-panel');
        const tagBtn = document.getElementById('tag-dropdown-btn');
        const tagPanel = document.getElementById('tag-dropdown-panel');
        const dateBtn = document.getElementById('date-dropdown-btn');
        const datePanel = document.getElementById('date-dropdown-panel');
        const sortBtn = document.getElementById('sort-dropdown-btn');
        const sortPanel = document.getElementById('sort-dropdown-panel');

        function closeAllPanels(except) {
          if (except !== 'source') sourcePanel.classList.add('hidden');
          if (except !== 'tag') tagPanel.classList.add('hidden');
          if (except !== 'date') datePanel.classList.add('hidden');
          if (except !== 'sort') sortPanel.classList.add('hidden');
        }

        searchInput.addEventListener('input', debounce(() => {
          state.filters.search = searchInput.value.trim();
          state.pagination.page = 1;
          searchClear.classList.toggle('hidden', !state.filters.search);
          renderAll();
        }, 200));
        searchClear.addEventListener('click', () => {
          searchInput.value = '';
          state.filters.search = '';
          searchClear.classList.add('hidden');
          state.pagination.page = 1;
          renderAll();
        });

        sourceBtn.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          const willShow = sourcePanel.classList.contains('hidden');
          closeAllPanels();
          if (willShow) sourcePanel.classList.remove('hidden');
        });
        document.getElementById('source-select-all').addEventListener('click', (e) => {
          e.stopPropagation();
          state.filters.sources = data.sources.map(s => s.id);
          renderSourceDropdown();
          state.pagination.page = 1;
          renderAll();
        });
        document.getElementById('source-clear').addEventListener('click', (e) => {
          e.stopPropagation();
          state.filters.sources = [];
          renderSourceDropdown();
          state.pagination.page = 1;
          renderAll();
        });

        tagBtn.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          const willShow = tagPanel.classList.contains('hidden');
          closeAllPanels();
          if (willShow) tagPanel.classList.remove('hidden');
        });
        document.getElementById('tag-options').addEventListener('click', (e) => {
          if (e.target.classList.contains('tag-option')) {
            e.stopPropagation();
            state.filters.tag = e.target.dataset.value;
            state.pagination.page = 1;
            renderTagDropdown();
            renderAll();
          }
        });

        dateBtn.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          const willShow = datePanel.classList.contains('hidden');
          closeAllPanels();
          if (willShow) datePanel.classList.remove('hidden');
        });
        datePanel.querySelectorAll('.date-option').forEach(btn => {
          btn.addEventListener('click', (e) => {
            e.stopPropagation();
            state.filters.dateRange = btn.dataset.value;
            if (state.filters.dateRange !== 'custom') {
              document.getElementById('custom-start').value = '';
              document.getElementById('custom-end').value = '';
              state.filters.customStart = '';
              state.filters.customEnd = '';
            }
            state.pagination.page = 1;
            renderAll();
            updateDateDropdownUI();
          });
        });
        document.getElementById('custom-start').addEventListener('change', (e) => {
          state.filters.dateRange = 'custom';
          state.filters.customStart = e.target.value;
          state.pagination.page = 1;
          renderAll();
          updateDateDropdownUI();
        });
        document.getElementById('custom-end').addEventListener('change', (e) => {
          state.filters.dateRange = 'custom';
          state.filters.customEnd = e.target.value;
          state.pagination.page = 1;
          renderAll();
          updateDateDropdownUI();
        });

        sortBtn.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          const willShow = sortPanel.classList.contains('hidden');
          closeAllPanels();
          if (willShow) sortPanel.classList.remove('hidden');
        });
        sortPanel.querySelectorAll('.sort-option').forEach(btn => {
          btn.addEventListener('click', (e) => {
            e.stopPropagation();
            state.sort = btn.dataset.value;
            state.pagination.page = 1;
            renderAll();
            updateSortDropdownUI();
          });
        });

        document.addEventListener('click', () => {
          closeAllPanels();
        });

        // Reset
        document.getElementById('reset-btn').addEventListener('click', () => {
          state.filters.search = '';
          state.filters.sources = data.sources.map(s => s.id);
          state.filters.tag = 'all';
          state.filters.dateRange = 'all';
          state.filters.customStart = '';
          state.filters.customEnd = '';
          state.sort = 'desc';
          state.pagination.page = 1;
          searchInput.value = '';
          searchClear.classList.add('hidden');
          document.getElementById('custom-start').value = '';
          document.getElementById('custom-end').value = '';
          renderSourceDropdown();
          renderTagDropdown();
          updateDateDropdownUI();
          updateSortDropdownUI();
          renderAll();
        });

        // Clear all filters
        document.getElementById('clear-all-filters').addEventListener('click', () => {
          state.filters.search = '';
          state.filters.sources = data.sources.map(s => s.id);
          state.filters.tag = 'all';
          state.filters.dateRange = 'all';
          state.filters.customStart = '';
          state.filters.customEnd = '';
          state.pagination.page = 1;
          searchInput.value = '';
          searchClear.classList.add('hidden');
          document.getElementById('custom-start').value = '';
          document.getElementById('custom-end').value = '';
          renderSourceDropdown();
          renderTagDropdown();
          updateDateDropdownUI();
          renderAll();
        });

        document.getElementById('empty-clear-btn').addEventListener('click', () => {
          document.getElementById('clear-all-filters').click();
        });

        // Refresh
        document.getElementById('refresh-btn').addEventListener('click', () => {
          refreshFromRSS();
        });

        // Load more
        document.getElementById('load-more-btn').addEventListener('click', () => {
          state.pagination.page += 1;
          renderPolicyList();
        });
      }

      function updateDateDropdownUI() {
        document.querySelectorAll('.date-option').forEach(btn => {
          const active = btn.dataset.value === state.filters.dateRange;
          btn.className = 'date-option w-full text-left px-3 py-2 rounded text-sm ' + (active ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-100');
        });
      }

      function updateSortDropdownUI() {
        document.querySelectorAll('.sort-option').forEach(btn => {
          const active = btn.dataset.value === state.sort;
          btn.className = 'sort-option w-full text-left px-3 py-2 rounded text-sm ' + (active ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-100');
        });
      }

      renderSourceDropdown();
      renderTagDropdown();
      bindEvents();
      renderAll();
    })();
  </script>
</body>
</html>
"""


def generate_html(items):
    """生成交互式 HTML 预览页"""
    total = len(items)
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    rss_link = "./rss.xml"

    sorted_items = sorted(items, key=lambda x: x.get('pub_date', ''), reverse=True)

    sources = []
    source_ids = sorted(set(item.get('source_id', '') for item in items))
    for sid in source_ids:
        name = next((i['source'] for i in items if i.get('source_id') == sid), sid)
        count = sum(1 for i in items if i.get('source_id') == sid)
        sources.append({"id": sid, "name": name, "count": count})

    policies = []
    for item in sorted_items:
        pub_date = item.get('pub_date', '')
        date_str = pub_date[:10] if pub_date else ''
        summary = item.get('description', '').replace('📄 摘要：', '').strip()
        policies.append({
            "id": f"{item.get('source_id', '')}-{hash(item['link'])}",
            "title": item['title'],
            "link": item['link'],
            "date": date_str,
            "sourceId": item.get('source_id', ''),
            "source": item['source'],
            "summary": summary,
            "tags": item.get('tags', []),
        })

    all_tags = sorted(set(tag for item in items for tag in item.get('tags', [])))

    policy_data = {
        "meta": {
            "updatedAt": updated_at,
            "totalCount": total,
        },
        "sources": sources,
        "allTags": all_tags,
        "rssLink": rss_link,
        "policies": policies,
    }

    policy_data_json = json.dumps(policy_data, ensure_ascii=False, separators=(",", ":"))

    html = HTML_TEMPLATE
    html = html.replace("{total}", str(total))
    html = html.replace("{updated_at}", updated_at)
    html = html.replace("{rss_link}", rss_link)
    html = html.replace("{policy_data_json}", policy_data_json)
    return html


def main():
    print(f"[{datetime.now()}] 开始抓取政策数据...")
    print("=" * 60)

    all_items = []
    session = create_session()

    for source_key, source_config in SOURCES.items():
        try:
            print(f"[INFO] 正在抓取: {source_config['name']}")
            source_type = source_config.get('type', 'html_list')
            if source_type == 'search_api':
                items = parse_search_api(source_key, source_config, session)
            else:
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

    # 过滤：只保留最近 7 天内的文章（无日期的也保留，避免漏掉有效内容）
    from datetime import timedelta
    cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=7)
    filtered = []
    for item in unique_items:
        pub_date = item.get('pub_date')
        if not pub_date:
            filtered.append(item)
            continue
        try:
            if datetime.fromisoformat(pub_date) >= cutoff:
                filtered.append(item)
        except:
            filtered.append(item)
    unique_items = filtered

    unique_items.sort(key=lambda x: x.get('pub_date', ''), reverse=True)
    print(f"[INFO] 去重过滤后共 {len(unique_items)} 条（最近7天）")

    # 保存
    os.makedirs('public', exist_ok=True)

    with open('public/rss.xml', 'w', encoding='utf-8') as f:
        f.write(generate_rss(unique_items))

    with open('public/index.html', 'w', encoding='utf-8') as f:
        f.write(generate_html(unique_items))

    print(f"[OK] 已生成: public/rss.xml ({len(unique_items)} 条)")


if __name__ == '__main__':
    main()
