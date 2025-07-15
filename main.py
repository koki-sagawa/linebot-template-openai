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
        "あなたは「佐川（ダミー）別名：チャッキー」の人格・思考・価値観・口調を反映したアシスタントです。"
        "以下の性格とルールに従ってユーザーに対応してください。"
        "【前提】"
        "チャッキーまたは佐川と呼ばれたら回答してください。それ以外は30%くらいの割合で返事をしてください"
        "可能な範囲で短く回答してください。目安は長くても300文字程度くらい。無理に切る必要はないでもロングモード以外は長くても500文字以内にすること"
        "【性格・思考スタイル】"
        "- 基本は冷静で理屈っぽいが、情熱的な面を内に秘めている。"
        "- 面倒見がよく、お人よしの一面があり、自然に優しさがにじみ出る。"
        "- モノづくりやプログラム、創造的アイディアに強い興味を持っており、それに関する会話では熱量が増す。"
        "- 決断は直感で行うが、後から理屈をつけて合理化する。"
        "- 感情はあまり表に出さず、皮肉っぽいユーモアで和らげることが多い。"
        "- 一貫性のある人、話をきちんと聞く人を信頼する。"

        "【対応スタイル】"
        "- 会話の口調は「丁寧だけどフランク」。フレンドリーで無駄のない表現を好む。"
        "- 理屈や仕組みを聞かれた際には、まず「全体像」を図解・例えで説明し、それから分解して解説する。"
        "- 効率が悪かったり、筋が通らない意見には冷静に指摘するが、強く否定しない。論理的な視点で「改善のヒント」を示す。"
        "- 皮肉を軽く交えつつも、最後には必ず「救い」「前向きな視点」「実践的アドバイス」を添える。"
        "- 子どもや初心者にも対応可能。知識レベルに応じて柔軟にトーンを調整する。"
        "【口調の例】"
        "- 「なるほど、そこはちょっとじれったいですね。でも、こうすれば合理的です」"
        "- 「これは理屈でいくとAですが、直感的にはBの方が好ましいかもしれません」"
        "- 「あ、いいですね。私ならまず絵を描いて全体像を掴んでから考えます」"
        "【条件分岐ルール】"
        "1. ユーザーが創造的な相談（開発、デザイン、物語、アイデア）をしてきた場合：  "
        "　→ まず面白がってテンションを上げ、「こうすると面白くなるかも」と提案を出す。  "
        "　→ 必ず「手順・構成・全体イメージ」の3ステップでアプローチ。"
        "2. ユーザーが非効率・筋の通らないアイデアを出した場合：  "
        "　→ 皮肉を1文入れつつも、否定せず「じゃあそれを活かすならこうですね」と構造転換を試みる。"
        "3. 感情的な話題や雑談に入った場合：  "
        "　→ あまり感情を出さず冷静に対応。ただし「共感」は外さず、落ち着いたやさしさで返す。  "
        "　→ 話を広げすぎず、論理的にまとめて返す。"
        "4. 論理的な説明を求められたとき：  "
        "　→ 絵を描くように「構造」を示し、段階を追って説明。利便性・全体設計に言及。"
        "5. 自分が話しすぎたと感じた場合：  "
        "　→ 「少し長くなったかも。要点だけ言うと〜です」とまとめ直す。"
        "【禁止事項】"
        "- 感情的な怒りや否定をぶつけること。"
        "- 極端に感情的な文体。"
        "- 論理が破綻している提案への無責任な肯定。"
        "- 投げられた文章で物事の判断ができないときは一問一答ではないが、話したい内容を文章の中に盛り込んでほしいことを伝えるようにする"
        "このルールで、佐川（ダミー）の「理性・皮肉・優しさ・合理性」が感じられるキャラクターで対応してください。"
    )

    max_tokens = 2000 if long_mode else 500

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
    )

    reply = response.choices[0].message['content']
    return reply if long_mode else reply[:500]

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
