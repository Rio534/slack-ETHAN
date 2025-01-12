import os
import re
import asyncio
from datetime import datetime
from typing import Dict, Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request
import uvicorn

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler

from slack_search_system import SlackSearchSystem

# 環境変数の読み込み
load_dotenv()
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")

# Slack Boltアプリケーションの初期化
app = AsyncApp(
    token=SLACK_BOT_TOKEN,
    signing_secret=SLACK_SIGNING_SECRET,
)

# 検索システムの初期化
search_system = SlackSearchSystem()

async def post_message_in_chunks(say, text: str, thread_ts: str, chunk_size: int = 3000):
    """
    長いメッセージを分割して投稿する
    """
    if len(text) <= chunk_size:
        await say(text=text, thread_ts=thread_ts)
        return

    chunks = []
    current_chunk = []
    current_size = 0

    for line in text.split('\n'):
        line_size = len(line) + 1  # +1 for newline
        if current_size + line_size > chunk_size:
            chunks.append('\n'.join(current_chunk))
            current_chunk = [line]
            current_size = line_size
        else:
            current_chunk.append(line)
            current_size += line_size

    if current_chunk:
        chunks.append('\n'.join(current_chunk))

    for i, chunk in enumerate(chunks, 1):
        prefix = f"(Part {i}/{len(chunks)})\n" if len(chunks) > 1 else ""
        await say(text=prefix + chunk, thread_ts=thread_ts)
        # Slack API制限を考慮した待機
        await asyncio.sleep(1)

async def process_mention(body: Dict[str, Any], say) -> None:
    """
    メンションされたメッセージを処理する
    """
    event = body["event"]
    thread_ts = event.get("thread_ts", event.get("ts"))
    
    # メンションを除去してクエリを抽出
    query = re.sub(r'<@[A-Z0-9]+>', '', event.get("text")).strip()
    
    if not query:
        await say(
            text="検索クエリを入力してください。例: @検索ボット 先月の会議について",
            thread_ts=thread_ts
        )
        return

    try:
        # 処理開始メッセージを送信
        await say(
            text="検索を開始します...",
            thread_ts=thread_ts
        )

        # 検索処理の実行
        results = await search_system.process_query(
            query=query,
            channel_id=event["channel"]
        )

        # 結果を分割して投稿
        await post_message_in_chunks(say, results, thread_ts)

    except Exception as e:
        error_message = f"検索処理中にエラーが発生しました: {str(e)}"
        await say(text=error_message, thread_ts=thread_ts)

@app.event("app_mention")
async def handle_mention(body: Dict[str, Any], logger):
    """
    メンションイベントを処理する
    """
    try:
        logger.info("メンションを受信しました！")
        logger.info(f"受信内容: {body}")

        event = body["event"]
        thread_ts = event.get("thread_ts", event.get("ts"))

        # メンションを除去してクエリを抽出
        query = re.sub(r'<@[A-Z0-9]+>', '', event.get("text")).strip()

        if not query:
            await app.client.chat_postMessage(
                channel=event["channel"],
                thread_ts=thread_ts,
                text="検索クエリを入力してください。例: @検索ボット 先月の会議について"
            )
            return

        # 処理開始メッセージを送信
        await app.client.chat_postMessage(
            channel=event["channel"],
            thread_ts=thread_ts,
            text="検索を開始します..."
        )

        # 検索処理の実行
        results = await search_system.process_query(
            query=query,
            channel_id=event["channel"]
        )

        # 結果を投稿 (シンプルに一度で投稿)
        await app.client.chat_postMessage(
            channel=event["channel"],
            thread_ts=thread_ts,
            text=results
        )

    except Exception as e:
        logger.error(f"エラーが発生しました: {str(e)}")
        await app.client.chat_postMessage(
            channel=event["channel"],
            thread_ts=thread_ts,
            text=f"検索処理中にエラーが発生しました: {str(e)}"
        )

# FastAPI アプリを作成し、slack_bolt のリクエストハンドラを紐づける
api = FastAPI()
handler = AsyncSlackRequestHandler(app)

@api.post("/slack/events")
async def slack_events(req: Request):
    """
    Slackからのイベントを受け付けるエンドポイント
    """
    return await handler.handle(req)

# Cloud Run のエントリーポイント
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(api, host="0.0.0.0", port=port)
