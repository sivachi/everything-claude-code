from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Protocol
from dataclasses import dataclass, field
import pandas as pd
from datetime import datetime
from enum import Enum
import japanize_matplotlib # 可視化なら必須

@dataclass
class AnalysisTarget:
    """分析対象を表す汎用クラス"""
    name: str
    identifier: str
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FeedbackType:
    """フィードバックタイプを定義するクラス"""
    id: str
    display_name: str
    description: str
    prompt_context: str


@dataclass
class Category:
    """カテゴリーを定義するクラス"""
    id: str
    name: str
    description: Optional[str] = None


@dataclass
class CategorySchema:
    """カテゴリースキーマを定義するクラス"""
    feedback_type: FeedbackType
    categories: List[Category]
    prompt_template: str


@dataclass
class ColumnMapping:
    """データソースの列マッピングを定義"""
    feedback_type_columns: Dict[str, str]  # feedback_type_id -> column_name
    metadata_columns: List[str]
    target_identifier_column: Optional[str] = None


@dataclass
class ProcessingResult:
    """処理結果を格納するデータクラス"""
    matched_categories: List[Category]
    confidence: float
    reasoning: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class ContentValidator(Protocol):
    """コンテンツ検証のプロトコル"""
    def is_valid(self, content: str) -> bool:
        ...


class AIProvider(ABC):
    """AI プロバイダーの抽象基底クラス"""
    
    @abstractmethod
    def analyze(
        self, 
        content: str, 
        schema: CategorySchema,
        context: Optional[Dict[str, Any]] = None
    ) -> ProcessingResult:
        """コンテンツを分析してカテゴリーに分類する"""
        pass


class DataSource(ABC):
    """データソースの抽象基底クラス"""
    
    @abstractmethod
    def fetch(self, source_config: Dict[str, Any]) -> pd.DataFrame:
        """データソースからデータを取得"""
        pass
    
    @abstractmethod
    def get_target_info(self, source_config: Dict[str, Any]) -> AnalysisTarget:
        """分析対象の情報を取得"""
        pass


class ResultHandler(ABC):
    """結果ハンドラーの抽象基底クラス"""
    
    @abstractmethod
    def handle(
        self,
        results: pd.DataFrame,
        metadata: Dict[str, Any],
        schemas: List[CategorySchema]
    ) -> Any:
        """処理結果を扱う"""
        pass


class StandardContentValidator:
    """標準的なコンテンツバリデーター"""
    
    def __init__(self, invalid_values: Optional[List[str]] = None):
        self.invalid_values = invalid_values or ['', 'nan', 'None', 'null', 'N/A']
    
    def is_valid(self, content: str) -> bool:
        content = str(content).strip()
        return bool(content) and content not in self.invalid_values


