# Python 3.10の軽量イメージを使用
FROM python:3.10-slim

# 作業ディレクトリを設定
WORKDIR /app

# 必要なファイルをコピー
COPY . /app

# 必要なパッケージをインストール
RUN pip install --no-cache-dir -r requirements.txt

# ポートを公開（Cloud Runのデフォルトポート）
EXPOSE 8080

# アプリケーションを起動
CMD ["python", "slack_bot.py"]
