import { ChatInputCommandInteraction, EmbedBuilder } from 'discord.js';
import { getOrCreateUser, supabase } from '../../lib/supabase';

export async function receiptStatsCommand(interaction: ChatInputCommandInteraction) {
  await interaction.deferReply();

  try {
    // Get user
    const user = await getOrCreateUser(
      interaction.user.id,
      interaction.user.username
    );

    // Get period
    const period = interaction.options.getString('period') || 'month';
    
    // Calculate date range
    const endDate = new Date();
    const startDate = new Date();
    
    switch (period) {
      case 'week':
        startDate.setDate(endDate.getDate() - 7);
        break;
      case 'month':
        startDate.setMonth(endDate.getMonth() - 1);
        break;
      case 'year':
        startDate.setFullYear(endDate.getFullYear() - 1);
        break;
    }

    // Get statistics
    const { data, error } = await supabase.rpc('get_receipt_stats', {
      p_user_id: user.id,
      p_start_date: startDate.toISOString().split('T')[0],
      p_end_date: endDate.toISOString().split('T')[0],
    });

    if (error) {
      throw new Error(error.message);
    }

    const stats = data[0];
    
    // Create embed
    const embed = new EmbedBuilder()
      .setTitle(`📊 統計情報 (${getPeriodLabel(period)})`)
      .setColor(0x00ff00)
      .addFields(
        {
          name: '合計金額',
          value: `¥${(stats.total_amount || 0).toLocaleString()}`,
          inline: true,
        },
        {
          name: 'レシート数',
          value: `${stats.receipt_count || 0} 枚`,
          inline: true,
        },
        {
          name: '平均金額',
          value: `¥${stats.receipt_count ? Math.round((stats.total_amount || 0) / stats.receipt_count).toLocaleString() : '0'}`,
          inline: true,
        }
      );

    // Add category breakdown
    if (stats.category_breakdown && stats.category_breakdown.length > 0) {
      const categoryText = stats.category_breakdown
        .map((cat: any) => {
          const amount = `¥${cat.amount.toLocaleString()}`;
          const percentage = `${cat.percentage}%`;
          return `**${cat.category_name}**: ${amount} (${percentage})`;
        })
        .join('\n');

      embed.addFields({
        name: 'カテゴリ別内訳',
        value: categoryText || 'データなし',
        inline: false,
      });

      // Create simple text chart
      const maxPercentage = Math.max(...stats.category_breakdown.map((cat: any) => cat.percentage));
      const chart = stats.category_breakdown
        .map((cat: any) => {
          const barLength = Math.round((cat.percentage / maxPercentage) * 20);
          const bar = '█'.repeat(barLength) + '░'.repeat(20 - barLength);
          return `${cat.category_name.padEnd(10)} ${bar} ${cat.percentage}%`;
        })
        .join('\n');

      embed.addFields({
        name: 'カテゴリ分布',
        value: `\`\`\`\n${chart}\n\`\`\``,
        inline: false,
      });
    }

    await interaction.editReply({
      embeds: [embed],
    });

  } catch (error) {
    console.error('Stats error:', error);
    await interaction.editReply({
      content: `エラーが発生しました: ${error instanceof Error ? error.message : 'Unknown error'}`,
    });
  }
}

function getPeriodLabel(period: string): string {
  switch (period) {
    case 'week':
      return '過去7日間';
    case 'month':
      return '過去30日間';
    case 'year':
      return '過去1年間';
    default:
      return period;
  }
}