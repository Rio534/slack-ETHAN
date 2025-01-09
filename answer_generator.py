# answer_generator.py

from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
import re
import json
from dataclasses import dataclass, asdict

@dataclass
class AnswerQuality:
    has_direct_answer: bool = False
    has_specific_info: bool = False
    has_time_info: bool = False
    is_relevant: bool = False
    confidence_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class AnswerGenerator:
    def __init__(self, model: Any):
        """
        AnswerGeneratorの初期化
        
        Args:
            model: Gemini生成AIモデルのインスタンス
        """
        self.model = model
        self.answer_cache = {}  # キャッシュの初期化
        
        # 質問タイプのパターン
        self.question_patterns = {
            'location': [r'どこ', r'場所', r'どの辺', r'どちら'],
            'time': [r'いつ', r'何時', r'時間'],
            'who': [r'だれ', r'誰', r'何人'],
            'what': [r'なに', r'何', r'どんな'],
            'how': [r'どうやって', r'どのように', r'どうすれば'],
            'why': [r'なぜ', r'どうして', r'理由']
        }

    def _identify_question_type(self, query: str) -> str:
        """
        質問のタイプを特定
        """
        for qtype, patterns in self.question_patterns.items():
            if any(re.search(pattern, query) for pattern in patterns):
                return qtype
        return 'general'

    def _extract_time_info(self, message: Dict[str, Any]) -> str:
        """メッセージから時間情報を抽出"""
        try:
            timestamp = float(message.get('ts', 0))
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime('%Y年%m月%d日 %H:%M')
        except Exception as e:
            print(f"時間情報の抽出エラー: {str(e)}")
            return "不明な時刻"

    async def generate_answer(self, 
                            query: str,
                            messages: List[Dict[str, Any]],
                            max_retries: int = 2) -> Tuple[str, AnswerQuality]:
        """回答を生成"""
        if not messages:
            return "申し訳ありません。関連する情報が見つかりませんでした。", AnswerQuality()

        # キャッシュキーの生成
        cache_key = f"{query}_{messages[0].get('ts',0) if messages else 'no_messages'}"
        
        # キャッシュチェック
        if cache_key in self.answer_cache:
            cached_answer, cached_quality = self.answer_cache[cache_key]
            print("キャッシュされた回答を使用")
            return cached_answer, cached_quality

        best_answer = ""
        best_quality = AnswerQuality()
        
        # 質問タイプの特定
        question_type = self._identify_question_type(query)
        
        for attempt in range(max_retries):
            try:
                # コンテキストの準備
                context = []
                for msg in messages:
                    time_info = self._extract_time_info(msg)
                    text = msg.get('text', '').strip()
                    if text:
                        context.append(f"[{time_info}] {text}")

                context_text = "\n".join(context)
                
                # 質問タイプに応じたプロンプトの生成
                prompt = self._generate_prompt(query, context_text, question_type)

                # 回答の生成
                response = await self.model.generate_content_async(prompt)
                current_answer = response.text.strip()
                
                # 回答の品質評価
                current_quality = await self._evaluate_answer_quality(
                    current_answer, 
                    query,
                    question_type
                )
                
                # より良い回答が得られた場合は更新
                if current_quality.confidence_score > best_quality.confidence_score:
                    best_answer = current_answer
                    best_quality = current_quality
                    
                # 十分な品質が得られた場合は終了
                if current_quality.confidence_score >= 0.8: # 閾値を0.8に上げる
                    break
                    
            except Exception as e:
                print(f"回答生成エラー（試行 {attempt + 1}）: {str(e)}")
                continue

        # 最低限の回答を保証
        if not best_answer and messages:
            best_answer = self._generate_fallback_answer(messages, query, question_type)
            best_quality = AnswerQuality(
                has_direct_answer=True,
                has_specific_info=True,
                has_time_info=True,
                is_relevant=True,
                confidence_score=0.6
            )

        # 結果をキャッシュ
        if best_answer:
            self.answer_cache[cache_key] = (best_answer, best_quality)
            
        # デバッグ情報の出力
        print("\n=== 回答生成結果 ===")
        print(f"質問タイプ: {question_type}")
        print(f"生成された回答:")
        print(best_answer)
        print("\n品質評価:")
        for key, value in best_quality.to_dict().items():
            print(f"- {key}: {value}")
        print("=" * 60)

        return best_answer, best_quality

    def _generate_prompt(self, query: str, context_text: str, question_type: str) -> str:
        """
        質問タイプに応じたプロンプトを生成
        """
        base_prompt = f"""
        質問: {query}

        以下の情報を元に、質問に対する回答を生成してください：

        {context_text}
        """

        # 質問タイプに応じた追加要件
        type_specific_requirements = {
            'location': """
            回答の要件:
            1. 場所に関する情報を明確に示す
            2. 「〜で」「〜にて」などの場所を示す表現を含める
            3. 可能であれば場所の詳細な状況も説明
            4. 不確かな場合はその旨を明記
            """,
            'time': """
            回答の要件:
            1. 時間情報を具体的に示す
            2. 日時の前後関係を明確に
            3. 継続時間や期間も記載（該当する場合）
            """,
            'who': """
            回答の要件:
            1. 人物を具体的に特定
            2. 役割や立場も含める
            3. 関係する人物の情報も記載
            """,
            'what': """
            回答の要件:
            1. 対象を具体的に説明
            2. 特徴や性質を記載
            3. 関連する情報も含める
            """,
            'how': """
            回答の要件:
            1. 手順や方法を具体的に説明
            2. 順序立てて記載
            3. 重要なポイントを強調
            """,
            'why': """
            回答の要件:
            1. 理由や原因を具体的に説明
            2. 背景情報も含める
            3. 論理的な繋がりを示す
            """,
            'general': """
            回答の要件:
            1. 質問の意図に沿った情報を提供
            2. 具体的な事実を中心に説明
            3. 関連する重要情報も含める
            """
        }

        # 共通の要件
        common_requirements = """
        フォーマット:
        [送信] YYYY年MM月DD日 HH:MM
        
        内容：
        （ここに回答の本文）

        補足：
        （必要な場合のみ補足情報を記載）
        """

        return base_prompt + type_specific_requirements.get(question_type, type_specific_requirements['general']) + common_requirements

    def _generate_fallback_answer(self, 
                                messages: List[Dict[str, Any]], 
                                query: str,
                                question_type: str) -> str:
        """
        最低限の回答を生成
        """
        # 最新のメッセージを使用
        latest_message = messages[0]
        time_info = self._extract_time_info(latest_message)
        text = latest_message.get('text', '').strip()
        
        # 回答を生成する
        return f"""[送信] {time_info}

内容：
{text}

補足：
この情報は、入力された質問に最も関連性の高いものとして検出されました。"""


    async def _evaluate_answer_quality(self,
                                     answer: str,
                                     query: str,
                                     question_type: str) -> AnswerQuality:
        """
        質問タイプを考慮して回答の品質を評価
        """
        prompt = f"""
        Evaluate the quality of this answer for a {question_type} question:
        Question: {query}
        Answer: {answer}

        Consider the question type '{question_type}' when evaluating.
        Return a JSON object with the following boolean properties:
        - has_direct_answer: Does it directly address the {question_type} aspect?
        - has_specific_info: Does it contain specific details?
        - has_time_info: Does it include temporal information?
        - is_relevant: Is it relevant to the question?
        - confidence_score: A float between 0 and 1 indicating confidence

        Return only the JSON object, no explanation.
        """

        try:
            response = await self.model.generate_content_async(prompt)
            
            # JSON文字列を抽出
            match = re.search(r'{.*}', response.text, re.DOTALL)
            if not match:
                print(f"JSON形式のレスポンスが不正です: {response.text}")
                return AnswerQuality()
            
            quality_dict = json.loads(match.group()) # 抽出したJSON文字列をパース
            return AnswerQuality(**quality_dict)
            
        except Exception as e:
            print(f"回答品質評価エラー: {str(e)}")
            return AnswerQuality()