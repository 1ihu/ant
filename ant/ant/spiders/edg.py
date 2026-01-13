import scrapy
from ant.items import AntItem


class EdgSpider(scrapy.Spider):
    name = "edg"
    allowed_domains = ["www.ediangong.net"]
    start_urls = ["https://www.ediangong.net"]

    def parse(self, response):
        # 添加调试信息：检查响应状态
        self.logger.info(f"响应状态码: {response.status}")
        self.logger.info(f"响应URL: {response.url}")
        self.logger.info(f"响应体长度: {len(response.body)}")
        
        # 检查响应是否成功
        if response.status != 200:
            self.logger.error(f"请求失败，状态码: {response.status}")
            return
        
        # Scrapy 的 response 对象本身就有 css() 和 xpath() 方法，不需要创建 Selector
        # 尝试多种选择器来查找电影列表
        items = response.css('ol.grid_view li')
        if not items:
            items = response.css('#__layout > div > div.index_box > div.serverListBox > div.serverList > div.item')
        
        self.logger.info(f"找到 {len(items)} 个电影项")
        
        if len(items) == 0:
            # 如果找不到项目，保存响应内容用于调试
            self.logger.warning("未找到电影列表，可能是页面结构变化或反爬虫拦截")
            self.logger.debug(f"响应内容前500字符: {response.text[:500]}")
            return
        
        # 解析当前页面的电影数据
        for item in items:
            move_item = AntItem()
            move_item['title'] = item.css('span.serverTxt').get()
            # move_item['desc'] = item.css('div > div.info > div.bd > p::text').get()
            yield move_item
        
        # 方法1：自动查找"下一页"链接
        next_page = response.css('span.next a::attr(href)').get()
        if next_page:
            # 构建完整的下一页 URL
            next_page_url = response.urljoin(next_page)
            self.logger.info(f"找到下一页链接: {next_page_url}")
            yield scrapy.Request(url=next_page_url, callback=self.parse)
        else:
            self.logger.info("没有找到下一页链接，爬取完成")
        
        # 方法2：手动构造翻页 URL（备用方案，如果方法1失败可以使用）
        # 豆瓣 Top250 的 URL 规律：?start=0, 25, 50, 75, ..., 225 (共10页)
        # 如果需要使用此方法，可以取消下面的注释并注释掉上面的方法1
        """
        # 从当前 URL 中提取 start 参数
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        parsed = urlparse(response.url)
        params = parse_qs(parsed.query)
        current_start = int(params.get('start', [0])[0])
        next_start = current_start + 25
        
        # 如果还有下一页（Top250 总共250部电影，最后一页 start=225）
        if next_start < 250:
            params['start'] = [str(next_start)]
            new_query = urlencode(params, doseq=True)
            next_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
            self.logger.info(f"构造下一页URL: {next_url}")
            yield scrapy.Request(url=next_url, callback=self.parse)
        else:
            self.logger.info("已爬取所有页面，完成")
        """