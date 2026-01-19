import json
import re
from datetime import datetime, timedelta
import scrapy
from ant.items import AntItem


class WannSpider(scrapy.Spider):
    name = "wann"
    allowed_domains = ["tab.wenergy.com.cn"]
    api_url = "https://tab.wenergy.com.cn/inteligentsearch_wz/rest/esinteligentsearch/getFullTextDataNew"
    page_size = 10  # 每页10条
    
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
    
    def start_requests(self):
        """从第 1 页开始请求 API（pn=0）"""
        yield from self._make_request(pn=0)
    
    def _make_request(self, pn=0):
        """构造 POST 请求（JSON 格式）"""
        # 构造请求数据（注意 sort 是 JSON 字符串）
        request_data = {
            "token": "",
            "pn": pn,
            "rn": self.page_size,
            "sdt": "",
            "edt": "",
            "wd": "",
            "inc_wd": "",
            "exc_wd": "",
            "fields": "",
            "cnum": "001",
            "sort": '{"webdate":"0","id":"0"}',  # JSON 字符串格式
            "ssort": "",
            "cl": 200,  # 数字类型
            "terminal": "",
            "condition": [{
                "fieldName": "categorynum",
                "equal": "002001001",
                "notEqual": None,
                "equalList": None,
                "notEqualList": None,
                "isLike": True,
                "likeType": 2
            }],
            "time": [],
            "highlights": "",
            "statistics": None,
            "unionCondition": None,
            "accuracy": "",
            "noParticiple": "1",
            "searchRange": None,
            "noWd": True
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://tab.wenergy.com.cn/cgxx/002001/002001001/purchase.html",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        
        page_number = (pn // self.page_size) + 1
        self.logger.info(f"请求 API 第 {page_number} 页 (pn={pn})")
        
        yield scrapy.Request(
            url=self.api_url,
            method="POST",
            body=json.dumps(request_data, ensure_ascii=False),
            headers=headers,
            callback=self.parse,
            meta={"pn": pn, "page_number": page_number},
            errback=self.errback_handler
        )
    
    def errback_handler(self, failure):
        """处理请求失败的回调"""
        self.logger.error(f"请求失败: {failure.value}")
        if hasattr(failure.value, 'response') and failure.value.response:
            response = failure.value.response
            self.logger.error(f"响应状态码: {response.status}")
            self.logger.error(f"响应内容: {response.text[:1000]}")

    def parse(self, response):
        pn = response.meta.get("pn", 0)
        page_number = response.meta.get("page_number", 1)
        
        # 添加调试信息
        self.logger.info(f"响应状态码: {response.status}")
        self.logger.info(f"当前页码: {page_number} (pn={pn})")
        
        # 检查响应是否成功
        if response.status != 200:
            self.logger.error(f"请求失败，状态码: {response.status}")
            self.logger.error(f"响应内容: {response.text[:1000]}")
            return
        
        # 解析 JSON 响应
        try:
            data = response.json()
        except Exception as e:
            self.logger.error(f"响应非 JSON 格式: {e}")
            self.logger.debug(f"响应内容前500字符: {response.text[:500]}")
            return
        
        # 提取数据列表：数据在 result.records 中
        result = data.get("result", {})
        records = result.get("records", [])
        
        self.logger.info(f"找到 {len(records)} 条记录")
        
        if not records:
            self.logger.warning(f"第 {page_number} 页未返回数据，停止翻页")
            return
        
        # 计算18天前的日期
        today = datetime.now()
        cutoff_date = today - timedelta(days=18)
        should_stop = False  # 标记是否应该停止翻页
        
        # 循环遍历每条记录
        for record in records:
            item = AntItem()
            
            # 提取标题：字段名是 title
            item['title'] = record.get("title")
            
            # 提取链接：字段名是 linkurl（相对路径）
            linkurl = record.get("linkurl")
            if linkurl:
                # 如果是相对路径，转换为绝对路径
                if linkurl.startswith("http"):
                    item['file_url'] = linkurl
                else:
                    # 拼接完整URL
                    base_url = "https://tab.wenergy.com.cn"
                    item['file_url'] = base_url + linkurl if linkurl.startswith("/") else base_url + "/" + linkurl
            else:
                item['file_url'] = None
            
            # 提取时间：字段名是 webdate（格式：2026-01-16 00:00:00）
            item['time'] = record.get("webdate")
            
            # 清理数据
            if item['title']:
                item['title'] = str(item['title']).strip()
            if item['time']:
                item['time'] = str(item['time']).strip()
            
            # 解析时间并检查是否超过18天
            time_str = item['time']
            if time_str:
                parsed_date = self._parse_date(time_str)
                if parsed_date:
                    if parsed_date < cutoff_date:
                        should_stop = True
                        self.logger.info(f"发现超过18天的数据：{time_str} ({parsed_date.strftime('%Y-%m-%d')})，将停止爬取并导出数据")
                        # 遇到超过18天的数据，立即停止处理当前页剩余数据
                        break
            
            # 设置其他字段
            item['status'] = None
            item['content'] = None
            
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
        
        # 翻页逻辑：如果本页数据量等于 page_size，继续下一页
        # 下一页的 pn = 当前 pn + page_size (pn=0是第一页，pn=10是第二页，pn=20是第三页)
        if len(records) >= self.page_size:
            next_pn = pn + self.page_size
            next_page_number = page_number + 1
            self.logger.info(f"第 {page_number} 页有 {len(records)} 条数据，继续爬取第 {next_page_number} 页 (pn={next_pn})")
            yield from self._make_request(pn=next_pn)
        else:
            self.logger.info(f"第 {page_number} 页只有 {len(records)} 条数据（少于 {self.page_size} 条），已到最后一页")
    
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
            '%Y-%m-%d %H:%M:%S',  # 2026-01-16 00:00:00 (API返回格式)
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