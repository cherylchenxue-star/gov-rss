# 政府政策聚合 RSS

聚合多个政府部门政策信息的 RSS 订阅源。

## 访问地址

- **网页预览**: https://cherylchenxue-star.github.io/gov-rss/
- **RSS 订阅**: https://cherylchenxue-star.github.io/gov-rss/rss.xml

## 数据来源（共12个）

### 工信部（7个）
| 来源名称 | 网址 |
|---------|------|
| 工信部信息通信发展司 | https://www.miit.gov.cn/jgsj/txs/wjfb/index.html |
| 工信部科技司 | https://www.miit.gov.cn/jgsj/kjs/wjfb/index.html |
| 工信部高新技术司 | https://www.miit.gov.cn/gyhxxhb/jgsj/gxjss/wjfb/index.html |
| 工信部网络安全管理局 | https://www.miit.gov.cn/jgsj/waj/wjfb/index.html |
| 工信部信息通信管理局 | https://www.miit.gov.cn/jgsj/xgj/wjfb/index.html |
| 工信部政策文件 | https://www.miit.gov.cn/zwgk/index.html |
| 工信部中小企业促进中心 | https://www.chinasme.org.cn/html/mcms/daohang/zhengcehuibian/index.html |

### 其他部委（5个）
| 来源名称 | 网址 |
|---------|------|
| 科技部科技政策 | https://www.most.gov.cn/satp/ |
| 国家数据局 | https://www.nda.gov.cn/sjj/zwgk/tzgg/list/index_pc_1.html |
| 国家发改委 | https://www.ndrc.gov.cn/xxgk/ |
| 国家网信办 | https://www.cac.gov.cn/wxzw/A0937index_1.htm |
| 中国人工智能学会 | https://www.caai.cn/site/term/14.html |

## 更新频率

每天 3 次（北京时间 06:00、14:00、22:00）

## 功能特性

- 自动抓取政策原文摘要
- 多源聚合去重
- 反爬对策（随机延时、User-Agent轮换）
- RSS 2.0 标准格式
- 智能过滤导航/面包屑文本

## 项目结构

```
gov-rss/
├── policy_aggregator.py    # 主程序：数据抓取与RSS生成
├── .github/workflows/
│   └── update-rss.yml      # GitHub Actions 自动更新
└── README.md               # 本文件
```

## 技术栈

- Python 3.11
- requests + BeautifulSoup4（网页抓取）
- GitHub Actions（定时任务）
- GitHub Pages（RSS托管）
