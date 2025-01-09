# config.py

import os
from dotenv import load_dotenv
from typing import List

class Config:
    # 環境変数の読み込み
    load_dotenv()
    
    # 必須の環境変数
    SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
    SLACK_USER_TOKEN = os.getenv("SLACK_USER_TOKEN")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    
    # オプションの環境変数
    DEFAULT_CHANNEL = os.getenv("DEFAULT_CHANNEL", "general")
    MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", "100"))
    DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"

    @classmethod
    def validate(cls) -> None:
        """
        必要な環境変数が設定されているかを確認
        設定されていない場合は例外を発生させる
        """
        missing_vars: List[str] = []
        
        # 必須の環境変数をチェック
        if not cls.SLACK_USER_TOKEN:
            missing_vars.append("SLACK_USER_TOKEN")
        if not cls.SLACK_BOT_TOKEN:
            missing_vars.append("SLACK_BOT_TOKEN")
        if not cls.GEMINI_API_KEY:
            missing_vars.append("GEMINI_API_KEY")
            
        if missing_vars:
            raise ValueError(
                "必要な環境変数が設定されていません:\n" +
                "\n".join([f"- {var}" for var in missing_vars])
            )
            
    @classmethod
    def print_debug_info(cls) -> None:
        """
        デバッグ情報を出力
        本番環境ではトークン情報は表示しない
        """
        if cls.DEBUG_MODE:
            print("=== 設定情報 ===")
            print(f"DEFAULT_CHANNEL: {cls.DEFAULT_CHANNEL}")
            print(f"MAX_SEARCH_RESULTS: {cls.MAX_SEARCH_RESULTS}")
            print(f"DEBUG_MODE: {cls.DEBUG_MODE}")
            print("================")