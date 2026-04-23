```markdown
# Amazon Rank Crawler 📊

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.7%2B-blue)](https://www.python.org/downloads/)
[![Build Status](https://img.shields.io/github/actions/workflow/status/yourusername/amazon_rank_crawler/ci.yml?branch=main)](https://github.com/yourusername/amazon_rank_crawler/actions/workflows/ci.yml)
[![Issues](https://img.shields.io/github/issues/yourusername/amazon_rank_crawler)](https://github.com/yourusername/amazon_rank_crawler/issues)
[![Stars](https://img.shields.io/github/stars/yourusername/amazon_rank_crawler)](https://github.com/yourusername/amazon_rank_crawler/stargazers)

---

## 📌 项目介绍

**Amazon Rank Crawler** 是一个强大的开源爬虫工具，旨在帮助用户高效地抓取和分析亚马逊商品的销售排名及相关数据。该项目基于多种技术栈构建，包括 Python、JavaScript、TypeScript 和 C++，并利用 `playwright` 进行浏览器自动化，结合 `BeautifulSoup` 和 `lxml` 进行网页解析，最终将数据导出为 Excel 文件，方便后续分析和处理。

### 🛠️ 主要功能

- **自动化的网页抓取**：通过 `playwright` 实现对亚马逊商品列表页和详情页的自动化访问。
- **数据解析与提取**：使用 `BeautifulSoup` 和 `lxml` 解析网页内容，提取商品的关键信息，如排名、ASIN、标题、价格、评分、评论数、品牌、月销量、优惠券折扣等。
- **数据导出**：将抓取到的数据整理成结构化的 Excel 文件，方便用户进行数据分析。
- **错误处理与重试机制**：内置 `retry_manager` 模块，支持对网络请求失败进行自动重试，提高爬虫的稳定性。
- **多线程与并发控制**：通过 `crawler_settings` 配置并发参数，优化抓取效率。

---

## 🚀 快速开始

### 1. 环境准备

确保你的系统已安装以下软件：

- **Python 3.7+**
- **pip**

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 运行爬虫

```bash
python main.py
```

### 4. 查看输出

抓取到的数据将保存在 `output/amazon_sale_info.xlsx` 文件中，商品图片保存在 `output/images/` 目录。

---

## 📦 安装部署

### 1. 克隆仓库

```bash
git clone https://github.com/yourusername/amazon_rank_crawler.git
cd amazon_rank_crawler
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置爬虫

编辑 `config.py` 文件，根据需要调整爬虫的设置，例如：

```python
class CrawlerSettings:
    start_url = "https://www.amazon.com/Best-Sellers/zgbs"
    headless = True  # 是否以无头模式运行浏览器
    browser_channel = None
    slow_mo_ms = 100  # 模拟人类操作的延迟时间（毫秒）
    max_detail_concurrency = 5  # 详情页抓取的并发数
```

### 4. 运行爬虫

```bash
python main.py
```

---

## 📖 使用示例

以下是一个简单的使用示例，展示如何启动爬虫并获取商品列表页的数据：

```python
from amazon_rank_crawler import AmazonRankCrawler, CrawlerSettings

async def main():
    settings = CrawlerSettings(
        start_url="https://www.amazon.com/Best-Sellers/zgbs",
        headless=True,
        slow_mo_ms=50,
        max_detail_concurrency=3,
    )
    crawler = AmazonRankCrawler(settings)
    list_records = await crawler.crawl_list_page()
    print(f"List page records collected: {len(list_records)}")
    for item in list_records[:3]:
        print({
            "rank": item.rank,
            "asin": item.asin,
            "title": item.title,
            "price": item.price,
            "rating": item.rating,
            "review_count": item.review_count,
        })

    detail_records = await crawler.crawl_detail_pages(list_records)
    print(f"Detail page records enriched: {len(detail_records)}")
    for item in detail_records[:3]:
        print({
            "asin": item.asin,
            "brand": item.brand,
            "monthly_sales": item.monthly_sales,
            "coupon_discount": item.coupon_discount,
            "dimensions_weight": item.dimensions_weight,
            "feature_1": item.feature_1,
            "sub_category_rank": item.sub_category_rank,
            "a_plus_content_flag": item.a_plus_content_flag,
            "bad_review_1": item.bad_review_1,
        })

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🏗️ 项目结构

```text
📁 amazon_rank_crawler
  📄 __init__.py
  📄 base.py          # 基础类定义
  📄 browser.py       # 浏览器自动化相关逻辑
  📄 config.py        # 爬虫配置
  📄 detail_page.py   # 详情页解析逻辑
  📄 exporter.py      # 数据导出模块
  📄 list_page.py     # 列表页解析逻辑
  📄 models.py        # 数据模型定义
  📄 retry_manager.py # 重试机制实现
  📄 runner.py        # 爬虫运行器
  📄 utils.py         # 工具函数
📁 logs               # 日志文件目录
📁 output             # 输出文件目录
  📁 images           # 商品图片保存目录
  📄 amazon_sale_info.xlsx # 抓取到的数据
📁 temp               # 临时文件目录
📁 tests              # 测试用例目录
  📄 test_parsers_smoke.py
📄 main.py            # 入口文件
📄 requirements.txt   # 项目依赖
📄 run_amazon_sale_info.py
📄 run_amazon_sale_info_list_only.py
📄 run_amazon_sale_info_smoke.py
```

---

## ⚙️ 配置说明

### 1. `config.py`

- **start_url**: 爬虫的起始 URL。
- **headless**: 是否以无头模式运行浏览器。
- **slow_mo_ms**: 模拟人类操作的延迟时间（毫秒）。
- **max_detail_concurrency**: 详情页抓取的并发数。

### 2. `crawler_settings`

通过调整 `crawler_settings` 中的参数，可以控制爬虫的行为，例如并发数、抓取速度等。

---

## ❓ FAQ

### 1. 如何增加新的抓取字段？

在 `models.py` 中添加新的字段，并在 `detail_page.py` 或 `list_page.py` 中实现相应的解析逻辑。

### 2. 如何处理验证码或反爬机制？

本项目集成了 `playwright-stealth` 模块，可以有效绕过部分反爬机制。如果遇到验证码，建议使用第三方验证码识别服务。

### 3. 如何提高抓取效率？

可以通过调整 `crawler_settings` 中的 `max_detail_concurrency` 参数，增加并发数，或者优化解析逻辑，提高解析速度。

---

## 🤝 贡献指南

我们欢迎所有对项目感兴趣的开发者参与贡献！以下是一些贡献的建议：

1. **提交问题**: 如果你遇到任何问题或有任何建议，请随时提交 issue。
2. **提交代码**: 如果你想贡献代码，请先 fork 项目，然后提交 pull request。
3. **文档完善**: 帮助完善项目的文档和注释。
4. **测试**: 编写和运行测试用例，确保项目的稳定性。

---

## 📜 许可证

本项目采用 [MIT 许可证](https://opensource.org/licenses/MIT)。详细信息请参见 [LICENSE](https://github.com/yourusername/amazon_rank_crawler/blob/main/LICENSE) 文件。

---

## 📧 联系方式

- **GitHub**: [yourusername](https://github.com/yourusername)
- **Email**: your_email@example.com

---

感谢你的关注和使用！希望 Amazon Rank Crawler 能帮助你高效地获取亚马逊商品的销售数据。如果有任何问题或建议，欢迎随时联系或提交 issue。
```

---

**注意**: 请将 `yourusername` 和 `your_email@example.com` 替换为你的实际 GitHub 用户名和邮箱地址。