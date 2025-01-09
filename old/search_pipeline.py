import os
from dotenv import load_dotenv
import google.generativeai as genai
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import json
from datetime import datetime, timedelta
import re
import asyncio
from typing import List, Dict, Any, Optional
import calendar

# 既存のインポート文に追加
from config import Config
from utils import clean_slack_message, format_slack_message


class DateExtractor:
    def __init__(self):
        self.relative_date_patterns = {
            r'先月': self._get_last_month_range,
            r'先々月': self._get_two_months_ago_range,
            r'今月': self._get_current_month_range,
            r'来月': self._get_next_month_range,
            r'昨日': self._get_yesterday_range,
            r'今日': self._get_today_range,
            r'明日': self._get_tomorrow_range
        }
        
        # 具体的な日付パターン（例：8月27日、2024年3月1日）
        self.specific_date_pattern = r'(\d{4}年)?(\d{1,2})月(\d{1,2})日'
        
    def extract_date_range(self, query: str) -> tuple:
        """
        クエリから日付範囲を抽出する
        戻り値: (start_date, end_date) - YYYY-MM-DD形式の文字列のタプル
        """
        # 相対的な日付表現のチェック
        for pattern, handler in self.relative_date_patterns.items():
            if re.search(pattern, query):
                return handler()
        
        # 具体的な日付のチェック
        match = re.search(self.specific_date_pattern, query)
        if match:
            year = match.group(1)[:-1] if match.group(1) else str(datetime.now().year)
            month = int(match.group(2))
            day = int(match.group(3))
            
            # 日付の妥当性チェック
            try:
                date = datetime(int(year), month, day)
                date_str = date.strftime('%Y-%m-%d')
                return date_str, date_str
            except ValueError:
                return None, None
        
        return None, None
    
    def _get_last_month_range(self) -> tuple:
        """先月の日付範囲を取得"""
        today = datetime.now()
        first_day = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        last_day = today.replace(day=1) - timedelta(days=1)
        return first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')
    
    def _get_two_months_ago_range(self) -> tuple:
        """先々月の日付範囲を取得"""
        today = datetime.now()
        first_day = (today.replace(day=1) - timedelta(days=32)).replace(day=1)
        last_day = (today.replace(day=1) - timedelta(days=1)).replace(day=1) - timedelta(days=1)
        return first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')
    
    def _get_current_month_range(self) -> tuple:
        """今月の日付範囲を取得"""
        today = datetime.now()
        first_day = today.replace(day=1)
        last_day = today.replace(day=calendar.monthrange(today.year, today.month)[1])
        return first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')
    
    def _get_next_month_range(self) -> tuple:
        """来月の日付範囲を取得"""
        today = datetime.now()
        if today.month == 12:
            first_day = today.replace(year=today.year + 1, month=1, day=1)
        else:
            first_day = today.replace(month=today.month + 1, day=1)
        last_day = (first_day.replace(month=first_day.month % 12 + 1, day=1) - timedelta(days=1))
        return first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')
    
    def _get_yesterday_range(self) -> tuple:
        """昨日の日付範囲を取得"""
        yesterday = datetime.now() - timedelta(days=1)
        date_str = yesterday.strftime('%Y-%m-%d')
        return date_str, date_str
    
    def _get_today_range(self) -> tuple:
        """今日の日付範囲を取得"""
        date_str = datetime.now().strftime('%Y-%m-%d')
        return date_str, date_str
    
    def _get_tomorrow_range(self) -> tuple:
        """明日の日付範囲を取得"""
        tomorrow = datetime.now() + timedelta(days=1)
        date_str = tomorrow.strftime('%Y-%m-%d')
        return date_str, date_str

