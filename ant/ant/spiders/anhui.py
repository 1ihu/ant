import re
from datetime import datetime, timedelta
import scrapy
from ant.items import AntItem


class AnhuiSpider(scrapy.Spider):
    name = "anhui"
    allowed_domains = ["www.ahtba.org.cn"]
    start_urls = ["https://www.ahtba.org.cn/site/trade/affiche/gotoTradeList?tradeType=01&classify=A&affiche=A00"]
    
    # 关键字列表，用于筛选标题
    keywords = [
        '设计施工总承包',
        'epc',
        '增容',
        '配电',
        '电力',
        '设计',
        '光伏',
        '新能源',
        '储能',
        '线路',
        '迁改',
        '架空',
        '送出',
        '升压站',
        '输变电',
        '变电站',
        '断路器',
        '接入系统',
        '电能质量评估',
        '光储充',
        '风储',
        '渔光互补',
        '风电',
        '锂电',
        '可研',
        '大修',
    ]

    def parse(self, response):
        # 添加调试信息
        self.logger.info(f"响应状态码: {response.status}")
        self.logger.info(f"响应URL: {response.url}")
        
        # 检查响应是否成功
        if response.status != 200:
            self.logger.error(f"请求失败，状态码: {response.status}")
            return
        
        # 使用 CSS 选择器查找所有的 li 元素
        # 选择器: #tradeList > div > ul > li (获取所有li，而不是只获取第一个)
        li_items = response.css('#tradeList > div > ul > li')
        self.logger.info(f"找到 {len(li_items)} 个 li 元素")
        
        if len(li_items) == 0:
            self.logger.warning("未找到 li 元素，可能是页面结构变化或选择器不正确")
            self.logger.debug(f"响应内容前500字符: {response.text[:500]}")
            return
        
        # 计算18天前的日期
        today = datetime.now()
        cutoff_date = today - timedelta(days=18)
        should_stop = False  # 标记是否应该停止翻页
        
        # 循环遍历每个 li 元素
        for li in li_items:
            item = AntItem()
            
            # 提取标题和链接
            # 标题在 div.titBox > div.fl.tit > a
            title_link = li.css('div.titBox > div.fl.tit > a')
            if title_link:
                # 从 a 标签中提取标题文本
                item['title'] = title_link.css('::text').get()
                link = title_link.css('::attr(href)').get()
                if link:
                    item['file_url'] = response.urljoin(link)  # 转换为绝对URL
                else:
                    item['file_url'] = None
            else:
                # 如果没有找到，尝试备用选择器
                item['title'] = li.css('a::text').get()
                link = li.css('a::attr(href)').get()
                if link:
                    item['file_url'] = response.urljoin(link)
                else:
                    item['file_url'] = None
            
            # 提取时间（根据实际页面结构调整选择器）
            time_str = None
            # 方法1：查找包含日期的文本节点
            all_texts = li.css('::text').getall()
            for text in all_texts:
                text = text.strip()
                # 检查是否是日期格式（YYYY-MM-DD 或 YYYY/MM/DD）
                if re.match(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}', text):
                    time_str = text
                    break
            
            # 方法2：如果方法1失败，尝试从span或其他元素中提取
            if not time_str:
                time_str = li.css('span::text').re_first(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}')
            
            item['time'] = time_str.strip() if time_str else None
            
            # 解析时间并检查是否超过18天
            if time_str:
                time_str = time_str.strip()
                parsed_date = self._parse_date(time_str)
                if parsed_date:
                    if parsed_date < cutoff_date:
                        should_stop = True
                        self.logger.info(f"发现超过18天的数据：{time_str} ({parsed_date.strftime('%Y-%m-%d')})，将停止爬取并导出数据")
                        # 遇到超过18天的数据，立即停止处理当前页剩余数据
                        break
            
            # 提取状态（如果有）
            status = li.css('span.status::text').get() or li.css('.status::text').get()
            item['status'] = status.strip() if status else None
            
            # 清理数据
            if item['title']:
                item['title'] = item['title'].strip()
            
            # 关键字筛选：检查标题是否包含任何关键字
            if item['title']:
                title_lower = item['title'].lower()
                # 检查标题是否包含任何关键字（不区分大小写）
                contains_keyword = any(keyword.lower() in title_lower for keyword in self.keywords)
                
                if contains_keyword:
                    # 找到匹配的关键字（用于日志）
                    matched_keywords = [kw for kw in self.keywords if kw.lower() in title_lower]
                    self.logger.debug(f"标题包含关键字: {matched_keywords} - {item['title']}")
                    yield item
                else:
                    self.logger.debug(f"标题不包含关键字，跳过: {item['title']}")
            else:
                # 如果没有标题，也跳过
                self.logger.debug("标题为空，跳过该项")
        
        # 如果发现超过18天的数据，停止翻页并终止程序
        if should_stop:
            self.logger.info("=" * 50)
            self.logger.info("检测到超过18天的数据，停止爬取。程序将正常终止，数据已导出。")
            self.logger.info("=" * 50)
            return  # 直接返回，不执行任何翻页逻辑
        
        # 翻页逻辑：根据URL规律手动构造下一页URL
        # 需要根据实际网站的翻页规律调整
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        
        parsed = urlparse(response.url)
        params = parse_qs(parsed.query)
        
        # 尝试获取当前页码（可能是 pageNo、page、p 等参数）
        current_page = 1
        page_param = None
        for param_name in ['pageNo', 'page', 'p', 'currentPage']:
            if param_name in params:
                try:
                    current_page = int(params[param_name][0])
                    page_param = param_name
                    break
                except (ValueError, IndexError):
                    continue
        
        # 如果没有找到页码参数，假设是第一页，使用 pageNo 作为参数名
        if page_param is None:
            page_param = 'pageNo'
            current_page = 1
        
        next_page = current_page + 1
        
        # 再次检查 should_stop（双重保险，确保不会继续翻页）
        if should_stop:
            self.logger.info("检测到终止标志，停止翻页")
            return
        
        # 检查当前页是否有数据，如果没有数据就不继续翻页
        if len(li_items) > 0:
            # 构造下一页URL
            params[page_param] = [str(next_page)]
            new_query = urlencode(params, doseq=True)
            next_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
            
            self.logger.info(f"当前第 {current_page} 页，找到 {len(li_items)} 条数据，继续爬取第 {next_page} 页")
            yield response.follow(next_url, callback=self.parse)
        else:
            self.logger.info(f"当前第 {current_page} 页没有数据，停止翻页")
    
    def _parse_date(self, date_str):
        """
        解析日期字符串，支持多种格式
        返回 datetime 对象，如果解析失败返回 None
        """
        if not date_str:
            return None
        
        # 清理字符串
        date_str = date_str.strip()
        
        # 常见的日期格式
        date_formats = [
            '%Y-%m-%d',           # 2024-01-12
            '%Y/%m/%d',           # 2024/01/12
            '%Y年%m月%d日',        # 2024年1月12日
            '%Y.%m.%d',           # 2024.01.12
            '%m-%d',              # 01-12 (假设是今年)
            '%m/%d',              # 01/12 (假设是今年)
            '%m月%d日',            # 1月12日 (假设是今年)
        ]
        
        for fmt in date_formats:
            try:
                parsed = datetime.strptime(date_str, fmt)
                # 如果格式中没有年份（如 01-12），假设是今年
                if '%Y' not in fmt:
                    parsed = parsed.replace(year=datetime.now().year)
                return parsed
            except ValueError:
                continue
        
        # 如果所有格式都失败，尝试使用正则表达式提取日期
        # 匹配 2024-01-12 或 2024/01/12 等格式
        match = re.search(r'(\d{4})[-\/年](\d{1,2})[-\/月](\d{1,2})', date_str)
        if match:
            try:
                year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                return datetime(year, month, day)
            except ValueError:
                pass
        
        # 匹配只有月日的格式（如 01-12）
        match = re.search(r'(\d{1,2})[-\/月](\d{1,2})', date_str)
        if match:
            try:
                month, day = int(match.group(1)), int(match.group(2))
                # 假设是今年
                return datetime(datetime.now().year, month, day)
            except ValueError:
                pass
        
        self.logger.warning(f"无法解析日期格式: {date_str}")
        return None