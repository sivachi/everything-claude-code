# Everything Claude Code - システム詳細説明

## 概要

**Everything Claude Code (ecc-universal)** は、Claude Code（AnthropicのCLIツール）用の**プラグイン集**です。10ヶ月以上の実践的な利用から生まれた、本番品質のエージェント・スキル・フック・コマンド・ルール・MCP設定をまとめたものです。Anthropicハッカソン受賞プロジェクトでもあります。

---

## フォルダ構成

```
everything-claude-code/
├── agents/                  # 特化型サブエージェント (16ファイル)
│   ├── architect.md         #   設計・アーキテクチャ担当
│   ├── build-error-resolver.md  # ビルドエラー解決
│   ├── chief-of-staff.md    #   タスク管理・調整役
│   ├── code-reviewer.md     #   コードレビュー
│   ├── database-reviewer.md #   DB設計レビュー
│   ├── doc-updater.md       #   ドキュメント更新
│   ├── e2e-runner.md        #   E2Eテスト実行
│   ├── go-build-resolver.md #   Go ビルド修正
│   ├── go-reviewer.md       #   Go コードレビュー
│   ├── harness-optimizer.md #   テストハーネス最適化
│   ├── loop-operator.md     #   ループ処理オペレータ
│   ├── planner.md           #   実装計画策定
│   ├── python-reviewer.md   #   Python コードレビュー
│   ├── refactor-cleaner.md  #   リファクタリング
│   ├── security-reviewer.md #   セキュリティレビュー
│   └── tdd-guide.md         #   TDD ガイド
│
├── commands/                # スラッシュコマンド (40ファイル)
│   ├── tdd.md               #   /tdd - テスト駆動開発
│   ├── plan.md              #   /plan - 実装計画
│   ├── e2e.md               #   /e2e - E2Eテスト生成・実行
│   ├── code-review.md       #   /code-review - コードレビュー
│   ├── build-fix.md         #   /build-fix - ビルドエラー修正
│   ├── learn.md             #   /learn - セッションからパターン抽出
│   ├── skill-create.md      #   /skill-create - Git履歴からスキル生成
│   ├── orchestrate.md       #   /orchestrate - マルチエージェント調整
│   ├── go-build.md, go-review.md, go-test.md  # Go専用コマンド
│   ├── multi-*.md           #   マルチプロジェクト系コマンド
│   └── ...                  #   その他多数
│
├── skills/                  # スキル定義 (ワークフロー・ドメイン知識)
│   └── (多数のスキルファイル)
│
├── hooks/                   # フック (自動化トリガー)
│   ├── hooks.json           #   フック設定 (SessionStart, PreToolUse, PostToolUse等)
│   └── README.md
│
├── rules/                   # ルール (常時適用ガイドライン)
│   └── README.md            #   共通ルール + 言語別ルール (TS/Python/Go/Swift)
│
├── scripts/                 # ユーティリティスクリプト
│   ├── claw.js              #   CLIツール
│   ├── setup-package-manager.js  # パッケージマネージャ検出
│   ├── skill-create-output.js    # スキル生成出力
│   └── release.sh           #   リリーススクリプト
│
├── mcp-configs/             # MCP サーバー設定
│   └── mcp-servers.json     #   GitHub, Supabase, Vercel, Cloudflare等の統合設定
│
├── contexts/                # コンテキストモード
│   ├── dev.md               #   開発モード (コード優先)
│   ├── research.md          #   リサーチモード
│   └── review.md            #   レビューモード
│
├── schemas/                 # JSONスキーマ定義
│   ├── hooks.schema.json
│   ├── package-manager.schema.json
│   └── plugin.schema.json
│
├── examples/                # CLAUDE.md テンプレート集
│   ├── CLAUDE.md            #   基本テンプレート
│   ├── saas-nextjs-CLAUDE.md    # Next.js SaaS向け
│   ├── django-api-CLAUDE.md     # Django API向け
│   ├── go-microservice-CLAUDE.md # Go マイクロサービス向け
│   ├── rust-api-CLAUDE.md       # Rust API向け
│   └── user-CLAUDE.md          # ユーザー設定例
│
├── plugins/                 # プラグインドキュメント
├── docs/                    # 追加ドキュメント
│   ├── continuous-learning-v2-spec.md
│   └── token-optimization.md
│
├── .claude/                 # Claude Code ローカル設定
├── .claude-plugin/          # プラグインメタデータ (plugin.json等)
├── .cursor/                 # Cursor IDE 対応設定
├── .codex/                  # OpenAI Codex 対応設定
├── .opencode/               # OpenCode 対応設定
│
├── tests/                   # テストスイート
├── install.sh               # インストールスクリプト
├── package.json             # npm パッケージ (ecc-universal)
├── CLAUDE.md                # プロジェクト指示書
├── the-longform-guide.md    # 詳細ガイド
├── the-shortform-guide.md   # 短縮ガイド
├── the-openclaw-guide.md    # OpenClaw ガイド
└── the-security-guide.md    # セキュリティガイド
```

---

## 主要コンポーネントの詳細

### 1. Agents（エージェント）

YAMLフロントマター付きMarkdownで定義。モデル選択（`opus`=計画向き、`sonnet`=レビュー向き）、利用可能ツール、役割の詳細指示を含む。Claude Codeのサブエージェント機能で委任実行される。

### 2. Commands（コマンド）

ユーザーが `/tdd`, `/plan`, `/code-review` のように呼び出すスラッシュコマンド。ワークフローを自動化し、適切なエージェントやスキルを組み合わせて実行する。

### 3. Hooks（フック）

ライフサイクルイベント（セッション開始・終了、ツール実行前後）に応じて自動実行されるスクリプト。Node.jsやbashコマンドで定義。

### 4. Rules（ルール）

常時適用されるガイドライン。共通ルール（セキュリティ、コーディングスタイル）+ 言語別ルール（TypeScript, Python, Go, Swift）のレイヤー構成。

### 5. MCP Configs（MCP設定）

GitHub, Supabase, Vercel, Cloudflare, ClickHouse等の外部サービスとの統合設定。

### 6. Skills（スキル）

再利用可能なワークフロー定義とドメイン知識。「いつ使うか」「どう動くか」「例」のセクション構成。

---

## 対応ワークフロー

| ワークフロー | コマンド | 概要 |
|---|---|---|
| テスト駆動開発 | `/tdd` | Red→Green→Refactorサイクル |
| 実装計画 | `/plan` | 段階的な実装計画策定 |
| コードレビュー | `/code-review` | 品質・セキュリティレビュー |
| E2Eテスト | `/e2e` | E2Eテスト生成・実行 |
| ビルド修正 | `/build-fix` | ビルドエラー自動修正 |
| 継続学習 | `/learn` | セッションからパターン抽出 |
| マルチプロジェクト | `/orchestrate` | 複数プロジェクト横断作業 |

---

## インストール方法

```bash
npx ecc-install typescript   # TypeScriptプロジェクト向け
# または
./install.sh                 # 直接インストール
```

対応パッケージマネージャ: **npm, pnpm, yarn, bun**（環境変数 `CLAUDE_PACKAGE_MANAGER` または設定で切替可能）

---

## まとめ

Everything Claude Codeは、Claude Codeを使った開発を大幅に効率化するための**ベストプラクティス・ツールキット**です。エージェント、コマンド、フック、ルールを組み合わせて、TDD、コードレビュー、セキュリティチェックなどの開発ワークフローを自動化・標準化します。
