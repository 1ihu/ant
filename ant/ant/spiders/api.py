import json
from urllib.parse import urlencode

import scrapy


class ApiSpider(scrapy.Spider):
    """
    直接调用 API 获取公告列表，避免处理动态页面。
    如果目标字段与这里假设的不一致，可在日志里查看完整记录后微调字段映射。
    """

    name = "api"
    allowed_domains = ["glzb.geely.com"]
    page_size = 26
    base_url = "https://glzb.geely.com/gpmp/notice/listnotice"

    def start_requests(self):
        """从第 1 页开始请求 API。"""
        yield from self._make_request(page_number=1)

    def _make_request(self, page_number: int):
        params = {
            "pagesize": self.page_size,
            "pagenumber": page_number,
            "publishstatus": 2,
            "iflongpro": 0,
            # 可选：服务器要求的时间戳参数，用于缓存穿透（示例中的 _ 参数）
            # "_" : str(int(time.time() * 1000))
        }
        url = f"{self.base_url}?{urlencode(params)}"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://glzb.geely.com/",  # 部分接口需要 Referer
            "User-Agent": "Mozilla/5.0",
        }
        self.logger.info(f"请求 API: {url}")
        yield scrapy.Request(url, headers=headers, callback=self.parse, meta={"page_number": page_number})

    def parse(self, response):
        page_number = response.meta.get("page_number", 1)

        try:
            data = response.json()
        except Exception:
            self.logger.error("响应非 JSON，前 200 字符: %s", response.text[:200])
            return

        # 兼容不同的字段命名
        body = data.get("data") or data.get("result") or {}
        records = (
            body.get("list")
            or body.get("records")
            or body.get("rows")
            or body.get("datas")
            or []
        )

        if not records:
            self.logger.warning(f"第 {page_number} 页未返回数据，停止翻页")
            return

        # 产出记录：若接口字段名不同，可根据日志调整
        for rec in records:
            yield {
                "id": rec.get("id") or rec.get("noticeId"),
                "title": rec.get("title") or rec.get("noticeTitle") or rec.get("name"),
                "publish_time": rec.get("publishTime") or rec.get("publishDate") or rec.get("date"),
                "url": rec.get("url") or rec.get("fileUrl") or rec.get("link"),
                "raw": rec,  # 保留原始记录方便调试
            }

        # 翻页逻辑
        total = body.get("total") or body.get("totalCount") or body.get("recordCount")
        page_size = body.get("pageSize") or self.page_size
        current = body.get("pageNumber") or page_number

        has_more = False
        if total is not None:
            # 有总数时，按总数判断
            has_more = current * page_size < int(total)
        else:
            # 无总数时，如果本页数量达到 page_size，尝试下一页
            has_more = len(records) >= page_size

        if has_more:
            next_page = current + 1
            yield from self._make_request(page_number=next_page)
        else:
            self.logger.info("已到最后一页，停止爬取")
