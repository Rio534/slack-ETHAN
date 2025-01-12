# ベースイメージ
FROM python:3.10-slim

# 作業ディレクトリの設定
WORKDIR /app

# 必要なファイルをコピー
COPY requirements.txt . 
COPY . .

# 必要な依存関係をインストール
RUN pip install --no-cache-dir -r requirements.txt

# Cloud Run が必要とするポートの公開
EXPOSE 8080

# アプリケーションの起動コマンド
CMD ["python", "slack_bot.py"]
