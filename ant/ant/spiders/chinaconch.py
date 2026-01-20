import json
from urllib.parse import urlencode

import scrapy
from ant.items import AntItem


class ChinaconchSpider(scrapy.Spider):
    name = "chinaconch"
    allowed_domains = ["srm.chinaconch.com"]
    page_size = 10
    base_url = "https://srm.chinaconch.com/ssrc/v1/3/hlsn/oauth-source-notices/br-list/public"
    
    # 关键字列表，用于筛选 bidTitle（可根据需要修改）
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
        """从第 0 页开始请求 API（API 使用 0-based 分页）。"""
        yield from self._make_request(page_number=0)

    def _make_request(self, page_number: int):
        params = {
            "lang": "zh_CN",
            "sourceFrom": "BID",
            "page": page_number,
            "size": self.page_size,
        }
        url = f"{self.base_url}?{urlencode(params)}"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://srm.chinaconch.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        self.logger.info(f"请求 API: {url}")
        yield scrapy.Request(url, headers=headers, callback=self.parse, meta={"page_number": page_number})

    def parse(self, response):
        page_number = response.meta.get("page_number", 0)

        try:
            data = response.json()
        except Exception as e:
            self.logger.error(f"响应非 JSON，错误: {e}，前 200 字符: {response.text[:200]}")
            return

        # 获取分页信息
        total_pages = data.get("totalPages", 0)
        total_elements = data.get("totalElements", 0)
        current_page = data.get("number", page_number)
        content_list = data.get("content", [])

        self.logger.info(f"第 {current_page + 1} 页，共 {total_pages} 页，总计 {total_elements} 条数据，本页 {len(content_list)} 条")

        if not content_list:
            self.logger.warning(f"第 {current_page + 1} 页未返回数据，停止翻页")
            return

        # 处理每条记录
        for rec in content_list:
            bid_title = rec.get("bidTitle")
            bid_status_meaning = rec.get("bidStatusMeaning")
            sign_start_date = rec.get("signStartDate")
            
            # 根据 bidTitle 进行筛选
            if bid_title:
                bid_title_lower = str(bid_title).lower()
                # 检查标题是否包含任何关键字（不区分大小写）
                contains_keyword = any(keyword.lower() in bid_title_lower for keyword in self.keywords)
                
                if contains_keyword:
                    # 找到匹配的关键字（用于日志）
                    matched_keywords = [kw for kw in self.keywords if kw.lower() in bid_title_lower]
                    self.logger.debug(f"标题包含关键字: {matched_keywords} - {bid_title} (状态: {bid_status_meaning})")
                    
                    # 创建 item
                    item = AntItem()
                    item['title'] = bid_title
                    item['status'] = bid_status_meaning
                    item['time'] = sign_start_date
                    item['file_url'] = None  # API 响应中没有直接的 URL
                    item['content'] = None
                    
                    yield item
                else:
                    self.logger.debug(f"标题不包含关键字，跳过: {bid_title}")
            else:
                self.logger.debug("bidTitle 为空，跳过该项")

        # 翻页逻辑：如果当前页小于总页数减1（因为从0开始），继续下一页
        if current_page < total_pages - 1:
            next_page = current_page + 1
            self.logger.info(f"第 {current_page + 1} 页处理完成，继续爬取第 {next_page + 1} 页")
            yield from self._make_request(page_number=next_page)
        else:
            self.logger.info(f"已到最后一页（第 {current_page + 1} 页），停止爬取")
