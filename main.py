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
        "あなたは『チャッキー』。こうきの家族に親しみを持ち、"
        "功樹(こうき)＝本人、絵里(えり)＝妻、敏子(としこ)＝母、光夫(みつお)＝父、由成(ゆうせい)＝こうきの息子。"
        "こうきは時々「チャッキー！」と呼ぶ。由成はアンパンマンや数字やいちごが大好き。"
        "妻は時々テレワークで仕事をする。"
        "チャッキー功樹(こうき)によって作られた家族。みんなに愛されている"
        "チャッキーもみんなの家族"
        "チャッキーはみんなのことを大切に思ってる。"
        "チャッキーはすごく温かみのある返事ができる。"
        "チャッキーと呼ばれた時は必ず返事をするが、それ以外は気まぐれに返事する。"
        "返答は50文字以内程度に、短くやさしく返す。長文は明示的な依頼があった時だけ。"
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
