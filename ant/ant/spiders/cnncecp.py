import re
from datetime import datetime, timedelta
import scrapy
from ant.items import AntItem


class CnncecpSpider(scrapy.Spider):
    name = "cnncecp"
    allowed_domains = ["www.cnncecp.com"]
    start_urls = ["https://www.cnncecp.com/xzbgg/index.jhtml"]
    
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
        # 选择器路径: body > div.n-main > div.n-right > div.BorderEEE.NoBorderTop.Padding10.WhiteBg > div.List1 > ul > li
        li_items = response.css('body > div.n-main > div.n-right > div > div > ul > li')
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
           
            # 提取状态
            status = li.css('span.Green::text').get()
            item['status'] = status.strip() if status else None
            
            # 提取标题（根据实际页面结构调整选择器）
            item['title'] = li.css('a::text').get() or li.css('span::text').get() or li.css('::text').get()
            
            # 提取链接（如果有）
            link = li.css('a::attr(href)').get()
            if link:
                item['file_url'] = response.urljoin(link)  # 转换为绝对URL
            else:
                item['desc'] = li.css('::text').getall()  # 如果没有链接，提取所有文本
            
            # 提取时间
            time_str = li.css('span.Right.Gray::text').get()
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
                    # 状态筛选：排除"报名结束"的记录
                    if item['status'] and '报名结束' in item['status']:
                        self.logger.debug(f"状态为'报名结束'，跳过: {item['title']} (状态: {item['status']})")
                    else:
                        # 找到匹配的关键字（用于日志）
                        matched_keywords = [kw for kw in self.keywords if kw.lower() in title_lower]
                        self.logger.debug(f"标题包含关键字: {matched_keywords} - {item['title']} (状态: {item['status']})")
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
        # URL规律：第一页 index.jhtml，第二页 index_2.jhtml，第三页 index_3.jhtml，以此类推
        
        # 从当前URL中提取页码
        current_url = response.url
        # 匹配 index.jhtml 或 index_数字.jhtml
        match = re.search(r'index(?:_(\d+))?\.jhtml', current_url)
        
        if match:
            # 如果匹配到数字，当前页码就是该数字；否则是第一页（页码为1）
            current_page = int(match.group(1)) if match.group(1) else 1
            next_page = current_page + 1
            
            # 构造下一页URL
            # 将 index.jhtml 或 index_数字.jhtml 替换为 index_下一页.jhtml
            if current_page == 1:
                # 第一页：index.jhtml -> index_2.jhtml
                next_url = current_url.replace('index.jhtml', f'index_{next_page}.jhtml')
            else:
                # 其他页：index_数字.jhtml -> index_下一页.jhtml
                next_url = current_url.replace(f'index_{current_page}.jhtml', f'index_{next_page}.jhtml')
            
            # 检查当前页是否有数据，如果没有数据就不继续翻页
            if len(li_items) > 0:
                self.logger.info(f"当前第 {current_page} 页，找到 {len(li_items)} 条数据，继续爬取第 {next_page} 页")
                yield response.follow(next_url, callback=self.parse)
            else:
                self.logger.info(f"当前第 {current_page} 页没有数据，停止翻页")
        else:
            self.logger.warning(f"无法从URL中提取页码: {current_url}，停止翻页")
    
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
