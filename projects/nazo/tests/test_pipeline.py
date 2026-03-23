#!/usr/bin/env python3
"""
test_pipeline.py — パイプライン全4スクリプトのテスト

テスト対象:
  1. 01_chunk.py: output/chunks.jsonl の構造・整合性チェック
  2. 02_classify.py: output/classified.jsonl のデータ検証（APIは叩かない）
  3. 03_output.py: classified.jsonl → カテゴリ別MD出力の実行＋形式チェック
  4. 04_shrine_messages.py: 神社メッセージMDの形式チェック
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from collections import Counter

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_DIR / "output"
CHUNKS_FILE = OUTPUT_DIR / "chunks.jsonl"
CLASSIFIED_FILE = OUTPUT_DIR / "classified.jsonl"
CATEGORY_OUTPUT_DIR = PROJECT_DIR / "output_md" / "カテゴリ別"
SHRINE_OUTPUT_DIR = PROJECT_DIR / "output_md" / "神社メッセージ"

# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def load_jsonl(filepath):
    """JSONLファイルを読み込んでリストで返す"""
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            records.append((i, json.loads(line)))
    return records


# ===========================================================================
# テスト1: 01_chunk.py — chunks.jsonl の検証
# ===========================================================================

class TestChunks:
    """output/chunks.jsonl の構造・整合性テスト"""

    @pytest.fixture(autouse=True)
    def load_chunks(self):
        assert CHUNKS_FILE.exists(), f"chunks.jsonl が存在しません: {CHUNKS_FILE}"
        self.records = load_jsonl(CHUNKS_FILE)
        assert len(self.records) > 0, "chunks.jsonl が空です"

    def test_each_line_is_valid_json(self):
        """各行が有効なJSONであること（load_jsonlで既に検証済み、念のため）"""
        # load_jsonl が json.loads で例外を出さなければOK
        assert len(self.records) > 0

    def test_required_fields_exist(self):
        """必須フィールド（chunk_id, source_file, source_type, text, char_count）が存在すること"""
        required = {"chunk_id", "source_file", "source_type", "text", "char_count"}
        for line_num, record in self.records:
            missing = required - set(record.keys())
            assert not missing, (
                f"行{line_num}: 必須フィールドが不足: {missing} (chunk_id={record.get('chunk_id', '?')})"
            )

    def test_char_count_is_correct(self):
        """char_count が text の実際の文字数と一致すること"""
        for line_num, record in self.records:
            actual_len = len(record["text"])
            assert record["char_count"] == actual_len, (
                f"行{line_num}: char_count不一致 "
                f"(記録={record['char_count']}, 実際={actual_len}, "
                f"chunk_id={record['chunk_id']})"
            )

    def test_chunk_id_unique(self):
        """chunk_id が重複していないこと"""
        ids = [record["chunk_id"] for _, record in self.records]
        counter = Counter(ids)
        duplicates = {k: v for k, v in counter.items() if v > 1}
        assert not duplicates, f"chunk_id が重複: {duplicates}"

    def test_text_not_empty(self):
        """text が空文字でないこと"""
        for line_num, record in self.records:
            assert record["text"].strip(), (
                f"行{line_num}: text が空です (chunk_id={record['chunk_id']})"
            )

    def test_char_count_positive(self):
        """char_count が正の整数であること"""
        for line_num, record in self.records:
            assert isinstance(record["char_count"], int) and record["char_count"] > 0, (
                f"行{line_num}: char_count が正でない: {record['char_count']}"
            )

    def test_total_chunks_reasonable(self):
        """チャンク総数が妥当な範囲であること（1件以上）"""
        assert len(self.records) >= 1, "チャンク数が0件です"


# ===========================================================================
# テスト2: 02_classify.py — classified.jsonl の検証（APIは叩かない）
# ===========================================================================

class TestClassified:
    """output/classified.jsonl のデータ検証テスト"""

    @pytest.fixture(autouse=True)
    def load_classified(self):
        assert CLASSIFIED_FILE.exists(), f"classified.jsonl が存在しません: {CLASSIFIED_FILE}"
        self.records = load_jsonl(CLASSIFIED_FILE)
        assert len(self.records) > 0, "classified.jsonl が空です"

    def test_each_line_is_valid_json(self):
        """各行が有効なJSONであること"""
        assert len(self.records) > 0

    def test_required_fields_exist(self):
        """必須フィールド（chunk_id, source_file, category_id, summary, is_spiritual, topic）が存在すること"""
        required = {"chunk_id", "source_file", "category_id", "summary", "is_spiritual", "topic"}
        for line_num, record in self.records:
            missing = required - set(record.keys())
            assert not missing, (
                f"行{line_num}: 必須フィールドが不足: {missing} (chunk_id={record.get('chunk_id', '?')})"
            )

    def test_category_id_format(self):
        """category_id の形式が正しいこと（X-X-X or "none" or "error"）"""
        valid_pattern = re.compile(r"^\d+-\d+(-\d+)?$")
        valid_special = {"none", "error", "unknown"}
        for line_num, record in self.records:
            cat_id = record["category_id"]
            assert valid_pattern.match(cat_id) or cat_id in valid_special, (
                f"行{line_num}: category_id の形式が不正: '{cat_id}' "
                f"(chunk_id={record['chunk_id']})"
            )

    def test_is_spiritual_is_boolean(self):
        """is_spiritual がブール型であること"""
        for line_num, record in self.records:
            assert isinstance(record["is_spiritual"], bool), (
                f"行{line_num}: is_spiritual がboolでない: {type(record['is_spiritual'])} "
                f"(chunk_id={record['chunk_id']})"
            )

    def test_summary_not_empty_for_spiritual(self):
        """スピリチュアル関連チャンクの summary が空でないこと"""
        for line_num, record in self.records:
            if record.get("is_spiritual") and record.get("category_id") not in ("none", "error"):
                assert record["summary"].strip(), (
                    f"行{line_num}: スピリチュアルなのに summary が空 "
                    f"(chunk_id={record['chunk_id']})"
                )

    def test_category_id_none_when_not_spiritual(self):
        """is_spiritual=false のとき category_id が 'none' であること"""
        for line_num, record in self.records:
            if not record.get("is_spiritual"):
                assert record["category_id"] in ("none", "error", "unknown"), (
                    f"行{line_num}: is_spiritual=false なのに category_id='{record['category_id']}' "
                    f"(chunk_id={record['chunk_id']})"
                )

    def test_chunk_id_unique(self):
        """chunk_id が重複していないこと"""
        ids = [record["chunk_id"] for _, record in self.records]
        counter = Counter(ids)
        duplicates = {k: v for k, v in counter.items() if v > 1}
        assert not duplicates, f"chunk_id が重複: {duplicates}"


# ===========================================================================
# テスト3: 03_output.py — カテゴリ別MD出力の実行＋形式チェック
# ===========================================================================

class TestCategoryOutput:
    """03_output.py の実行とカテゴリ別MD出力の形式テスト"""

    @pytest.fixture(autouse=True, scope="class")
    def run_output_script(self):
        """03_output.py を実行してカテゴリ別MDを生成"""
        assert CLASSIFIED_FILE.exists(), "classified.jsonl が必要です"
        result = subprocess.run(
            [sys.executable, str(PROJECT_DIR / "scripts" / "03_output.py")],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_DIR),
        )
        assert result.returncode == 0, (
            f"03_output.py の実行に失敗:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_category_dir_exists(self):
        """output_md/カテゴリ別/ ディレクトリが生成されること"""
        assert CATEGORY_OUTPUT_DIR.exists(), f"ディレクトリが存在しません: {CATEGORY_OUTPUT_DIR}"

    def test_md_files_generated(self):
        """カテゴリ別MDファイルが1つ以上生成されること"""
        md_files = list(CATEGORY_OUTPUT_DIR.glob("*.md"))
        assert len(md_files) >= 1, "カテゴリ別MDファイルが生成されていません"

    def test_md_files_start_with_title(self):
        """各MDファイルが # で始まるタイトルを持つこと"""
        md_files = list(CATEGORY_OUTPUT_DIR.glob("*.md"))
        for md_path in md_files:
            content = md_path.read_text(encoding="utf-8")
            lines = [l for l in content.split("\n") if l.strip()]
            assert lines, f"ファイルが空です: {md_path.name}"
            assert lines[0].startswith("# "), (
                f"{md_path.name}: 最初の行が '#' で始まっていません: '{lines[0][:50]}'"
            )

    def test_md_files_have_source_attribution(self):
        """カテゴリ別MDファイルに出典（**出典：**）が含まれること"""
        md_files = list(CATEGORY_OUTPUT_DIR.glob("*.md"))
        # 全カテゴリ統合.md を含めて少なくとも1ファイルに出典がある
        has_source = False
        for md_path in md_files:
            content = md_path.read_text(encoding="utf-8")
            if "**出典：**" in content:
                has_source = True
                break
        assert has_source, "どのカテゴリ別MDにも出典（**出典：**）が見つかりません"

    def test_category_files_have_correct_naming(self):
        """カテゴリ別ファイルが 数字_ で始まる命名規則であること（統合ファイル除く）"""
        md_files = list(CATEGORY_OUTPUT_DIR.glob("*.md"))
        numbered = [f for f in md_files if re.match(r"^\d+_", f.name)]
        # 少なくとも1つの番号付きファイルがあること
        assert len(numbered) >= 1, "番号付きカテゴリファイル（例: 1_存在.md）がありません"

    def test_integration_file_exists(self):
        """全カテゴリ統合.md が生成されること"""
        integration_file = CATEGORY_OUTPUT_DIR / "全カテゴリ統合.md"
        assert integration_file.exists(), "全カテゴリ統合.md が生成されていません"


