# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Claude Code plugin** - a collection of production-ready agents, skills, hooks, commands, rules, and MCP configurations. The project provides battle-tested workflows for software development using Claude Code.

## Running Tests

```bash
# Run all tests
node tests/run-all.js

# Run individual test files
node tests/lib/utils.test.js
node tests/lib/package-manager.test.js
node tests/hooks/hooks.test.js
```

## Architecture

The project is organized into several core components:

- **agents/** - Specialized subagents for delegation (planner, code-reviewer, tdd-guide, etc.)
- **skills/** - Workflow definitions and domain knowledge (coding standards, patterns, testing)
- **commands/** - Slash commands invoked by users (/tdd, /plan, /e2e, etc.)
- **hooks/** - Trigger-based automations (session persistence, pre/post-tool hooks)
- **rules/** - Always-follow guidelines (security, coding style, testing requirements)
- **mcp-configs/** - MCP server configurations for external integrations
- **scripts/** - Cross-platform Node.js utilities for hooks and setup
- **tests/** - Test suite for scripts and utilities

## Key Commands

- `/tdd` - Test-driven development workflow
- `/plan` - Implementation planning
- `/e2e` - Generate and run E2E tests
- `/code-review` - Quality review
- `/build-fix` - Fix build errors
- `/learn` - Extract patterns from sessions
- `/skill-create` - Generate skills from git history

## Development Notes

- Package manager detection: npm, pnpm, yarn, bun (configurable via `CLAUDE_PACKAGE_MANAGER` env var or project config)
- Cross-platform: Windows, macOS, Linux support via Node.js scripts
- Agent format: Markdown with YAML frontmatter (name, description, tools, model)
- Skill format: Markdown with clear sections for when to use, how it works, examples
- Hook format: JSON with matcher conditions and command/notification hooks

## Contributing

Follow the formats in CONTRIBUTING.md:
- Agents: Markdown with frontmatter (name, description, tools, model)
- Skills: Clear sections (When to Use, How It Works, Examples)
- Commands: Markdown with description frontmatter
- Hooks: JSON with matcher and hooks array

File naming: lowercase with hyphens (e.g., `python-reviewer.md`, `tdd-workflow.md`)

---

## Projects ディレクトリ（自社開発用）

`projects/` フォルダは自社プロジェクトの作業場です。以下のルールに従ってください。

### フォルダ構成

```
projects/
├── src/                  # ソースコード
├── docs/                 # srcと1対1対応するドキュメント
├── tests/                # ユニットテスト（pytest）
├── old/                  # 不要になった旧ファイル
├── 03_sample/            # 参考サンプル（importせずコピーして使用）
├── 03_e2e/               # e2eテスト参照用
├── 100_IMPORT/           # 外部API用テンプレート
├── .env                  # 機密情報（APIキー等）※Git管理外
├── requirements.txt      # Python依存ライブラリ一覧
├── CLAUDE_ISSUE.md       # エラーの原因と解決策
└── CLAUDE_PROGRESS.md    # 進捗ログ・TODO管理
```

### 実装・設計ルール

- **疎結合な設計**: 各部品が独立して動作するよう設計する
- **サンプルの参照**: `03_sample/` 内のファイルは参考にするが、直接の `import` は禁止。コピーして使用する
- **中断の禁止**: 指示を途中で止めることなく、最後までやり遂げる
- **エラーハンドリング**: 外部API呼び出しやファイル操作には適切な例外処理（`try/except`）を入れ、エラー内容をログ出力する
- **文字エンコーディング**: すべてのファイルはUTF-8で統一

### 命名規則（projects/ 内の Python コード）

- **ファイル名**: スネークケース（例: `data_loader.py`）
- **関数名・変数名**: スネークケース（例: `get_user_data`, `item_count`）
- **クラス名**: パスカルケース（例: `UserManager`, `DataLoader`）
- **定数**: 大文字スネークケース（例: `MAX_RETRY_COUNT`, `API_BASE_URL`）

### ドキュメント記述ルール

- **docs ファイル**: 各関数のインプット、アウトプット、機能説明を詳細に記載
- **.py ファイル**: ファイル上部に処理内容と使用方法を記載
- **エラー記録**: エラーの原因と解決策は `CLAUDE_ISSUE.md` に記載

### 外部機能・APIの活用

| 指示内容 | 参照ファイル（100_IMPORT/...） |
| :--- | :--- |
| Geminiでカテゴリーを分類する | `GEMINI_CATEGORY.md` |
| OpenAIのAPIを使う | `OPENAIGPT5.md` |
| e2eテストをするとき | `03_e2e` を参照 |

### テストルール

- 主要な関数・クラスには `pytest` でユニットテストを作成し、`tests/` に配置
- テストファイル命名: `test_<対象ファイル名>.py`
- e2eテストが必要な場合は `03_e2e` を参照

### 依存関係管理

- `requirements.txt` に使用する外部ライブラリをバージョン固定で記載
- 新規ライブラリ追加時は即座に更新

### ワークフロールール（コンテキストウィンドウ対策）

- 重要な設計判断や実装方針を決めたら `CLAUDE_PROGRESS.md` に追記
- タスク完了・中断時に現在の状態を更新
- 未完了タスクは「TODO」セクションに残す
- どのファイルを作成・変更・削除したかを毎回記録
- **作業再開時は必ず `CLAUDE_PROGRESS.md` を最初に読み込む**
- 大きなタスクは小さなステップに分割し、ステップごとに進捗を記録

### セキュリティ

- APIキー等の機密情報は `.env` ファイルに記載
- `.env` ファイルの内容をコード内にハードコーディングしたり、ログに出力しない
