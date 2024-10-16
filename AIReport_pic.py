import os
import json
import requests
import random
import string
from common.log import logger
import plugins
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from plugins import *
import config
import asyncio
from playwright.async_api import async_playwright

@plugins.register(name="AIReport_pic",
                  desc="获取图片格式的最新AI日报",
                  version="2.0",
                  author="Lingyuzhou",
                  desire_priority=500)
class AIReport_pic(Plugin):
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        logger.info(f"[{__class__.__name__}] initialized")

    def get_help_text(self, **kwargs):
        return "输入“AI日报”获取最新的图片格式AI日报。"

    def on_handle_context(self, e_context):
        if e_context['context'].type == ContextType.TEXT:
            content = e_context["context"].content.strip()
            if content.startswith("AI日报"):
                logger.info(f"[{__class__.__name__}] 收到消息: {content}")
                asyncio.run(self.fetch_ai_news(e_context))

    async def fetch_ai_news(self, e_context):
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        if not os.path.exists(config_path):
            logger.error(f"请先配置{config_path}文件")
            self.send_error_reply(e_context, f"请先配置{config_path}文件")
            return

        with open(config_path, 'r') as file:
            config_data = json.load(file)
            api_key = config_data.get('TIAN_API_KEY', '')

        if not api_key:
            logger.error("API key配置缺失。")
            self.send_error_reply(e_context, "API key配置缺失。")
            return

        url = f"https://apis.tianapi.com/ai/index?key={api_key}&num=6"
        try:
            logger.info(f"请求API: {url}")
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            logger.debug(f"API返回数据: {data}")
            if data.get('code') == 200 and 'result' in data and 'newslist' in data['result']:
                await self.construct_reply(data['result']['newslist'], e_context)
            else:
                logger.error(f"API返回格式不正确: {data}")
                self.send_error_reply(e_context, "获取资讯失败，返回数据格式不正确。")
        except Exception as e:
            logger.error(f"接口抛出异常: {e}")
            self.send_error_reply(e_context, "请求失败，请稍后再试。")

    async def construct_reply(self, newslist, e_context):
        logger.info(f"[{__class__.__name__}] 开始生成HTML内容...")
        html_content = self.generate_html(newslist)
        logger.debug(f"生成的HTML内容: {html_content[:6000]}...")

        # 使用异步处理HTML渲染
        await self.render_html_to_image(html_content, e_context)
        logger.debug("[AIReport_pic] 卡片生成完成...")

    def generate_html(self, newslist):
        html_header = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>今日AI快讯</title>
<link href="https://fonts.googleapis.com/css2?family=DotGothic16:wght@700&display=swap" rel="stylesheet">
<style>
body {
    margin: 0;
    padding: 0;
    font-family: Arial, sans-serif;
    background-color: #e5e5e5;
}
.card {
    width: 600px;
    height: 1380px; 
    margin: 0 auto;
    background-color: #f5f5f5;
    position: relative;
    border-radius: 10px; 
    overflow: hidden; 
}
.header {
    background-color: #7da3e1;
    color: #3d72ba;
    text-align: center;
    padding: 25px 0;
    font-size: 40px;
    height: 100px;
    box-sizing: border-box;
    border-top-left-radius: 10px; 
    border-top-right-radius: 10px; 
    font-family: 'DotGothic16', sans-serif; 
    font-weight: 700; 
}
.news-container {
    padding: 20px 0;
    height: calc(1380px - 160px); /* Adjust for header and footer */
    overflow-y: auto; /* Allow scrolling if content exceeds height */
}
.news-unit {
    display: flex;
    margin: 0 20px 20px;
    background-color: #ffffff;
    box-shadow: 0 0 5px rgba(0,0,0,0.1);
    height: 180px;
    border-radius: 8px; 
    overflow: hidden; 
}
.news-unit img {
    width: 240px;
    height: 180px;
    object-fit: cover;
}
.text-block {
    padding: 10px 20px;
    width: 300px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}
.title {
    font-weight: bold;
    font-size: 14px;
    color: #333;
}
.description {
    font-family: 'KaiTi', 'SimKai';
    font-size: 14px;
    margin: 10px 0;
    overflow: hidden;
}
.ctime {
    font-size: 12px;
    color: #999;
    align-self: flex-end;
    margin-top: auto; 
}
.footer {
    background-color: #7da3e1;
    color: #ffffff;
    text-align: center;
    padding: 20px 0;
    font-size: 14px;
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 60px;
    box-sizing: border-box;
    border-bottom-left-radius: 10px;
    border-bottom-right-radius: 10px; 
}
</style>
</head>
<body>
<div class="card">
    <div class="header">今日AI快讯</div>
    <div class="news-container">'''

        html_footer = '''    </div>
    <div class="footer">此卡片由Lingyuzhou的AI助手生成</div>
</div>
</body>
</html>'''

        news_units = ""
        for news_item in newslist:
            title = news_item.get('title', '未知标题')
            description = news_item.get('description', '无描述')
            ctime = news_item.get('ctime', '未知时间')
            picUrl = news_item.get('picUrl', '')

            if len(description) > 100:
                description = description[:100] + '...'

            # 检查图片 URL 是否有效
            if picUrl:
                news_units += f'''
                <div class="news-unit">
                    <img src="{picUrl}" alt="news image">
                    <div class="text-block">
                        <div class="title">{title}</div>
                        <div class="description">{description}</div>
                        <div class="ctime">{ctime}</div>
                    </div>
                </div>'''
            else:
                logger.warning(f"无效的图片 URL: {picUrl}")

        return html_header + news_units + html_footer

    async def render_html_to_image(self, html_content, e_context):
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                await page.set_viewport_size({"width": 600, "height": 1380})
                try:
                    await page.set_content(html_content, timeout=60000)  # 设置超时为60秒
                    img_content = await page.screenshot()
                    logger.debug("[AIReport_pic] 图片生成成功")
                    await self.send_image_to_wechat(img_content, e_context)
                except Exception as e:
                    logger.error(f"设置页面内容失败: {e}")
                finally:
                    await browser.close()
        except Exception as e:
            logger.error(f"HTML渲染为图片失败: {e}")
            self.send_error_reply(e_context, "生成卡片失败，请稍后再试...")

    async def send_image_to_wechat(self, img_content, e_context):
        """发送生成的图片到微信"""
        from io import BytesIO
        content_io = BytesIO(img_content)
        await self._send_img(e_context, content_io)

    async def _send_img(self, e_context, content_io):
        reply = Reply(ReplyType.IMAGE, content_io)
        channel = e_context["channel"]
        await channel.send(reply, e_context["context"])

    def send_error_reply(self, e_context, error_message):
        """发送错误回复"""
        logger.error(error_message)  # Log the error message
        reply = Reply(ReplyType.ERROR, error_message)
        e_context["reply"] = reply
        e_context.action = EventAction.BREAK_PASS