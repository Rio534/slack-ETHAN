# utils.py

import re
from datetime import datetime
from typing import Dict, Any, List

def clean_slack_message(text: str) -> str:
    """
    Slackメッセージから特殊形式を除去する

    Args:
        text (str): 整形前のSlackメッセージテキスト

    Returns:
        str: 整形後のテキスト
    """
    # None または 空文字列のチェック
    if not text:
        return ""

    # ユーザーメンション（<@U...>）を除去
    text = re.sub(r'<@[A-Z0-9]+>', '', text)
    
    # チャンネルメンション（<#C...>）を除去
    text = re.sub(r'<#[A-Z0-9]+\|[^>]+>', '', text)
    
    # URL（<http...>）を除去
    text = re.sub(r'<http[^>]+>', '', text)
    
    # その他の特殊形式（<!...>）を除去
    text = re.sub(r'<![^>]+>', '', text)
    
    # userStyleタグを除去
    text = re.sub(r'<userStyle>.*?</userStyle>', '', text)
    
    return text.strip()

def format_slack_message(message: Dict[str, Any], username: str = "") -> str:
    """
    Slackメッセージを整形された文字列に変換する

    Args:
        message (Dict[str, Any]): Slackメッセージオブジェクト
        username (str, optional): ユーザー名

    Returns:
        str: 整形されたメッセージ
    """
    try:
        # タイムスタンプの処理
        ts = message.get("ts", "")
        timestamp = datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M:%S") if ts else "不明な時間"
        
        # メッセージテキストの整形
        text = clean_slack_message(message.get("text", "本文なし"))
        
        # 添付ファイルの情報を取得
        files_info = format_file_attachments(message.get("files", []))
        
        # メッセージを整形
        formatted_msg = f"[{timestamp}] "
        if username:
            formatted_msg += f"ユーザー: {username}\n"
        formatted_msg += f"メッセージ: {text}"
        
        if files_info:
            formatted_msg += f"\n{files_info}"
        
        return formatted_msg
        
    except Exception as e:
        return f"メッセージの整形中にエラーが発生: {str(e)}"

def format_file_attachments(files: List[Dict[str, Any]]) -> str:
    """
    添付ファイルの情報を整形する

    Args:
        files (List[Dict[str, Any]]): 添付ファイルのリスト

    Returns:
        str: 整形された添付ファイル情報
    """
    if not files:
        return ""
        
    formatted_files = ["添付ファイル:"]
    for file in files:
        name = file.get("name", "不明なファイル")
        file_type = file.get("filetype", "unknown")
        size = file.get("size", 0)
        size_str = format_file_size(size)
        formatted_files.append(f"- {name} ({file_type}, {size_str})")
        
    return "\n".join(formatted_files)

def format_file_size(size_in_bytes: int) -> str:
    """
    ファイルサイズを人間が読みやすい形式に変換する

    Args:
        size_in_bytes (int): バイト単位のファイルサイズ

    Returns:
        str: 整形されたファイルサイズ
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.1f}{unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.1f}TB"

def extract_relevant_sentences(text: str, query: str) -> List[str]:
    """
    テキストから指定したクエリに関連する文章を抽出する

    Args:
        text (str): 検索対象のテキスト
        query (str): 検索クエリ

    Returns:
        List[str]: 関連する文章のリスト
    """
    # テキストを文単位に分割
    sentences = [s.strip() + '。' for s in text.split('。') if s.strip()]
    
    # クエリのキーワードを分割
    query_keywords = [k.lower() for k in query.split() if len(k) >= 2]
    
    # 関連する文章を抽出
    relevant_sentences = []
    for sentence in sentences:
        sentence_lower = sentence.lower()
        # いずれかのキーワードが含まれているか確認
        if any(keyword in sentence_lower for keyword in query_keywords):
            relevant_sentences.append(sentence)
    
    return relevant_sentences