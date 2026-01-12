import scrapy


class EdgSpider(scrapy.Spider):
    name = "edg"
    allowed_domains = ["www.ediangong.net"]
    start_urls = ["https://www.ediangong.net"]

    def parse(self, response):
        pass
