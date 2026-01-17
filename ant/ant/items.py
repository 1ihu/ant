# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class AntItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    # pass
    title = scrapy.Field()
    #文件url
    file_url = scrapy.Field()
    # 公告时间
    time = scrapy.Field()
    # 状态
    status = scrapy.Field()
    # 内容
    content = scrapy.Field()