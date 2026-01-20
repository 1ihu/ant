import json
import re
from datetime import datetime, timedelta
from urllib.parse import urlencode

import scrapy
from ant.items import AntItem


class HuarunSpider(scrapy.Spider):
    name = "huarun"
    allowed_domains = ["scm.crland.com.cn"]
    page_size = 10
    base_url = "https://scm.crland.com.cn/api/isp/notice/tender/page"
    
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
        """从第 1 页开始请求 API。"""
        yield from self._make_request(page_number=1)

    def _make_request(self, page_number: int):
        params = {
            "page": page_number,
            "size": self.page_size,
        }
        url = f"{self.base_url}?{urlencode(params)}"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://scm.crland.com.cn/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        self.logger.info(f"请求 API: {url}")
        yield scrapy.Request(url, headers=headers, callback=self.parse, meta={"page_number": page_number})

    def parse(self, response):
        page_number = response.meta.get("page_number", 1)

        try:
            data = response.json()
        except Exception as e:
            self.logger.error(f"响应非 JSON，错误: {e}，前 200 字符: {response.text[:200]}")
            return

        # 检查响应状态
        if data.get("status") != "SUCCESS":
            self.logger.warning(f"第 {page_number} 页响应状态异常: {data.get('status')}")
            return

        # 获取结果列表
        response_body = data.get("responseBody", {})
        result_list = response_body.get("resultList", [])

        if not result_list:
            self.logger.warning(f"第 {page_number} 页未返回数据，停止翻页")
            return

        # 计算18天前的日期
        today = datetime.now()
        cutoff_date = today - timedelta(days=18)
        should_stop = False  # 标记是否应该停止翻页

        # 产出记录
        for rec in result_list:
            item = AntItem()
            item['title'] = rec.get("title") or rec.get("noticeTitle") or rec.get("name")
            item['file_url'] = rec.get("url") or rec.get("fileUrl") or rec.get("link") or rec.get("detailUrl")
            item['time'] = rec.get("publishTime") or rec.get("publishDate") or rec.get("date") or rec.get("createTime")
            item['status'] = rec.get("status") or rec.get("noticeStatus")
            item['content'] = rec.get("content") or rec.get("description") or rec.get("summary")
            
            # 清理数据
            if item['title']:
                item['title'] = str(item['title']).strip()
            if item['time']:
                item['time'] = str(item['time']).strip()
            
            # 解析时间并检查是否超过18天
            if item['time']:
                parsed_date = self._parse_date(item['time'])
                if parsed_date:
                    if parsed_date < cutoff_date:
                        should_stop = True
                        self.logger.info(f"发现超过18天的数据：{item['time']} ({parsed_date.strftime('%Y-%m-%d')})，将停止翻页")
                        # 遇到超过18天的数据，立即停止处理当前页剩余数据
                        break
            
            # 关键字筛选：检查标题是否包含任何关键字
            if item['title']:
                title_lower = item['title'].lower()
                # 检查标题是否包含任何关键字（不区分大小写）
                contains_keyword = any(keyword.lower() in title_lower for keyword in self.keywords)
                
                if contains_keyword:
                    # 状态筛选：排除"报名结束"的记录
                    if item['status'] and '报名结束' in str(item['status']):
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

        # 翻页逻辑：如果本页数据量等于page_size，尝试下一页
        if len(result_list) >= self.page_size:
            next_page = page_number + 1
            self.logger.info(f"第 {page_number} 页有 {len(result_list)} 条数据，继续爬取第 {next_page} 页")
            yield from self._make_request(page_number=next_page)
        else:
            self.logger.info(f"第 {page_number} 页数据量不足 {self.page_size}，已到最后一页，停止爬取")
    
    def _parse_date(self, date_str):
        """
        解析日期字符串，支持多种格式
        返回 datetime 对象，如果解析失败返回 None
        """
        if not date_str:
            return None
        
        # 清理字符串
        date_str = str(date_str).strip()
        
        # 常见的日期格式
        date_formats = [
            '%Y-%m-%d %H:%M:%S',     # 2024-01-12 10:30:00
            '%Y-%m-%d',               # 2024-01-12
            '%Y/%m/%d %H:%M:%S',      # 2024/01/12 10:30:00
            '%Y/%m/%d',               # 2024/01/12
            '%Y年%m月%d日',            # 2024年1月12日
            '%Y.%m.%d',               # 2024.01.12
            '%m-%d',                  # 01-12 (假设是今年)
            '%m/%d',                  # 01/12 (假设是今年)
            '%m月%d日',                # 1月12日 (假设是今年)
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