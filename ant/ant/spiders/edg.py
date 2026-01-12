import scrapy
from ant.items import AntItem


class EdgSpider(scrapy.Spider):
    name = "edg"
    allowed_domains = ["movie.douban.com"]
    start_urls = ["https://movie.douban.com/top250"]

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
            items = response.css('#content > div > div.article > ol > li')
        
        self.logger.info(f"找到 {len(items)} 个电影项")
        
        if len(items) == 0:
            # 如果找不到项目，保存响应内容用于调试
            self.logger.warning("未找到电影列表，可能是页面结构变化或反爬虫拦截")
            self.logger.debug(f"响应内容前500字符: {response.text[:500]}")
            return
        
        for item in items:
            # 尝试多种方式获取标题，使用 get() 方法替代已弃用的 extract_first()
            move_item = AntItem()
            move_item['title'] = item.css('div > div.info > div.hd > a > span.title::text').get()
            move_item['desc'] = item.css('div > div.info > div.bd > p::text').get()
            yield move_item