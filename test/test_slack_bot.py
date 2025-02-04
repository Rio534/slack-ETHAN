import sys
import os
from fastapi.testclient import TestClient

# slack_bot.py のあるディレクトリをパスに追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from slack_bot import api  # 修正: slack_bot を明示的にインポート

client = TestClient(api)

def test_slack_events():
    """SlackのURL検証イベントが正しく処理されるかテスト"""
    test_data = {
        "type": "url_verification",
        "challenge": "test_challenge"
    }
    response = client.post("/slack/events", json=test_data)
    assert response.status_code == 200
    assert response.json() == {"challenge": "test_challenge"}
