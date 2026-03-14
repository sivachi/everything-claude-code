import { ChatInputCommandInteraction, AttachmentBuilder } from 'discord.js';
import { getOrCreateUser, getReceipts } from '../../lib/supabase';

export async function receiptExportCommand(interaction: ChatInputCommandInteraction) {
  await interaction.deferReply();

  try {
    // Get user
    const user = await getOrCreateUser(
      interaction.user.id,
      interaction.user.username
    );

    // Get options
    const format = interaction.options.getString('format', true);
    const month = interaction.options.getString('month') || new Date().toISOString().slice(0, 7);

    // Fetch all receipts for the month
    const { receipts } = await getReceipts(user.id, {
      month,
      limit: 1000, // Get all receipts
    });

    if (receipts.length === 0) {
      await interaction.editReply({
        content: `${month} のレシートは見つかりませんでした。`,
      });
      return;
    }

    let fileContent: string;
    let fileName: string;
    let mimeType: string;

    if (format === 'csv') {
      // Create CSV
      const headers = ['日付', '店舗名', '金額', '税額', 'カテゴリ', 'メモ'];
      const rows = receipts.map(r => [
        r.receipt_date || '',
        r.store_name || '',
        r.amount?.toString() || '0',
        r.tax_amount?.toString() || '0',
        r.category?.name || '未分類',
        r.notes?.replace(/"/g, '""') || '', // Escape quotes
      ]);

      fileContent = [
        headers.join(','),
        ...rows.map(row => row.map(cell => `"${cell}"`).join(',')),
      ].join('\n');

      fileName = `receipts_${month}.csv`;
      mimeType = 'text/csv';
    } else {
      // Create JSON
      const exportData = {
        exportDate: new Date().toISOString(),
        period: month,
        totalAmount: receipts.reduce((sum, r) => sum + (r.amount || 0), 0),
        receiptCount: receipts.length,
        receipts: receipts.map(r => ({
          id: r.id,
          date: r.receipt_date,
          storeName: r.store_name,
          amount: r.amount,
          taxAmount: r.tax_amount,
          category: r.category?.name || '未分類',
          categoryCode: r.category?.code,
          notes: r.notes,
          imageUrl: r.image_url,
          createdAt: r.created_at,
        })),
      };

      fileContent = JSON.stringify(exportData, null, 2);
      fileName = `receipts_${month}.json`;
      mimeType = 'application/json';
    }

    // Create attachment
    const attachment = new AttachmentBuilder(Buffer.from(fileContent, 'utf-8'), {
      name: fileName,
    });

    // Calculate summary
    const totalAmount = receipts.reduce((sum, r) => sum + (r.amount || 0), 0);

    await interaction.editReply({
      content: `📤 ${month} のレシートデータをエクスポートしました\n` +
        `レシート数: ${receipts.length}件\n` +
        `合計金額: ¥${totalAmount.toLocaleString()}`,
      files: [attachment],
    });

  } catch (error) {
    console.error('Export error:', error);
    await interaction.editReply({
      content: `エラーが発生しました: ${error instanceof Error ? error.message : 'Unknown error'}`,
    });
  }
}