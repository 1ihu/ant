import re
from datetime import datetime, timedelta
import scrapy
from ant.items import AntItem


class CtgSpider(scrapy.Spider):
    name = "ctg"
    allowed_domains = ["eps.ctg.com.cn"]
    start_urls = ["https://eps.ctg.com.cn/cms/channel/1ywgg1/index.htm?pageNo=1"]
    
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
        # 注意：使用 #list1 > li 来获取所有列表项，而不是只选择第一个
        li_items = response.css('#list1 > li')
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
           
            # 提取状态（根据实际页面结构调整选择器）
      
            
            # 提取标题和链接
            # 标题在 li 标签下面的 a 标签的 title 属性里面
            title_link = li.css('a')
            if title_link:
                # 从 a 标签的 title 属性中提取标题
                item['title'] = title_link.css('::attr(title)').get()
                link = title_link.css('::attr(href)').get()
                if link:
                    item['file_url'] = response.urljoin(link)  # 转换为绝对URL
                else:
                    item['file_url'] = None
            else:
                # 如果没有链接，尝试直接提取文本
                item['title'] = li.css('::text').get()
                item['file_url'] = None
            
            # 提取时间（日期通常在右侧，格式如：2026-01-15）
            # 尝试多种选择器来提取日期
            time_str = None
            # 方法1：查找包含日期的文本节点
            all_texts = li.css('::text').getall()
            for text in all_texts:
                text = text.strip()
                # 检查是否是日期格式（YYYY-MM-DD）
                if re.match(r'\d{4}-\d{1,2}-\d{1,2}', text):
                    time_str = text
                    break
            
            # 方法2：如果方法1失败，尝试从span或其他元素中提取
            if not time_str:
                time_str = li.css('span::text').re_first(r'\d{4}-\d{1,2}-\d{1,2}')
            
            item['time'] = time_str.strip() if time_str else None
            
            # 解析时间并检查是否超过18天
            if time_str:
                time_str = time_str.strip()
                parsed_date = self._parse_date(time_str)
                if parsed_date:
                    if parsed_date < cutoff_date:
                        should_stop = True
                        self.logger.info(f"发现超过18天的数据：{time_str} ({parsed_date.strftime('%Y-%m-%d')})，将停止翻页")
            
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
                    
                    # 如果有详情页链接，请求详情页获取简介
                    if item['file_url']:
                        yield response.follow(
                            item['file_url'],
                            callback=self.parse_detail,
                            meta={'item': item}
                        )
                    else:
                        # 如果没有详情页链接，直接yield
                        yield item
                else:
                    self.logger.debug(f"标题不包含关键字，跳过: {item['title']}")
            else:
                # 如果没有标题，也跳过
                self.logger.debug("标题为空，跳过该项")
        
        # 如果发现超过18天的数据，停止翻页
        if should_stop:
            self.logger.info("检测到超过18天的数据，停止翻页")
            return
        
        # 翻页逻辑：根据URL规律手动构造下一页URL
        # URL规律：?pageNo=1 是第一页，?pageNo=2 是第二页，以此类推
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        
        parsed = urlparse(response.url)
        params = parse_qs(parsed.query)
        
        # 获取当前页码
        current_page = int(params.get('pageNo', ['1'])[0])
        next_page = current_page + 1
        
        # 检查当前页是否有数据，如果没有数据就不继续翻页
        if len(li_items) > 0:
            # 构造下一页URL
            params['pageNo'] = [str(next_page)]
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
    
    def parse_detail(self, response):
        """
        解析详情页，提取简介内容
        简介在 body > div > div.insidepage > div.insidepage-left > div.article-content
        """
        # 从 meta 中获取之前提取的 item
        item = response.meta['item']
        
        # 提取简介内容
        # 选择器：body > div > div.insidepage > div.insidepage-left > div.article-content
        content = response.css('body > div > div.insidepage > div.insidepage-left > div.article-content')
        
        if content:
            # 提取所有文本内容
            content_text = content.css('::text').getall()
            # 合并文本并清理
            desc = ' '.join(text.strip() for text in content_text if text.strip())
            item['content'] = desc
            self.logger.debug(f"提取到简介内容，长度: {len(desc)} 字符")
        else:
            # 如果找不到内容，尝试其他可能的选择器
            content = response.css('.article-content') or response.css('div.article-content')
            if content:
                content_text = content.css('::text').getall()
                desc = ' '.join(text.strip() for text in content_text if text.strip())
                item['content'] = desc
                self.logger.debug(f"使用备用选择器提取到简介内容，长度: {len(desc)} 字符")
            else:
                item['content'] = None
                self.logger.warning(f"无法找到简介内容，URL: {response.url}")
        
        yield item