# ===========================================================================
# テスト4: 04_shrine_messages.py — 神社メッセージMDの形式チェック
# ===========================================================================

class TestShrineMessages:
    """output_md/神社メッセージ/ の生成済みMDファイルの形式テスト"""

    @pytest.fixture(autouse=True)
    def load_shrine_files(self):
        assert SHRINE_OUTPUT_DIR.exists(), f"ディレクトリが存在しません: {SHRINE_OUTPUT_DIR}"
        self.md_files = list(SHRINE_OUTPUT_DIR.glob("*.md"))
        assert len(self.md_files) > 0, "神社メッセージMDファイルが見つかりません"

    def test_md_files_exist(self):
        """神社メッセージMDファイルが1つ以上存在すること"""
        assert len(self.md_files) >= 1

    def test_title_format(self):
        """各MDファイルが # で始まるタイトルを持つこと"""
        for md_path in self.md_files:
            content = md_path.read_text(encoding="utf-8")
            lines = [l for l in content.split("\n") if l.strip()]
            assert lines, f"ファイルが空です: {md_path.name}"
            assert lines[0].startswith("# "), (
                f"{md_path.name}: 最初の行が '#' で始まっていません: '{lines[0][:50]}'"
            )

    def test_has_shrine_tag(self):
        """タグ（神社）が付いていること"""
        for md_path in self.md_files:
            content = md_path.read_text(encoding="utf-8")
            assert "- 神社:" in content or "- 神社: " in content or "神社:" in content, (
                f"{md_path.name}: 神社タグが見つかりません"
            )

    def test_has_deity_or_shrine_tag(self):
        """タグ（神社または神様）がエントリ単位で付いていること"""
        for md_path in self.md_files:
            content = md_path.read_text(encoding="utf-8")
            # エントリ単位のタグ（イタリック内）
            assert re.search(r"\*神社:", content), (
                f"{md_path.name}: エントリ単位の神社タグ（*神社:...* 形式）が見つかりません"
            )

    def test_pii_mask_applied(self):
        """PIIマスク（[人物X]形式）が適用されていること"""
        pii_pattern = re.compile(r"\[人物[A-Z]+\]")
        found_any = False
        for md_path in self.md_files:
            content = md_path.read_text(encoding="utf-8")
            if pii_pattern.search(content):
                found_any = True
                break
        assert found_any, "どの神社メッセージMDにもPIIマスク（[人物X]形式）が見つかりません"

    def test_has_source_attribution(self):
        """出典（**出典：**）が含まれること"""
        for md_path in self.md_files:
            content = md_path.read_text(encoding="utf-8")
            assert "**出典：**" in content, (
                f"{md_path.name}: 出典（**出典：**）が見つかりません"
            )

    def test_no_raw_personal_names_in_mask_targets(self):
        """主要なマスク対象の生の人名が残っていないこと（サンプルチェック）"""
        # 一部の代表的な人名をチェック
        raw_names_to_check = ["美穂", "満美", "麻貴", "カレン"]
        for md_path in self.md_files:
            content = md_path.read_text(encoding="utf-8")
            for name in raw_names_to_check:
                assert name not in content, (
                    f"{md_path.name}: マスクされていない人名が残っています: '{name}'"
                )

    def test_message_structure(self):
        """各ファイルに ## で始まる人物セクションがあること（人名が空でもOK）"""
        for md_path in self.md_files:
            content = md_path.read_text(encoding="utf-8")
            # ## の後に人名があるか、空でも ## 行自体が存在すること
            h2_sections = re.findall(r"^## ", content, re.MULTILINE)
            assert len(h2_sections) >= 1, (
                f"{md_path.name}: ## セクション（人物エントリ）が見つかりません"
            )

    def test_blockquote_messages(self):
        """少なくとも一部のファイルに引用形式（> ）のメッセージがあること"""
        has_quote = False
        for md_path in self.md_files:
            content = md_path.read_text(encoding="utf-8")
            if re.search(r"^> .+", content, re.MULTILINE):
                has_quote = True
                break
        assert has_quote, "どの神社メッセージMDにも引用形式（> ）のメッセージが見つかりません"
