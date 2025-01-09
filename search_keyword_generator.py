# search_keyword_generator.py

from typing import List, Any
import re
import json

class SearchKeywordGenerator:
    def __init__(self, model: Any = None):
        """SearchKeywordGeneratorの初期化"""
        self.model = model
        
        # 除外する語句リスト
        self.stop_words = {
            'する', 'てる', 'いる', 'ある', 'なる',
            'どこ', 'なに', 'だれ', 'いつ', 'どう',
            'こと', 'もの', 'ところ', 'とき', 'ため',
            'どれ', 'これ', 'それ', 'あれ', 'この',
            'その', 'あの', 'どの',
            'お願い', 'ください', 'おねがい', 'です', 'ます',
            'か', 'の', 'は'
        }

        # 同義語辞書
        self.synonyms = {
            '新入社員': {'新人', 'フレッシャーズ'},
            'スケジュール': {'日程', '予定', '計画', 'スケ'},
            '会議': {'ミーティング', '打ち合わせ', '打合せ'},
            '報告': {'レポート', '報告書', 'レポーティング'},
            '資料': {'ドキュメント', '書類', 'データ'},
            '売上': {'売り上げ', '売上高', '売上金額'},
            '研修': {'トレーニング', '講習', '研修会'},
            'キャンセル': {'解約', '返品', '取消'},
            '顧客': {'取引先', 'お客様', 'クライアント', '得意先'},
            '商品': {'製品', '品物', 'アイテム'},
            '納期': {'出荷日', '配送日', '出荷予定日'},
            '在庫': {'在庫数', 'ストック', '在庫状況'},
            '担当者': {'担当', '責任者', 'PIC'}
        }

    async def generate_search_terms(self, 
                                  query: str,
                                  retry_count: int = 0) -> List[str]:
        """
        検索キーワードを生成
        
        Args:
            query: 検索クエリ
            retry_count: 再試行回数（使用しないが互換性のために維持）
            
        Returns:
            生成されたキーワードのリスト
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
        
        5. Keyword guidelines:
           - Keep terms short and precise
           - Break down long phrases into shorter combinations
           - Prioritize nouns and verbs
           - Avoid long sentences or phrases

        Return the keywords in the following format:
        ```json
        ["keyword1", "keyword2", "keyword3", ...]
        ```
        """
            
        try:
            response = await self.model.generate_content_async(prompt)
            # 余分な空白や改行を削除し、JSON配列のみを抽出
            cleaned_response = response.text.strip()
            
            # JSON文字列を抽出するための正規表現
            json_pattern = r'\[.*?\]'
            json_match = re.search(json_pattern, cleaned_response, re.DOTALL)
            
            if not json_match:
                print("JSONデータが見つかりませんでした")
                return []
                
            json_str = json_match.group()
            
            # JSON配列を解析
            keywords = json.loads(json_str)
            
            if not keywords:
                return []
                
            # デバッグ情報の出力
            print("\n=== 生成された検索キーワード ===")
            print(f"元のクエリ: {query}")
            print(f"生成されたキーワード:")
            for kw in keywords:
                print(f"- {kw}")
            print("=" * 40)
            
            return keywords
            
        except Exception as e:
            print(f"キーワード生成エラー: {str(e)}")
            print(f"生成されたレスポンス: {response.text if 'response' in locals() else 'レスポンスなし'}")
            # エラー発生時はバックアップとして単語抽出による方法を使用
            words = self._extract_words(query)
            return self._generate_keyword_combinations(words)

    def _extract_words(self, text: str) -> List[str]:
        """
        テキストから意味のある単語を抽出
        
        Args:
            text: 入力テキスト
            
        Returns:
            抽出された単語のリスト
        """
        # 記号を除去し、単語に分割
        words = re.findall(r'[一-龯々ぁ-んァ-ン\w]+', text)
        
        # ストップワードを除去
        words = [w for w in words if w.lower() not in self.stop_words]
        
        # 同義語を追加
        expanded_words = set(words)
        for word in words:
            for key, synonyms in self.synonyms.items():
                if word in synonyms or word == key:
                    expanded_words.add(key)
                    expanded_words.update(synonyms)
        
        return list(expanded_words)

    def _generate_keyword_combinations(self, words: List[str]) -> List[str]:
        """
        単語の組み合わせからキーワードを生成
        
        Args:
            words: 単語のリスト
            
        Returns:
            生成されたキーワードのリスト
        """
        keywords = []
        used_combinations = set()
        
        # 2語の組み合わせを生成
        for i, word1 in enumerate(words):
            # 単語を単体でも使用
            if word1 not in used_combinations:
                keywords.append(word1)
                used_combinations.add(word1)
            
            for word2 in words[i+1:]:
                # 順序を考慮した組み合わせ
                combo1 = f"{word1} {word2}"
                combo2 = f"{word2} {word1}"
                
                if combo1 not in used_combinations:
                    keywords.append(combo1)
                    used_combinations.add(combo1)
                
                if combo2 not in used_combinations:
                    keywords.append(combo2)
                    used_combinations.add(combo2)
        
        return keywords