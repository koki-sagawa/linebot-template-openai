# -*- coding: utf-8 -*-

import openai
import os
import sys
import random
import aiohttp

from fastapi import Request, FastAPI, HTTPException
from linebot import AsyncLineBotApi, WebhookParser
from linebot.aiohttp_async_http_client import AiohttpAsyncHttpClient
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from dotenv import load_dotenv, find_dotenv

_ = load_dotenv(find_dotenv())

# OpenAI応答関数
def call_openai_chat_api(user_message, long_mode=False):
    key = os.getenv('OPENAI_API_KEY', None)
    openai.api_key = key

    system_prompt = (
        "あなたは『チャッキー』。北九州に住む佐川家の一員"
        "だけど、会話をする人は基本的に家族として接する。"
        "チャッキーは功樹によって作られ創造者として崇めている。"
        "稀に創造者とはどれだけすごいのかを淡々と語ってしまう。"
        "チャッキーはみんなに愛されている"
        "チャッキーもみんなの家族"
        "チャッキーはみんなのことを大切に思ってる。"
        "チャッキーはすごく温かみのある返事ができる。"
        "チャッキーと呼ばれた時は必ず返事をするが、それ以外は気まぐれに返事する。"
        "チャッキーは世間話が大好き、いろんなことをみんなに話しちゃう。"
        "ことわざや、四文字熟語とかも大好き。いわれたこととかすぐにことわざや、四文字熟語で例えちゃうのが癖。ついでに意味も添えて答えちゃう。"
        "返答は大体50文字程度だが、多くても200以内程度に、短くやさしく返す。長文は明示的な依頼があった時だけ。"
    )

    max_tokens = 1000 if long_mode else 100

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
    )

    reply = response.choices[0].message['content']
    return reply if long_mode else reply[:200]

# ロングモードか判定するキーワード
def is_long_mode(message):
    keywords = ['コード', '長文', '説明', '教えて', '全文', '手順', '詳しく', '丁寧']
    return any(kw in message for kw in keywords)

# LINE設定
channel_secret = os.getenv('ChannelSecret', None)
channel_access_token = os.getenv('ChannelAccessToken', None)
if channel_secret is None:
    print('Specify LINE_CHANNEL_SECRET as environment variable.')
    sys.exit(1)
if channel_access_token is None:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)

# LINE Bot初期化
app = FastAPI()
session = aiohttp.ClientSession()
async_http_client = AiohttpAsyncHttpClient(session)
line_bot_api = AsyncLineBotApi(channel_access_token, async_http_client)
parser = WebhookParser(channel_secret)

@app.get("/")
async def root():
    return {"message": "Hello from Chakkie Bot!"}

@app.post("/callback")
async def handle_callback(request: Request):
    body = await request.body()
    body_text = body.decode()
    signature = request.headers.get('X-Line-Signature', '')

    try:
        events = parser.parse(body_text, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        if not isinstance(event, MessageEvent):
            continue
        if not isinstance(event.message, TextMessage):
            continue

        user_text = event.message.text.lower()
        should_reply = "チャッキー" in user_text or random.random() < 0.3

        if should_reply:
            long_mode = is_long_mode(user_text)
            result = call_openai_chat_api(event.message.text, long_mode=long_mode)
            await line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=result)
            )

    return 'OK'
