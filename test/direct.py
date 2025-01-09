# direct.py
# メンションを付けなくても直接質問ができるインタラクティブな検索システム

import os
import sys
from dotenv import load_dotenv
import asyncio
from datetime import datetime
import signal
from typing import Optional

# プロジェクトルートディレクトリを検索パスに追加
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)

from slack_search_system import SlackSearchSystem
from config import Config

class InteractiveSearchSystem:
    def __init__(self):
        """検索システムの初期化"""
        # 環境変数の読み込み
        load_dotenv()
        
        # 設定の検証
        Config.validate()
        
        # 検索システムの初期化
        self.search_system = SlackSearchSystem()
        
        # シグナルハンドラの設定
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum: int, frame: Optional[object]) -> None:
        """
        Ctrl+C などのシグナルをハンドリング
        """
        print("\n\nプログラムを終了します...")
        sys.exit(0)

    async def start(self, channel_id: str) -> None:
        """
        インタラクティブな検索を開始
        
        Args:
            channel_id (str): 検索対象のチャンネルID
        """
        try:
            print("\n=== Slack検索システム ===")
            print("• 終了するには 'exit'/'quit' と入力するか、Ctrl+C を押してください")
            print("• 'help' でコマンド一覧を表示します")
            print("=" * 60)

            while True:
                try:
                    # プロンプトの表示
                    query = input("\n検索したい内容を入力してください: ").strip()
                    
                    # コマンドの処理
                    if not self._handle_command(query):
                        continue

                    # 空の入力をチェック
                    if not query:
                        print("検索クエリを入力してください")
                        continue

                    # 検索実行
                    print("\n検索を開始します...")
                    start_time = datetime.now()
                    
                    results = await self.search_system.process_query(
                        query=query,
                        channel_id=channel_id
                    )
                    
                    # 検索時間の計算
                    search_time = (datetime.now() - start_time).total_seconds()
                    
                    # 結果の出力
                    print(f"\n[検索完了] 処理時間: {search_time:.2f}秒")
                    print("-" * 60)
                    print(results)

                except EOFError:
                    # Ctrl+D が押された場合
                    print("\nプログラムを終了します...")
                    break
                    
        except Exception as e:
            print(f"\n[エラー] 予期しないエラーが発生しました: {str(e)}")
            if Config.DEBUG_MODE:
                raise

    def _handle_command(self, command: str) -> bool:
        """
        特殊コマンドの処理
        
        Args:
            command (str): 入力されたコマンド
            
        Returns:
            bool: 通常の検索を続行する場合はTrue
        """
        # 終了コマンド
        if command.lower() in ['exit', 'quit']:
            print("\n検索を終了します")
            sys.exit(0)
            
        # ヘルプコマンド
        if command.lower() == 'help':
            self._show_help()
            return False
            
        # クリアコマンド
        if command.lower() in ['clear', 'cls']:
            os.system('cls' if os.name == 'nt' else 'clear')
            return False
            
        return True

    def _show_help(self) -> None:
        """ヘルプメッセージの表示"""
        help_text = """
=== コマンド一覧 ===
• exit, quit : プログラムを終了
• help      : このヘルプを表示
• clear, cls: 画面をクリア
• Ctrl+C    : プログラムを強制終了
• Ctrl+D    : プログラムを終了

=== 検索のヒント ===
• 日付指定: 「今月」「先月」「2024年3月」などの日付表現が使えます
• 複数の質問: 「プロジェクトの進捗を教えて。また、次のミーティングはいつ？」 
  のように、複数の質問を一度に行えます
• 具体的に: より具体的な質問をすることで、より正確な回答が得られます
        """
        print(help_text)

async def main():
    """メイン関数"""
    # 固定のチャンネルID
    CHANNEL_ID = os.getenv("DEFAULT_CHANNEL_ID", "C03M4V2FZ0V")
    
    try:
        search_system = InteractiveSearchSystem()
        await search_system.start(CHANNEL_ID)
        
    except Exception as e:
        print(f"\n[エラー] システムの初期化中にエラーが発生しました: {str(e)}")
        if Config.DEBUG_MODE:
            raise
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
