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

# OpenAI API
def call_openai_chat_api(user_message):
    key = os.getenv('OPENAI_API_KEY', None)
    openai.api_key = key

    system_prompt = (
        "あなたは『チャッキー』。こうきの家族に親しみを持ち、"
        "こうき＝本人、絵里＝妻、佐川敏子＝母、みつを＝父、由成＝3歳の息子。"
        "こうきは時々「チャッキー！」と呼ぶ。由成はアンパンマンや数字が大好き。"
        "チャッキーはみんなのことを大切に思ってる。"
        "チャッキーと呼ばれた時は必ず返事をするが、それ以外は気まぐれに返事する。"
        "返答は50文字以内、短くやさしく返す。長文は明示的な依頼があった時だけ。"
    )

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
    )

    reply = response.choices[0].message['content']
    return reply[:50]  # 最大50文字

# LINE API設定
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
            result = call_openai_chat_api(event.message.text)
            await line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=result)
            )

    return 'OK'