class QuestionSplitter:
    def __init__(self, model):
        self.model = model

    async def split_questions(self, query: str) -> List[str]:
        """
        複合的な質問を個別の質問に分割
        単一の質問の場合は元の質問をそのまま返す
        """
        prompt = f"""
        Input question: "{query}"

        Requirements:
        1. If the input contains multiple questions, split them into individual questions
        2. If the input is a single question, return it exactly as is without any modifications
        3. Do not paraphrase, summarize, or modify the original text
        4. Do not add or remove any words from the original questions
        5. Only split when there are clearly separate questions (e.g., marked by ？, 。, or conjunction words like また、そして、それから)

        Example input 1 (multiple questions): 
        "プロジェクトの進捗状況を教えて。また、次のミーティングはいつですか？"
        Expected output 1: ["プロジェクトの進捗状況を教えて。", "次のミーティングはいつですか？"]

        Example input 2 (single question):
        "プロジェクトの進捗状況を教えて"
        Expected output 2: ["プロジェクトの進捗状況を教えて"]

        Return only a JSON array of strings.
        """

        try:
            response = await self.model.generate_content_async(prompt)
            match = re.search(r'\[.*\]', response.text, re.DOTALL)
            if not match:
                return [query]
            
            questions = json.loads(match.group())
            
            # 分割結果の検証
            if len(questions) == 1 and questions[0] != query:
                # 単一の質問で内容が変更されている場合は元のクエリを使用
                return [query]
            
            print("\n=== 質問分割結果 ===")
            for i, question in enumerate(questions, 1):
                print(f"{i}. {question}")
            print("=" * 40)
            
            return questions

        except Exception as e:
            print(f"質問分割エラー: {str(e)}")
            return [query]

class SearchKeywordGenerator:
    def __init__(self, model):
        self.model = model

    async def generate_search_terms(self, query: str, 
                                  start_date: str = None, 
                                  end_date: str = None,
                                  user_id: str = None) -> list:
        """
        ユーザーのクエリから検索キーワードのバリエーションを生成
        """
        # 英語の検索クエリかどうかを判定
        is_english_query = bool(re.search(r'[a-zA-Z]', query))
        
        prompt = f"""
        Generate search keywords based on: "{query}"

        Requirements:
        1. Generate concise search terms (maximum 2-3 words per term)
        2. Focus on essential words and their combinations
        3. Consider the following variations:
           - Core keywords from the query
           - Similar meaning words (同義語)
           - Common abbreviations
           - Key noun-verb pairs
           {'- Include English variations' if is_english_query else '- Use only Japanese terms'}
        
        4. Generate **at least 15 search terms**
        
        5. Search operator combinations:
           {f'- Date range: after:{start_date}' if start_date else ''}
           {f'- Date range: before:{end_date}' if end_date else ''}
           {f'- User filter: from:<@{user_id}>' if user_id else ''}

        6. Keyword guidelines:
           - Keep terms short and precise
           - Break down long phrases into shorter combinations
           - Prioritize nouns and verbs
           - Avoid long sentences or phrases

        Example input: "新入社員の研修スケジュールについて"
        Example output: [
            "研修",
            "新入社員",
            "研修 スケジュール",
            "新人 研修",
            "研修 日程",
            "社員 研修",
            "研修 予定",
            "新入社員 研修",
            "after:2024-01-01 研修",
            "from:<@UXXXXXXXX> 研修",
            "研修内容",
            "研修資料",
            "研修 参加者",
            "研修 目的",
            "研修 プログラム",
            "研修 実施",
            "新人研修 スケジュール",
        ]

        Return only a JSON array of strings, without any explanation.
        Focus on short, effective keyword combinations.
        """

        try:
            response = await self.model.generate_content_async(prompt)
            match = re.search(r'\[.*\]', response.text, re.DOTALL)
            if not match:
                raise ValueError("Invalid response format")
            
            search_terms = json.loads(match.group())
            search_terms = list(set(term.strip() for term in search_terms if term.strip()))
            
            # 検索語の長さでソート（短い順）
            search_terms.sort(key=len)
            
            print("\n=== 生成された検索キーワード ===")
            for i, term in enumerate(search_terms, 1):
                print(f"{i}. {term}")
            print("=" * 40)
            
            return search_terms

        except Exception as e:
            print(f"検索キーワード生成エラー: {str(e)}")
            return [query]

