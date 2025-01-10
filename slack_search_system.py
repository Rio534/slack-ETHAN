# slack_search_system.py

from typing import List, Dict, Any, Set
from dataclasses import dataclass
from datetime import datetime
import google.generativeai as genai
from slack_sdk import WebClient

from config import Config
from question_splitter import QuestionSplitter
from search_keyword_generator import SearchKeywordGenerator
from answer_generator import AnswerGenerator
from utils import clean_slack_message
from search_retry import SearchRetryStrategy

@dataclass
class SearchResult:
    message: Dict[str, Any]
    matched_keywords: Set[str]
    relevance_score: float

class SlackSearchSystem:
    def __init__(self, min_relevance_score: float = 0.3):
        """SlackSearchSystemの初期化"""
        Config.validate()
        
        self.gemini_api_key = Config.GEMINI_API_KEY
        self.slack_token = Config.SLACK_USER_TOKEN
        self.min_relevance_score = min_relevance_score
        
        genai.configure(api_key=self.gemini_api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        self.slack_client = WebClient(token=self.slack_token)
        
        self.keyword_generator = SearchKeywordGenerator(self.model)
        self.question_splitter = QuestionSplitter(self.model)
        self.answer_generator = AnswerGenerator(self.model)
        self.retry_strategy = SearchRetryStrategy()

    def _find_keyword_matches(self,
                            messages: List[Dict[str, Any]],
                            search_terms: List[str]) -> List[SearchResult]:
        """キーワードマッチによる候補抽出"""
        results = []
        seen_messages = set()
        
        for msg in messages:
            text = msg.get('text', '').strip().lower()
            if not text or text in seen_messages:
                continue
                
            matched_keywords = set()
            
            # 各検索キーワードとのマッチをチェック
            for term in search_terms:
                # キーワードを分割（termは文字列として直接処理）
                keywords = set(term.lower().split())
                
                # 各キーワードの部分一致をチェック
                for keyword in keywords:
                    if keyword in text:
                        matched_keywords.add(keyword)
            
            # 1つ以上のキーワードにマッチした場合のみ追加
            if matched_keywords:
                results.append(SearchResult(
                    message=msg,
                    matched_keywords=matched_keywords,
                    relevance_score=0.0  # この時点では未評価
                ))
                seen_messages.add(text)
        
        return results

    def _evaluate_relevance(self,
                           results: List[SearchResult],
                           original_query: str) -> List[SearchResult]:
        """元のクエリとの関連性を評価"""
        query_words = set(original_query.lower().split())
        
        for result in results:
            text = result.message.get('text', '').strip().lower()
            score = 0.0
            
            # 1. キーワードマッチの数によるスコア
            keyword_score = len(result.matched_keywords) / len(query_words)
            score += keyword_score * 0.6
            
            # 2. 文の構造的な類似性
            if any(word in text for word in query_words):
                score += 0.4
            
            result.relevance_score = min(score, 1.0)
            
        return results

    def _filter_results(self, 
                       results: List[SearchResult]) -> List[SearchResult]:
        """結果の並び替えと絞り込み"""
        # スコアとキーワードマッチ数で並び替え
        sorted_results = sorted(
            results,
            key=lambda x: (
                len(x.matched_keywords),  # キーワードマッチ数
                x.relevance_score  # 関連性スコア
            ),
            reverse=True
        )
        
        # 最低スコア未満の結果を除外
        filtered_results = [
            result for result in sorted_results 
            if result.relevance_score >= self.min_relevance_score
        ]
        
        return filtered_results

    def _print_debug_info(self,
                         messages: List[Dict[str, Any]],
                         keyword_matches: List[SearchResult],
                         filtered_results: List[SearchResult]):
        """デバッグ情報の出力"""
        print("\n=== 検索結果サマリー ===")
        print(f"取得メッセージ数: {len(messages)}")
        print(f"キーワードマッチ数: {len(keyword_matches)}")
        print(f"最終結果数: {len(filtered_results)}")
        
        if filtered_results:
            print("\n選択されたメッセージ:")
            for i, result in enumerate(filtered_results, 1):
                text = result.message.get('text', '')[:100] + '...'
                print(f"\n{i}. スコア: {result.relevance_score:.2f}")
                print(f"マッチしたキーワード: {', '.join(result.matched_keywords)}")
                print(f"メッセージ: {text}")
        
        print("=" * 60)

    async def search_messages(self, 
                            channel_id: str,
                            search_terms: List[str],
                            query: str = "") -> List[Dict[str, Any]]:
        """メッセージを検索"""
        try:
            response = self.slack_client.conversations_history(
                channel=channel_id,
                limit=1000
            )
            messages = response.get("messages", [])
            
            # 第1段階：キーワードマッチによる候補抽出
            keyword_matches = self._find_keyword_matches(messages, search_terms)
            
            if not keyword_matches:
                return []
                
            # 第2段階：元のクエリとの関連性評価
            scored_results = self._evaluate_relevance(
                keyword_matches,
                query or search_terms[0]  # queryが空の場合は最初の検索語を使用
            )
            
            # 結果の並び替えと絞り込み
            filtered_results = self._filter_results(scored_results)
            
            # デバッグ情報の出力
            self._print_debug_info(messages, keyword_matches, filtered_results)
            
            return [result.message for result in filtered_results]
            
        except Exception as e:
            print(f"\n[エラー] 検索エラー: {str(e)}")
            return []

    async def process_query(self, 
                          query: str, 
                          channel_id: str) -> str:
        """クエリの処理メインメソッド"""
        start_time = datetime.now()
        
        try:
            print("\n=== 検索処理開始 ===")
            print(f"検索クエリ: {query}")
            print("=" * 60)

            # 質問の分割
            questions = await self.question_splitter.split_questions(query)
            all_answers = []
            
            for question in questions:
                print(f"\n--- 質問の処理: {question} ---")
                
                # SearchRetryStrategyを使用して検索を実行
                search_results = await self.retry_strategy.execute_search_with_retry(
                    search_func=self.search_messages,
                    keyword_generator=self.keyword_generator,
                    channel_id=channel_id,
                    query=question
                )

                if search_results:
                    # LLMを使用してサマリーを生成
                    answer, quality = await self.answer_generator.generate_answer(
                        question,
                        search_results
                    )
                else:
                    answer = "関連する情報が見つかりませんでした。"

                all_answers.append({
                    'question': question,
                    'answer': answer
                })
            
            # 最終的な回答を生成
            if len(all_answers) == 1:
                final_answer = all_answers[0]['answer']
            else:
                final_answer = "複数の質問への回答:\n\n" + "\n\n".join(
                    f"質問{i+1}: {ans['question']}\n{ans['answer']}"
                    for i, ans in enumerate(all_answers)
                )

            print("\n=== 最終回答 ===")
            print(final_answer)
            print("=" * 60)
            
            # 処理時間の計算と表示
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            print(f"\n[検索完了] 処理時間: {processing_time:.2f}秒")
            print("-" * 60)
            
            return final_answer
            
        except Exception as e:
            error_msg = f"検索処理中にエラーが発生しました: {str(e)}"
            print(f"\n[エラー] {error_msg}")
            return error_msg