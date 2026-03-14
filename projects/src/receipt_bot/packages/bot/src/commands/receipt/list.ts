import { ChatInputCommandInteraction, EmbedBuilder } from 'discord.js';
import { getOrCreateUser, getReceipts } from '../../lib/supabase';

export async function receiptListCommand(interaction: ChatInputCommandInteraction) {
  await interaction.deferReply();

  try {
    // Get user
    const user = await getOrCreateUser(
      interaction.user.id,
      interaction.user.username
    );

    // Get options
    const month = interaction.options.getString('month') || new Date().toISOString().slice(0, 7);
    const categoryCode = interaction.options.getString('category') || undefined;

    // Fetch receipts
    const { receipts, total } = await getReceipts(user.id, {
      month,
      categoryCode,
      limit: 10,
    });

    if (receipts.length === 0) {
      await interaction.editReply({
        content: `${month} のレシートは見つかりませんでした。`,
      });
      return;
    }

    // Create embed
    const embed = new EmbedBuilder()
      .setTitle(`📋 レシート一覧 (${month})`)
      .setColor(0x0099ff)
      .setDescription(`全 ${total} 件中 ${receipts.length} 件を表示`);

    // Add receipt fields
    receipts.forEach((receipt, index) => {
      const amount = receipt.amount ? `¥${receipt.amount.toLocaleString()}` : '金額不明';
      const category = receipt.category?.name || '未分類';
      const storeName = receipt.store_name || '店舗不明';
      const date = receipt.receipt_date || '日付不明';

      embed.addFields({
        name: `${index + 1}. ${date} - ${storeName}`,
        value: `${amount} (${category})${receipt.notes ? `\n📝 ${receipt.notes}` : ''}`,
        inline: false,
      });
    });

    // Calculate total
    const totalAmount = receipts.reduce((sum, r) => sum + (r.amount || 0), 0);
    embed.addFields({
      name: '合計',
      value: `¥${totalAmount.toLocaleString()}`,
      inline: false,
    });

    await interaction.editReply({
      embeds: [embed],
    });

  } catch (error) {
    console.error('List error:', error);
    await interaction.editReply({
      content: `エラーが発生しました: ${error instanceof Error ? error.message : 'Unknown error'}`,
    });
  }
}