class FeedbackAnalyzer:
    """フィードバック分析を行う汎用クラス"""
    
    def __init__(
        self,
        ai_provider: AIProvider,
        content_validator: Optional[ContentValidator] = None
    ):
        self.ai_provider = ai_provider
        self.content_validator = content_validator or StandardContentValidator()
        self.schemas: List[CategorySchema] = []
    
    def register_schema(self, schema: CategorySchema):
        """カテゴリースキーマを登録"""
        self.schemas.append(schema)
    
    def analyze_batch(
        self,
        data_source: DataSource,
        source_configs: List[Dict[str, Any]],
        column_mapping: ColumnMapping,
        result_handler: ResultHandler,
        batch_context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        バッチ分析を実行
        
        Args:
            data_source: データソース
            source_configs: ソース設定のリスト
            column_mapping: 列マッピング
            result_handler: 結果ハンドラー
            batch_context: バッチ全体のコンテキスト
        """
        all_results = []
        metadata = {
            'start_time': datetime.now(),
            'total_sources': len(source_configs),
            'processed_records': 0,
            'analysis_context': batch_context or {}
        }
        
        for config in source_configs:
            try:
                # データ取得
                df = data_source.fetch(config)
                target_info = data_source.get_target_info(config)
                
                # 各レコードを処理
                for _, row in df.iterrows():
                    result_row = self._process_record(
                        row, 
                        target_info, 
                        column_mapping,
                        context=batch_context
                    )
                    all_results.append(result_row)
                    metadata['processed_records'] += 1
                    
            except Exception as e:
                print(f"Error processing source {config}: {str(e)}")
                continue
        
        metadata['end_time'] = datetime.now()
        metadata['duration'] = (metadata['end_time'] - metadata['start_time']).total_seconds()
        
        # 結果をDataFrameに変換
        results_df = pd.DataFrame(all_results)
        
        # カテゴリー統計を計算
        metadata['category_statistics'] = self._calculate_statistics(results_df)
        
        # 結果を処理
        return result_handler.handle(results_df, metadata, self.schemas)
    
    def _process_record(
        self,
        row: pd.Series,
        target: AnalysisTarget,
        mapping: ColumnMapping,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """単一レコードを処理"""
        result = {
            'target_name': target.name,
            'target_id': target.identifier
        }
        
        # メタデータを追加
        for col in mapping.metadata_columns:
            if col in row.index:
                result[col] = row[col]
        
        # 各スキーマに対して処理
        for schema in self.schemas:
            feedback_type_id = schema.feedback_type.id
            
            if feedback_type_id in mapping.feedback_type_columns:
                column_name = mapping.feedback_type_columns[feedback_type_id]
                
                if column_name in row.index:
                    content = str(row[column_name]).strip()
                    
                    if self.content_validator.is_valid(content):
                        # AI分析を実行
                        analysis_result = self.ai_provider.analyze(
                            content, 
                            schema,
                            context=context
                        )
                        
                        # カテゴリーごとにバイナリ値を設定
                        for category in schema.categories:
                            col_name = f"{feedback_type_id}_{category.id}"
                            is_matched = any(
                                c.id == category.id 
                                for c in analysis_result.matched_categories
                            )
                            result[col_name] = 1 if is_matched else 0
                        
                        # 信頼度とコンテンツを保存
                        result[f"{feedback_type_id}_confidence"] = analysis_result.confidence
                        result[f"{feedback_type_id}_content"] = content
                    else:
                        # 無効なコンテンツの場合
                        for category in schema.categories:
                            col_name = f"{feedback_type_id}_{category.id}"
                            result[col_name] = 0
                        result[f"{feedback_type_id}_confidence"] = 0.0
                        result[f"{feedback_type_id}_content"] = content
        
        return result
    
    def _calculate_statistics(self, results_df: pd.DataFrame) -> Dict[str, Any]:
        """統計情報を計算"""
        stats = {}
        
        for schema in self.schemas:
            feedback_type_id = schema.feedback_type.id
            type_stats = {
                'total_responses': 0,
                'category_counts': {},
                'average_confidence': 0.0
            }
            
            # 有効な応答数をカウント
            confidence_col = f"{feedback_type_id}_confidence"
            if confidence_col in results_df.columns:
                valid_responses = results_df[results_df[confidence_col] > 0]
                type_stats['total_responses'] = len(valid_responses)
                
                if len(valid_responses) > 0:
                    type_stats['average_confidence'] = valid_responses[confidence_col].mean()
            
            # カテゴリーごとの集計
            for category in schema.categories:
                col_name = f"{feedback_type_id}_{category.id}"
                if col_name in results_df.columns:
                    count = results_df[col_name].sum()
                    type_stats['category_counts'][category.name] = count
            
            stats[schema.feedback_type.display_name] = type_stats
        
        return stats


# 実装例

class OpenAIProvider(AIProvider):
    """OpenAI APIを使用するプロバイダーの実装例"""
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", delay: float = 0.1):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.delay = delay
    
    def analyze(
        self,
        content: str,
        schema: CategorySchema,
        context: Optional[Dict[str, Any]] = None
    ) -> ProcessingResult:
        import json
        import time
        
        # カテゴリーリストを生成
        categories_text = "\n".join([
            f"{i+1}. {cat.name}" + (f" - {cat.description}" if cat.description else "")
            for i, cat in enumerate(schema.categories)
        ])
        
        # プロンプトを構築
        prompt = schema.prompt_template.format(
            feedback_type=schema.feedback_type.display_name,
            prompt_context=schema.feedback_type.prompt_context,
            categories=categories_text,
            content=content
        )
        
        try:
            response = self.client.chat.completions.create(
                response_format={"type": "json_object"},
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an AI assistant that analyzes and categorizes content. Always respond with valid JSON."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            
            result = json.loads(response.choices[0].message.content)
            time.sleep(self.delay)  # Rate limiting
            
            # カテゴリーIDをCategoryオブジェクトに変換
            matched_categories = []
            for cat_name in result.get('categories', []):
                for category in schema.categories:
                    if category.name == cat_name:
                        matched_categories.append(category)
                        break
            
            return ProcessingResult(
                matched_categories=matched_categories,
                confidence=result.get('confidence', 0.0),
                reasoning=result.get('reason', ''),
                metadata={'raw_response': result}
            )
            
        except Exception as e:
            return ProcessingResult(
                matched_categories=[],
                confidence=0.0,
                reasoning=f"Error: {str(e)}"
            )


class CSVDataSource(DataSource):
    """CSVファイルからデータを取得するデータソース"""
    
    def fetch(self, source_config: Dict[str, Any]) -> pd.DataFrame:
        file_path = source_config['file_path']
        encoding = source_config.get('encoding', 'utf-8')
        return pd.read_csv(file_path, encoding=encoding)
    
    def get_target_info(self, source_config: Dict[str, Any]) -> AnalysisTarget:
        import os
        file_path = source_config['file_path']
        target_name = source_config.get('target_name', os.path.basename(file_path))
        target_id = source_config.get('target_id', target_name.replace('.csv', ''))
        
        return AnalysisTarget(
            name=target_name,
            identifier=target_id,
            attributes=source_config.get('attributes', {})
        )


class MultiFormatResultHandler(ResultHandler):
    """複数形式で結果を出力するハンドラー"""
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        import os
        os.makedirs(output_dir, exist_ok=True)
    
    def handle(
        self,
        results: pd.DataFrame,
        metadata: Dict[str, Any],
        schemas: List[CategorySchema]
    ) -> Dict[str, str]:
        import os
        import json
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        outputs = {}
        
        # CSV出力
        csv_file = os.path.join(self.output_dir, f"analysis_results_{timestamp}.csv")
        results.to_csv(csv_file, index=False, encoding='utf-8-sig')
        outputs['csv'] = csv_file
        
        # JSON出力（メタデータ含む）
        json_file = os.path.join(self.output_dir, f"analysis_metadata_{timestamp}.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump({
                'metadata': {
                    'start_time': metadata['start_time'].isoformat(),
                    'end_time': metadata['end_time'].isoformat(),
                    'duration_seconds': metadata['duration'],
                    'total_sources': metadata['total_sources'],
                    'processed_records': metadata['processed_records']
                },
                'statistics': metadata['category_statistics'],
                'schemas': [
                    {
                        'feedback_type': {
                            'id': schema.feedback_type.id,
                            'name': schema.feedback_type.display_name
                        },
                        'categories': [
                            {'id': cat.id, 'name': cat.name}
                            for cat in schema.categories
                        ]
                    }
                    for schema in schemas
                ]
            }, f, ensure_ascii=False, indent=2)
        outputs['json'] = json_file
        
        # サマリーレポート出力
        report_file = os.path.join(self.output_dir, f"analysis_report_{timestamp}.txt")
        self._generate_report(report_file, metadata, schemas)
        outputs['report'] = report_file
        
        return outputs
    
    def _generate_report(
        self,
        file_path: str,
        metadata: Dict[str, Any],
        schemas: List[CategorySchema]
    ):
        """テキスト形式のレポートを生成"""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("分析レポート\n")
            f.write("=" * 60 + "\n\n")
            
            f.write(f"処理開始: {metadata['start_time'].strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"処理終了: {metadata['end_time'].strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"処理時間: {metadata['duration']:.2f}秒\n")
            f.write(f"処理件数: {metadata['processed_records']}件\n\n")
            
            for feedback_type_name, stats in metadata['category_statistics'].items():
                f.write(f"\n【{feedback_type_name}】\n")
                f.write("-" * 50 + "\n")
                f.write(f"有効回答数: {stats['total_responses']}件\n")
                f.write(f"平均信頼度: {stats['average_confidence']:.2%}\n\n")
                
                f.write("カテゴリー別集計:\n")
                for category_name, count in stats['category_counts'].items():
                    percentage = (count / stats['total_responses'] * 100) if stats['total_responses'] > 0 else 0
                    f.write(f"  {category_name:<30} {count:>6}件 ({percentage:>5.1f}%)\n")


# 使用例
def create_course_feedback_analyzer():
    """講座フィードバック分析の設定例"""
    
    # フィードバックタイプの定義
    positive_feedback = FeedbackType(
        id="positive",
        display_name="良かった点",
        description="サービスの良かった点に関するフィードバック",
        prompt_context="サービスの良い面や価値ある点"
    )
    
    improvement_feedback = FeedbackType(
        id="improvement",
        display_name="改善点",
        description="サービスの改善すべき点に関するフィードバック",
        prompt_context="サービスの改善が必要な面や課題"
    )
    
    # カテゴリーの定義
    positive_categories = [

        Category("practical", "実践的・実用的", "実務への適用可能性"),
        Category("basics", "基礎知識・入門対応", "初心者への配慮"),
        Category("other", "その他", "上記以外の良い点")
    ]
    
    improvement_categories = [
        Category("practice_lack", "実践・演習不足", "ハンズオンの不足"),
        Category("ui", "UI・操作性", "システムの使いやすさ"),
        Category("other", "その他", "上記以外の改善点")
    ]
    
    # プロンプトテンプレート
    prompt_template = """
    以下の{feedback_type}に関するフィードバックを分析し、該当するカテゴリーに分類してください。
    
    分析の観点: {prompt_context}
    
    カテゴリー:
    {categories}
    
    フィードバック内容:
    {content}
    
    以下のJSON形式で回答してください:
    {{
        "categories": ["該当するカテゴリー名のリスト（複数可）"],
        "confidence": 0.0～1.0の数値（判定の確信度）,
        "reason": "分類の理由（簡潔に）"
    }}
    """
    
    # スキーマの作成
    positive_schema = CategorySchema(
        feedback_type=positive_feedback,
        categories=positive_categories,
        prompt_template=prompt_template
    )
    
    improvement_schema = CategorySchema(
        feedback_type=improvement_feedback,
        categories=improvement_categories,
        prompt_template=prompt_template
    )
    
    return [positive_schema, improvement_schema]


def main():
    """メイン処理の例"""
    from dotenv import load_dotenv
    import os
    import glob
    
    # 環境設定
    load_dotenv()
    api_key = os.getenv('OPENAI_API_KEY')
    
    # コンポーネントの初期化
    ai_provider = OpenAIProvider(api_key)
    analyzer = FeedbackAnalyzer(ai_provider)
    
    # スキーマの登録（講座フィードバックの例）
    schemas = create_course_feedback_analyzer()
    for schema in schemas:
        analyzer.register_schema(schema)
    
    # データソースとハンドラーの準備
    data_source = CSVDataSource()
    result_handler = MultiFormatResultHandler("output")
    
    # ソース設定（CSVファイルのリスト）
    csv_files = glob.glob("data/*_DB.csv")
    source_configs = [
        {
            'file_path': file_path,
            'target_name': os.path.basename(file_path).replace('_DB.csv', ''),
            'attributes': {'type': 'course', 'format': 'online'}
        }
        for file_path in csv_files
    ]
    
    # 列マッピング
    column_mapping = ColumnMapping(
        feedback_type_columns={
            'positive': 'この講座の良かった点があれば自由に記入してください',
            'improvement': 'この講座の改善してほしい点があれば自由に記入してください'
        },
        metadata_columns=['お名前', 'メールアドレス', 'タイムスタンプ']
    )
    
    # 分析の実行
    output_files = analyzer.analyze_batch(
        data_source=data_source,
        source_configs=source_configs,
        column_mapping=column_mapping,
        result_handler=result_handler,
        batch_context={'analysis_type': 'course_feedback', 'version': '1.0'}
    )
    
    print(f"分析完了: {output_files}")


if __name__ == "__main__":
    main()