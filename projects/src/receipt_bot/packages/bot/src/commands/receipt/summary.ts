import { ChatInputCommandInteraction, EmbedBuilder, TextChannel } from 'discord.js';
import { getOrCreateUser, getReceipts, getUserTags } from '../../lib/supabase';
import { format, startOfDay, endOfDay, subDays } from 'date-fns';
import { ja } from 'date-fns/locale';

interface SummaryData {
  totalAmount: number;
  receiptCount: number;
  byCategory: Record<string, { amount: number; count: number }>;
  byTag: Record<string, { amount: number; count: number; color: string }>;
  receipts: Array<{
    store_name?: string;
    amount?: number;
    category?: string;
    tags?: string[];
  }>;
}

// 日次サマリーを生成
async function generateDailySummary(userId: string, date: Date): Promise<SummaryData> {
  const dateStr = format(date, 'yyyy-MM-dd');
  
  // 指定日のレシートを取得
  const { receipts } = await getReceipts(userId, {
    limit: 100,
  });

  // 指定日のレシートをフィルタリング
  const dailyReceipts = receipts.filter(receipt => 
    receipt.receipt_date === dateStr
  );

  // 集計データを作成
  const summaryData: SummaryData = {
    totalAmount: 0,
    receiptCount: dailyReceipts.length,
    byCategory: {},
    byTag: {},
    receipts: [],
  };

  // レシートごとに集計
  for (const receipt of dailyReceipts) {
    const amount = receipt.amount || 0;
    summaryData.totalAmount += amount;

    // カテゴリ別集計
    const categoryName = receipt.category?.name || '未分類';
    if (!summaryData.byCategory[categoryName]) {
      summaryData.byCategory[categoryName] = { amount: 0, count: 0 };
    }
    summaryData.byCategory[categoryName].amount += amount;
    summaryData.byCategory[categoryName].count += 1;

    // タグ別集計
    if (receipt.tags && receipt.tags.length > 0) {
      for (const tag of receipt.tags) {
        if (!summaryData.byTag[tag.name]) {
          summaryData.byTag[tag.name] = { amount: 0, count: 0, color: tag.color };
        }
        summaryData.byTag[tag.name].amount += amount;
        summaryData.byTag[tag.name].count += 1;
      }
    }

    // レシート詳細を追加
    summaryData.receipts.push({
      store_name: receipt.store_name,
      amount: receipt.amount,
      category: categoryName,
      tags: receipt.tags?.map(t => t.name),
    });
  }

  return summaryData;
}

// サマリーをEmbedとして作成
function createSummaryEmbed(date: Date, summary: SummaryData): EmbedBuilder {
  const dateStr = format(date, 'yyyy年MM月dd日 (E)', { locale: ja });
  
  const embed = new EmbedBuilder()
    .setTitle(`📊 ${dateStr}の支出サマリー`)
    .setColor(0x0099FF)
    .setTimestamp();

  // 全体サマリー
  embed.addFields({
    name: '📈 全体',
    value: `総額: **¥${summary.totalAmount.toLocaleString()}**\n件数: **${summary.receiptCount}件**`,
    inline: false,
  });

  // カテゴリ別サマリー
  if (Object.keys(summary.byCategory).length > 0) {
    const categoryLines = Object.entries(summary.byCategory)
      .sort(([, a], [, b]) => b.amount - a.amount)
      .map(([name, data]) => 
        `• ${name}: ¥${data.amount.toLocaleString()} (${data.count}件)`
      );
    
    embed.addFields({
      name: '📁 カテゴリ別',
      value: categoryLines.join('\n') || 'なし',
      inline: true,
    });
  }

  // タグ別サマリー
  if (Object.keys(summary.byTag).length > 0) {
    const tagLines = Object.entries(summary.byTag)
      .sort(([, a], [, b]) => b.amount - a.amount)
      .map(([name, data]) => 
        `• ${name}: ¥${data.amount.toLocaleString()} (${data.count}件)`
      );
    
    embed.addFields({
      name: '🏷️ タグ別',
      value: tagLines.join('\n') || 'なし',
      inline: true,
    });
  }

  // レシート詳細（上位5件）
  if (summary.receipts.length > 0) {
    const receiptLines = summary.receipts
      .sort((a, b) => (b.amount || 0) - (a.amount || 0))
      .slice(0, 5)
      .map(receipt => 
        `• ${receipt.store_name || '店舗不明'}: ¥${(receipt.amount || 0).toLocaleString()}`
      );
    
    embed.addFields({
      name: '🧾 主な支出',
      value: receiptLines.join('\n'),
      inline: false,
    });
  }

  return embed;
}

// 手動サマリーコマンド
export async function summaryCommand(interaction: ChatInputCommandInteraction) {
  await interaction.deferReply();

  try {
    const user = await getOrCreateUser(
      interaction.user.id,
      interaction.user.username
    );

    const dateOption = interaction.options.getString('date');
    const sendToChannel = interaction.options.getBoolean('send-to-channel') || false;
    
    // 日付の決定（指定がなければ昨日）
    let targetDate: Date;
    if (dateOption) {
      targetDate = new Date(dateOption);
    } else {
      targetDate = subDays(new Date(), 1);
    }

    // サマリーを生成
    const summary = await generateDailySummary(user.id, targetDate);
    const embed = createSummaryEmbed(targetDate, summary);

    if (summary.receiptCount === 0) {
      embed.setDescription('この日のレシートはありません。');
    }

    // チャンネルに送信するかどうか
    if (sendToChannel && interaction.channel) {
      await interaction.editReply({
        content: '✅ サマリーをチャンネルに送信しました。',
      });
      await (interaction.channel as TextChannel).send({ embeds: [embed] });
    } else {
      await interaction.editReply({ embeds: [embed] });
    }
  } catch (error) {
    console.error('Summary command error:', error);
    await interaction.editReply({
      content: 'サマリーの生成中にエラーが発生しました。',
    });
  }
}

// 自動日次サマリー送信
export async function sendDailySummary(userId: string, discordUserId: string, channelId: string, client: any): Promise<boolean> {
  try {
    const channel = await client.channels.fetch(channelId) as TextChannel;
    if (!channel) {
      console.error(`Channel ${channelId} not found`);
      return false;
    }

    // 昨日のサマリーを生成
    const yesterday = subDays(new Date(), 1);
    const summary = await generateDailySummary(userId, yesterday);
    
    // サマリーがない場合はスキップ
    if (summary.receiptCount === 0) {
      return false;
    }

    const embed = createSummaryEmbed(yesterday, summary);
    await channel.send({
      content: `<@${discordUserId}> 昨日の支出サマリーです:`,
      embeds: [embed],
    });

    return true;
  } catch (error) {
    console.error('Send daily summary error:', error);
    return false;
  }
}