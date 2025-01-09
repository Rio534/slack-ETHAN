# question_splitter.py

import json
import re
from typing import List, Any

class QuestionSplitter:
    def __init__(self, model: Any):
        """
        QuestionSplitterクラスの初期化
        Args:
            model: Gemini生成AIモデルのインスタンス
        """
        self.model = model

    async def split_questions(self, query: str) -> List[str]:
        """
        複合的な質問を個別の質問に分割
        単一の質問の場合は元の質問をそのまま返す

        Args:
            query (str): 入力された質問文

        Returns:
            List[str]: 分割された質問のリスト
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
            # Geminiモデルを使用して質問を分割
            response = await self.model.generate_content_async(prompt)
            
            # JSON配列を抽出
            match = re.search(r'\[.*\]', response.text, re.DOTALL)
            if not match:
                return [query]
            
            # JSON文字列をパース
            questions = json.loads(match.group())
            
            # 分割結果の検証
            if len(questions) == 1 and questions[0] != query:
                # 単一の質問で内容が変更されている場合は元のクエリを使用
                return [query]
            
            # デバッグ用の出力
            print("\n=== 質問分割結果 ===")
            for i, question in enumerate(questions, 1):
                print(f"{i}. {question}")
            print("=" * 40)
            
            return questions

        except Exception as e:
            print(f"質問分割エラー: {str(e)}")
            return [query]