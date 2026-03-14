import { ChatInputCommandInteraction, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle, StringSelectMenuBuilder, ComponentType, ButtonInteraction, StringSelectMenuInteraction, MessageComponentInteraction } from 'discord.js';
import { getOrCreateUser, deleteReceipt, getReceiptById, getReceipts } from '../../lib/supabase';

export async function receiptDeleteCommand(interaction: ChatInputCommandInteraction) {
  await interaction.deferReply();

  try {
    // Get user
    const user = await getOrCreateUser(
      interaction.user.id,
      interaction.user.username
    );

    // Get receipt ID from options (optional)
    const receiptId = interaction.options.getString('receipt_id');

    // If receipt ID is provided, delete directly
    if (receiptId) {
      // Get receipt details
      const receipt = await getReceiptById(receiptId);

      if (!receipt) {
        await interaction.editReply('❌ 指定されたレシートが見つかりません。');
        return;
      }

      // Verify ownership
      if (receipt.user_id !== user.id) {
        await interaction.editReply('❌ このレシートを削除する権限がありません。');
        return;
      }

      // Show confirmation for single receipt
      await showDeleteConfirmation(interaction, receipt, receiptId);
      return;
    }

    // If no receipt ID, show list to select from
    const month = new Date().toISOString().slice(0, 7);
    const { receipts, total } = await getReceipts(user.id, {
      month,
      limit: 25,
    });

    if (receipts.length === 0) {
      await interaction.editReply({
        content: `${month} のレシートは見つかりませんでした。`,
      });
      return;
    }

    // Create select menu options
    const options = receipts.slice(0, 25).map((receipt, index) => {
      const date = receipt.receipt_date || '日付不明';
      const storeName = receipt.store_name || '店舗不明';
      const amount = receipt.amount ? `¥${receipt.amount.toLocaleString()}` : '金額不明';
      
      return {
        label: `${date} - ${storeName}`,
        description: `${amount} (${receipt.category?.name || '未分類'})`,
        value: receipt.id,
        emoji: '🗑️',
      };
    });

    // Create select menu
    const selectMenu = new StringSelectMenuBuilder()
      .setCustomId('select_receipt_to_delete')
      .setPlaceholder('削除するレシートを選択してください')
      .addOptions(options);

    const row = new ActionRowBuilder<StringSelectMenuBuilder>()
      .addComponents(selectMenu);

    const embed = new EmbedBuilder()
      .setTitle('🗑️ レシート削除')
      .setDescription(`削除するレシートを選択してください。\n表示中: ${receipts.length}件 / 全${total}件`)
      .setColor(0xff6b6b);

    await interaction.editReply({
      embeds: [embed],
      components: [row],
    });

    // Handle selection
    const collector = interaction.channel?.createMessageComponentCollector({
      filter: i => i.user.id === interaction.user.id && i.customId === 'select_receipt_to_delete',
      time: 60000,
      componentType: ComponentType.StringSelect,
    });

    collector?.on('collect', async (i: StringSelectMenuInteraction) => {
      if (!i.isStringSelectMenu()) return;
      
      const selectedReceiptId = i.values[0];
      const selectedReceipt = receipts.find(r => r.id === selectedReceiptId);
      
      if (!selectedReceipt) {
        await i.update({
          content: '❌ レシートが見つかりませんでした。',
          embeds: [],
          components: [],
        });
        return;
      }

      await i.deferUpdate();
      await showDeleteConfirmation(i, selectedReceipt, selectedReceiptId);
      collector.stop();
    });

    collector?.on('end', (collected: any, reason: string) => {
      if (reason === 'time' && collected.size === 0) {
        interaction.editReply({
          content: '⏱️ タイムアウトしました。',
          embeds: [],
          components: [],
        }).catch(() => {});
      }
    });


  } catch (error) {
    console.error('Delete command error:', error);
    await interaction.editReply({
      content: `エラーが発生しました: ${error instanceof Error ? error.message : 'Unknown error'}`,
    });
  }
}

async function showDeleteConfirmation(
  interaction: ChatInputCommandInteraction | MessageComponentInteraction,
  receipt: any,
  receiptId: string
) {
  // Create confirmation embed
  const embed = new EmbedBuilder()
    .setTitle('⚠️ レシート削除の確認')
    .setColor(0xff6b6b)
    .setDescription('本当にこのレシートを削除しますか？')
    .addFields([
      {
        name: '店舗名',
        value: receipt.store_name || '不明',
        inline: true,
      },
      {
        name: '金額',
        value: receipt.amount ? `¥${receipt.amount.toLocaleString()}` : '不明',
        inline: true,
      },
      {
        name: '日付',
        value: receipt.receipt_date || '不明',
        inline: true,
      },
    ]);

  if (receipt.notes) {
    embed.addFields({
      name: 'メモ',
      value: receipt.notes,
      inline: false,
    });
  }

  if (receipt.image_url) {
    embed.setThumbnail(receipt.image_url);
  }

  // Create action buttons
  const row = new ActionRowBuilder<ButtonBuilder>()
    .addComponents(
      new ButtonBuilder()
        .setCustomId(`confirm_delete_${receiptId}`)
        .setLabel('削除する')
        .setStyle(ButtonStyle.Danger)
        .setEmoji('🗑️'),
      new ButtonBuilder()
        .setCustomId(`cancel_delete_${receiptId}`)
        .setLabel('キャンセル')
        .setStyle(ButtonStyle.Secondary)
    );

  await interaction.editReply({
    embeds: [embed],
    components: [row],
  });

  // Handle button interactions
  const collector = interaction.channel?.createMessageComponentCollector({
    filter: (i) => i.user.id === interaction.user.id && i.customId.includes(receiptId),
    time: 30000, // 30 seconds
  });

  collector?.on('collect', async (i: ButtonInteraction) => {
    if (i.customId.startsWith('confirm_delete_')) {
      await i.deferUpdate();
      try {
        // Delete the receipt
        await deleteReceipt(receiptId);
        
        embed.setTitle('✅ レシート削除完了')
          .setColor(0x00ff00)
          .setDescription('レシートが正常に削除されました。');
        
        await i.editReply({
          embeds: [embed],
          components: [],
        });
      } catch (error) {
        console.error('Delete error:', error);
        await i.editReply({
          content: '❌ 削除中にエラーが発生しました。',
          embeds: [],
          components: [],
        });
      }
      collector.stop();
    } else if (i.customId.startsWith('cancel_delete_')) {
      await i.update({
        content: '削除をキャンセルしました。',
        embeds: [],
        components: [],
      });
      collector.stop();
    }
  });

  collector?.on('end', (collected: any, reason: string) => {
    if (reason === 'time' && collected.size === 0) {
      interaction.editReply({
        content: '⏱️ タイムアウトしました。削除はキャンセルされました。',
        embeds: [],
        components: [],
      }).catch(() => {});
    }
  });
}