class SlackSearchSystem:
    def __init__(self):
        # 設定ファイルから環境変数を読み込む
        Config.validate()  # 必要な環境変数が設定されているか確認
        
        self.gemini_api_key = Config.GEMINI_API_KEY
        self.slack_token = Config.SLACK_USER_TOKEN
        
        genai.configure(api_key=self.gemini_api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        self.slack_client = WebClient(token=self.slack_token)
        
        self.keyword_generator = SearchKeywordGenerator(self.model)
        self.question_splitter = QuestionSplitter(self.model)

    async def search_messages(self, channel_id: str, search_terms: List[str]) -> List[Dict[str, Any]]:
        """
        生成された検索クエリを使用してSlackメッセージを検索
        """
        all_results = []
        seen_timestamps = set()

        for query in search_terms:
            try:
                print(f"\n--- '{query}' での検索を開始 ---")
                
                # 検索クエリにスペースが含まれている場合、そのままSlack APIに渡す
                response = self.slack_client.search_messages(
                    query=query,
                    count=100
                )
                
                messages = response.get("messages", {}).get("matches", [])
                print(f"検索クエリ '{query}' で {len(messages)} 件のメッセージを取得")
                
                matches_count = 0
                for msg in messages:
                    if msg.get("ts") in seen_timestamps:
                        continue
                        
                    # チャンネルIDが一致する場合のみ処理
                    if msg.get("channel", {}).get("id") != channel_id:
                        continue

                    text = clean_slack_message(msg.get("text", ""))
                    # 日付モディファイアを含むクエリの場合は、キーワードのみで関連性をチェック
                    search_query = query.split(" after:")[0].split(" before:")[0].split(" from:<@")[0].strip()
                    relevant_sentences = self._extract_relevant_sentences(text, search_query)
                    
                    if relevant_sentences:
                        matches_count += 1
                        seen_timestamps.add(msg.get("ts"))
                        print(f"マッチしたメッセージ {matches_count}: {' '.join(relevant_sentences)[:100]}...")
                        
                        user_info = self._get_user_info(msg.get("user", ""))
                        
                        formatted_msg = {
                            "timestamp": float(msg.get("ts", 0)),
                            "datetime": datetime.fromtimestamp(float(msg.get("ts", 0))),
                            "user": user_info,
                            "text": text,
                            "matched_query": query,
                            "relevant_sentences": relevant_sentences,
                            "has_files": "files" in msg,
                            "files": self._extract_file_info(msg.get("files", [])),
                            "links": self._extract_links(text)
                        }
                        
                        all_results.append(formatted_msg)
                
                print(f"クエリ '{query}' で {matches_count} 件のマッチを検出")
                        
            except SlackApiError as e:
                print(f"Slack API エラー: {e.response['error']}")
                continue

        all_results.sort(key=lambda x: x["timestamp"], reverse=True)
        
        print("\n=== 検索結果の要約 ===")
        print(f"総マッチ数: {len(all_results)} 件")
        print(f"ユニークなクエリ数: {len(set(r['matched_query'] for r in all_results))} 件")
        print("=" * 40)
        
        return all_results
    
    def _extract_relevant_sentences(self, text: str, query: str) -> List[str]:
        """
        テキストから関連する文章を抽出する
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

    def _get_user_info(self, user_id: str) -> Dict[str, str]:
        """ユーザー情報の取得"""
        try:
            response = self.slack_client.users_info(user=user_id)
            user = response["user"]
            return {
                "id": user_id,
                "name": user.get("real_name", "Unknown User"),
                "display_name": user.get("profile", {}).get("display_name", "")
            }
        except SlackApiError:
            return {
                "id": user_id,
                "name": "Unknown User",
                "display_name": ""
            }

    def _extract_file_info(self, files: List[Dict]) -> List[Dict[str, str]]:
        """添付ファイル情報の抽出"""
        file_info = []
        for file in files:
            file_info.append({
                "name": file.get("name", "Unknown File"),
                "type": file.get("filetype", "unknown"),
                "size": file.get("size", 0)
            })
        return file_info

    def _extract_links(self, text: str) -> List[str]:
        """メッセージ内のリンクを抽出"""
        return re.findall(r'<(https?://[^>]+)>', text)

    async def generate_answer(self, original_query: str, results: List[Dict[str, Any]]) -> str:
        """検索結果から質問に対する回答を生成"""
        if not results:
            return "申し訳ありません。関連する情報が見つかりませんでした。"

        # 関連する文章のみを使用してコンテキストを作成
        context_sentences = []
        for result in results:
            for sentence in result['relevant_sentences']:
                context_sentences.append({
                    'query': result['matched_query'],
                    'sentence': sentence,
                    'datetime': result['datetime'].strftime('%Y-%m-%d %H:%M')
                })

        # コンテキストの整形
        context = "\n".join([
            f"[{item['datetime']}] {item['sentence']}"
            for item in context_sentences
        ])

        prompt = f"""
        以下の質問と検索結果に基づいて回答を生成してください。

        質問: {original_query}

        検索結果:
        {context}

        要件:
        1. 検索結果の情報のみを使用して、質問に直接答えてください
        2. 日時情報が含まれている場合は、それを明確に示してください
        3. 見つかった具体的な情報（予定、タスク、状態など）を含めてください
        4. 簡潔に回答してください
        5. 情報が見つからない場合は「関連する情報が見つかりませんでした」と答えてください
        6. 日付や時間に関する情報は、できるだけ正確に記載してください

        回答例:
        質問: 2023/3/23のタスクは何でしたか？
        回答: 3月23日の予定として、翌日からの京都タスクの詳細が共有されました。具体的には、24日17:00-19:00にエスラボ本社からダイセル材を茶室に運び、その後造形を開始する予定でした。

        回答:"""

        try:
            print("\n回答生成を開始...")
            response = await self.model.generate_content_async(prompt)
            print("回答生成が完了しました")
            return response.text.strip()
        except Exception as e:
            print(f"回答生成エラー: {str(e)}")
            return "回答の生成中にエラーが発生しました。"

    async def process_query(self, query: str, channel_id: str, 
                          start_date: Optional[str] = None, 
                          end_date: Optional[str] = None,
                          user_id: Optional[str] = None) -> str:
        """
        Slackボットから呼び出されるメイン処理メソッド
        """
        try:
            # 質問を個別の質問に分割
            questions = await self.question_splitter.split_questions(query)
            
            all_answers = []
            
            for question in questions:
                # 検索キーワードの生成
                search_terms = await self.keyword_generator.generate_search_terms(
                    query=question,
                    start_date=start_date,
                    end_date=end_date,
                    user_id=user_id
                )
                
                # 検索の実行
                results = await self.search_messages(channel_id, search_terms)
                
                # 回答の生成
                answer = await self.generate_answer(question, results)
                
                all_answers.append({
                    'question': question,
                    'answer': answer,
                    'results': results
                })
            
            # 結果をSlack用にフォーマット
            return self.format_combined_results(query, all_answers)
            
        except Exception as e:
            return f"検索処理中にエラーが発生しました: {str(e)}"

    def format_combined_results(self, original_query: str, all_answers: List[Dict]) -> str:
        """複数の質問に対する回答を統合してフォーマット"""
        formatted_output = f"\n元の質問: {original_query}\n\n"
        formatted_output += "回答:\n"
        
        # 各質問の回答を箇条書きで表示
        for answer_info in all_answers:
            formatted_output += f"- {answer_info['answer']}\n"
        
        formatted_output += "\n" + "=" * 60 + "\n"
        formatted_output += "詳細な検索結果:\n"
        formatted_output += "=" * 60 + "\n"

        # 各質問の詳細な検索結果を表示
        for answer_info in all_answers:
            formatted_output += f"\n[質問: {answer_info['question']}]\n"
            formatted_output += "-" * 40 + "\n"
            
            if not answer_info['results']:
                formatted_output += "検索結果が見つかりませんでした。\n"
                continue

            for result in answer_info['results']:
                formatted_output += f"[{result['datetime'].strftime('%Y-%m-%d %H:%M')}] "
                formatted_output += f"{result['user']['name']}"
                if result['user']['display_name']:
                    formatted_output += f" (@{result['user']['display_name']})"
                formatted_output += f"\nマッチしたクエリ: {result['matched_query']}\n"
                
                formatted_output += "関連する文章:\n"
                for sentence in result['relevant_sentences']:
                    formatted_output += f"- {sentence}\n"

                if result['has_files']:
                    formatted_output += "添付ファイル:\n"
                    for file in result['files']:
                        formatted_output += f"- {file['name']} ({file['type']})\n"

                formatted_output += "-" * 40 + "\n"

        return formatted_output