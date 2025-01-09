# search_retry.py

from typing import List, Dict, Any, Callable
from datetime import datetime

class SearchRetryStrategy:
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.min_score_thresholds = [0.3, 0.2, 0.1]  # 各試行でのスコア閾値
        self.min_results = 3  # 最小期待結果数

    async def execute_search_with_retry(
        self,
        search_func: Callable,
        keyword_generator: Any,
        channel_id: str,
        query: str
    ) -> List[Dict[str, Any]]:
        """
        検索を実行し、結果が不十分な場合は再試行
        
        Args:
            search_func: 検索を実行する関数
            keyword_generator: キーワード生成器
            channel_id: 検索対象のチャンネルID
            query: 検索クエリ
            
        Returns:
            List[Dict[str, Any]]: 検索結果
        """
        all_results = []
        seen_messages = set()
        retry_count = 0

        while retry_count < self.max_retries:
            start_time = datetime.now()
            print(f"\n[試行 {retry_count + 1}/{self.max_retries}]")
            
            # キーワード生成（リトライ回数に基づいて単語も含める）
            search_terms = await keyword_generator.generate_search_terms(
                query=query,
                retry_count=retry_count
            )

            if not search_terms:
                print("- キーワード生成に失敗しました")
                break

            # 検索実行
            current_results = await search_func(
                channel_id=channel_id,
                search_terms=search_terms
            )

            # 結果の重複除去
            new_results = []
            for msg in current_results:
                msg_text = msg.get('text', '').strip()
                if msg_text and msg_text not in seen_messages:
                    new_results.append(msg)
                    seen_messages.add(msg_text)

            all_results.extend(new_results)

            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            print(f"- 新規検索結果数: {len(new_results)}")
            print(f"- 累積検索結果数: {len(all_results)}")
            print(f"- 処理時間: {processing_time:.2f}秒")

            # 十分な結果が得られた場合は終了
            if len(all_results) >= self.min_results:
                print("- 十分な結果が得られました")
                break

            # 次の試行に向けてスコア閾値を下げる
            retry_count += 1
            if retry_count < len(self.min_score_thresholds):
                print(f"- スコア閾値を {self.min_score_thresholds[retry_count]} に下げて再試行します")

        return all_results