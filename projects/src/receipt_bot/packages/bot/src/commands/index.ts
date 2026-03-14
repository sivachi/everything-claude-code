import { SlashCommandBuilder } from 'discord.js';
import { receiptUploadCommand } from './receipt/upload';
import { receiptListCommand } from './receipt/list';
import { receiptStatsCommand } from './receipt/stats';
import { receiptExportCommand } from './receipt/export';
import { receiptDeleteCommand } from './receipt/delete';
import { summaryCommand } from './receipt/summary';
import { notifyCommand } from './receipt/notify';
import { category } from './receipt/category';
import { tagListCommand, tagCreateCommand } from './tag';
import { EXPENSE_CATEGORIES } from '../lib/categories';

export const commands = {
  'receipt': {
    upload: receiptUploadCommand,
    list: receiptListCommand,
    stats: receiptStatsCommand,
    export: receiptExportCommand,
    delete: receiptDeleteCommand,
    summary: summaryCommand,
    notify: notifyCommand,
    category: category,
  },
  'tag': {
    list: tagListCommand,
    create: tagCreateCommand,
  }
};

export function registerCommands() {
  return [
    new SlashCommandBuilder()
      .setName('receipt')
      .setDescription('レシート管理コマンド')
      .addSubcommand(subcommand =>
        subcommand
          .setName('upload')
          .setDescription('レシートをアップロード')
          .addAttachmentOption(option =>
            option
              .setName('image')
              .setDescription('レシート画像')
              .setRequired(true)
          )
          .addStringOption(option =>
            option
              .setName('category')
              .setDescription('経費科目')
              .setRequired(false)
              .addChoices(
                ...EXPENSE_CATEGORIES.COMMON.map(cat => ({
                  name: cat.name,
                  value: cat.value
                }))
              )
          )
          .addStringOption(option =>
            option
              .setName('note')
              .setDescription('メモ')
              .setRequired(false)
          )
      )
      .addSubcommand(subcommand =>
        subcommand
          .setName('list')
          .setDescription('レシート一覧を表示')
          .addStringOption(option =>
            option
              .setName('month')
              .setDescription('対象月 (YYYY-MM)')
              .setRequired(false)
          )
          .addStringOption(option =>
            option
              .setName('category')
              .setDescription('カテゴリでフィルタ')
              .setRequired(false)
              .addChoices(
                ...EXPENSE_CATEGORIES.COMMON.map(cat => ({
                  name: cat.name,
                  value: cat.value
                }))
              )
          )
      )
      .addSubcommand(subcommand =>
        subcommand
          .setName('stats')
          .setDescription('統計情報を表示')
          .addStringOption(option =>
            option
              .setName('period')
              .setDescription('期間')
              .setRequired(false)
              .addChoices(
                { name: '今週', value: 'week' },
                { name: '今月', value: 'month' },
                { name: '今年', value: 'year' }
              )
          )
      )
      .addSubcommand(subcommand =>
        subcommand
          .setName('export')
          .setDescription('データをエクスポート')
          .addStringOption(option =>
            option
              .setName('format')
              .setDescription('出力形式')
              .setRequired(true)
              .addChoices(
                { name: 'CSV', value: 'csv' },
                { name: 'JSON', value: 'json' }
              )
          )
          .addStringOption(option =>
            option
              .setName('month')
              .setDescription('対象月 (YYYY-MM)')
              .setRequired(false)
          )
      )
      .addSubcommand(subcommand =>
        subcommand
          .setName('delete')
          .setDescription('レシートを削除')
          .addStringOption(option =>
            option
              .setName('receipt_id')
              .setDescription('レシートID（省略時はリストから選択）')
              .setRequired(false)
          )
      )
      .addSubcommand(subcommand =>
        subcommand
          .setName('summary')
          .setDescription('日次サマリーを表示')
          .addStringOption(option =>
            option
              .setName('date')
              .setDescription('対象日 (YYYY-MM-DD)')
              .setRequired(false)
          )
          .addBooleanOption(option =>
            option
              .setName('send-to-channel')
              .setDescription('チャンネルに送信する')
              .setRequired(false)
          )
      )
      .addSubcommandGroup(subcommandGroup =>
        subcommandGroup
          .setName('notify')
          .setDescription('通知設定')
          .addSubcommand(subcommand =>
            subcommand
              .setName('setup')
              .setDescription('日次サマリー通知を設定')
              .addChannelOption(option =>
                option
                  .setName('channel')
                  .setDescription('通知先チャンネル')
                  .setRequired(true)
              )
              .addStringOption(option =>
                option
                  .setName('time')
                  .setDescription('通知時刻 (HH:MM形式、例: 21:00)')
                  .setRequired(false)
              )
          )
          .addSubcommand(subcommand =>
            subcommand
              .setName('status')
              .setDescription('通知設定を確認')
          )
          .addSubcommand(subcommand =>
            subcommand
              .setName('stop')
              .setDescription('通知を停止')
          )
      )
      .addSubcommandGroup(subcommandGroup =>
        subcommandGroup
          .setName('category')
          .setDescription('カテゴリ設定')
          .addSubcommand(subcommand =>
            subcommand
              .setName('list')
              .setDescription('カテゴリ一覧を表示')
          )
          .addSubcommand(subcommand =>
            subcommand
              .setName('set-default')
              .setDescription('デフォルトカテゴリを設定')
              .addStringOption(option =>
                option
                  .setName('category')
                  .setDescription('デフォルトカテゴリ')
                  .setRequired(true)
                  .addChoices(
                    ...EXPENSE_CATEGORIES.COMMON.map(cat => ({
                      name: cat.name,
                      value: cat.value
                    }))
                  )
              )
          )
          .addSubcommand(subcommand =>
            subcommand
              .setName('add-rule')
              .setDescription('自動分類ルールを追加')
              .addStringOption(option =>
                option
                  .setName('keyword')
                  .setDescription('キーワード')
                  .setRequired(true)
              )
              .addStringOption(option =>
                option
                  .setName('category')
                  .setDescription('カテゴリ')
                  .setRequired(true)
                  .addChoices(
                    ...EXPENSE_CATEGORIES.COMMON.map(cat => ({
                      name: cat.name,
                      value: cat.value
                    }))
                  )
              )
          )
      )
      .toJSON(),
    new SlashCommandBuilder()
      .setName('tag')
      .setDescription('タグ管理コマンド')
      .addSubcommand(subcommand =>
        subcommand
          .setName('list')
          .setDescription('タグ一覧を表示')
      )
      .addSubcommand(subcommand =>
        subcommand
          .setName('create')
          .setDescription('新しいタグを作成')
      )
      .toJSON(),
  ];
}