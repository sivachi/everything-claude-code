import { ChatInputCommandInteraction, ActionRowBuilder, ButtonBuilder, ButtonStyle, ModalBuilder, TextInputBuilder, TextInputStyle, StringSelectMenuBuilder, ComponentType } from 'discord.js';
import { getOrCreateUser, uploadReceiptImage, createReceipt, getCategories, updateReceipt, getUserTags, addTagToReceipt, getReceiptWithTags, Tag } from '../../lib/supabase';
import { analyzeReceiptWithCategory } from '../../lib/gemini';

export async function receiptUploadCommand(interaction: ChatInputCommandInteraction) {
  await interaction.deferReply();

  try {
    // Get user
    const user = await getOrCreateUser(
      interaction.user.id,
      interaction.user.username
    );

    // Get attachment
    const attachment = interaction.options.getAttachment('image', true);
    
    // Validate file type
    if (!attachment.contentType?.startsWith('image/')) {
      await interaction.editReply('画像ファイルをアップロードしてください。');
      return;
    }

    // Download image
    const response = await fetch(attachment.url);
    const buffer = Buffer.from(await response.arrayBuffer());

    // Upload to Supabase
    const { url: imageUrl } = await uploadReceiptImage(
      user.id,
      buffer,
      attachment.name
    );

    // Analyze with Gemini (OCR + Category suggestion in one call)
    await interaction.editReply('レシートを解析中... 🔍');
    const analysis = await analyzeReceiptWithCategory(buffer);

    // Get categories for validation
    const categories = await getCategories();
    
    // Find the suggested category in our database
    let suggestedCategory = categories.find(c => c.code === analysis.category.code);
    
    // If category not found in DB, use MISC
    if (!suggestedCategory) {
      suggestedCategory = categories.find(c => c.code === 'MISC');
    }

    // Get manual category if specified
    const manualCategoryCode = interaction.options.getString('category');
    const manualCategory = manualCategoryCode
      ? categories.find(c => c.code === manualCategoryCode)
      : null;

    // Use manual category if provided, otherwise use AI suggestion
    const finalCategory = manualCategory || suggestedCategory;

    // Get note
    const note = interaction.options.getString('note');

    // Create receipt record
    const receipt = await createReceipt({
      user_id: user.id,
      discord_user_id: interaction.user.id,
      image_url: imageUrl,
      ocr_raw_text: JSON.stringify(analysis),
      store_name: analysis.storeName || undefined,
      amount: analysis.totalAmount || undefined,
      tax_amount: analysis.taxAmount || undefined,
      receipt_date: analysis.date || new Date().toISOString().split('T')[0],
      category_id: finalCategory?.id,
      category_confidence: manualCategory ? 1.0 : analysis.category.confidence,
      is_category_confirmed: !!manualCategory,
      notes: note || undefined,
    });

    // Create confirmation embed
    const embed = {
      title: '📸 レシート解析完了',
      color: 0x00ff00,
      fields: [
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
        {
          name: 'カテゴリ',
          value: finalCategory ? `${finalCategory.name}${!manualCategory ? ` (${Math.round(analysis.category.confidence * 100)}% 確信度)` : ''}` : '未分類',
          inline: true,
        },
      ],
      image: {
        url: imageUrl,
      },
      footer: {
        text: `OCR信頼度: ${Math.round(analysis.ocrConfidence * 100)}% | AI分類理由: ${analysis.category.reason}`,
      },
    };

    if (note) {
      embed.fields.push({
        name: 'メモ',
        value: note,
        inline: false,
      });
    }

    // Create action buttons
    const row = new ActionRowBuilder<ButtonBuilder>()
      .addComponents(
        new ButtonBuilder()
          .setCustomId(`receipt_confirm_${receipt.id}`)
          .setLabel('✅ 確定')
          .setStyle(ButtonStyle.Success),
        new ButtonBuilder()
          .setCustomId(`receipt_edit_${receipt.id}`)
          .setLabel('📝 編集')
          .setStyle(ButtonStyle.Primary),
        new ButtonBuilder()
          .setCustomId(`receipt_delete_${receipt.id}`)
          .setLabel('❌ キャンセル')
          .setStyle(ButtonStyle.Danger)
      );

    await interaction.editReply({
      embeds: [embed],
      components: [row],
    });

    // Handle button interactions
    const collector = interaction.channel?.createMessageComponentCollector({
      filter: i => i.customId.startsWith('receipt_') && i.customId.includes(receipt.id),
      time: 300000, // 5 minutes
    });

    collector?.on('collect', async i => {
      const [, action] = i.customId.split('_');

      if (action === 'confirm') {
        // 先に応答してから処理
        await i.deferUpdate();
        
        try {
          await updateReceipt(receipt.id, { is_category_confirmed: true });
          
          // Get user's tags for tag selection
          const userTags = await getUserTags(user.id);
          
          if (userTags.length > 0) {
            // Create tag selection menu
            const tagOptions = [
              {
                label: 'タグを付けない',
                value: 'no_tag',
                description: 'タグなしで完了',
                emoji: '❌',
              },
              ...userTags.map(tag => ({
                label: tag.name,
                value: tag.id.toString(),
                description: tag.description || '説明なし',
                emoji: '🏷️',
              }))
            ];

            const tagSelectMenu = new StringSelectMenuBuilder()
              .setCustomId(`receipt_tag_confirm_${receipt.id}`)
              .setPlaceholder('タグを選択してください（任意）')
              .addOptions(tagOptions);

            const tagRow = new ActionRowBuilder<StringSelectMenuBuilder>()
              .addComponents(tagSelectMenu);

            await i.editReply({
              content: '✅ レシートを登録しました！タグを追加しますか？',
              embeds: [embed],
              components: [tagRow],
            });

            // Handle tag selection
            const tagCollector = i.channel?.createMessageComponentCollector({
              filter: (fi) => fi.customId === `receipt_tag_confirm_${receipt.id}` && fi.user.id === i.user.id,
              time: 30000,
              max: 1,
              componentType: ComponentType.StringSelect,
            });

            tagCollector?.on('collect', async (tagInteraction) => {
              if (!tagInteraction.isStringSelectMenu()) return;
              
              const selectedValue = tagInteraction.values[0];

              if (selectedValue === 'no_tag') {
                await tagInteraction.update({
                  content: '✅ レシートを登録しました！',
                  embeds: [embed],
                  components: [],
                });
              } else {
                const tagId = parseInt(selectedValue);
                try {
                  await addTagToReceipt(receipt.id, tagId);
                  
                  // Update receipt with tags
                  const updatedReceipt = await getReceiptWithTags(receipt.id);
                  if (updatedReceipt.tags && updatedReceipt.tags.length > 0) {
                    embed.fields.push({
                      name: 'タグ',
                      value: updatedReceipt.tags.map(t => `🏷️ ${t.name}`).join(', '),
                      inline: false,
                    });
                  }
                  
                  const selectedTag = userTags.find((t: Tag) => t.id === tagId);
                  await tagInteraction.update({
                    content: `✅ レシートを登録し、タグ「${selectedTag?.name}」を追加しました！`,
                    embeds: [embed],
                    components: [],
                  });
                } catch (error) {
                  console.error('Tag add error:', error);
                  await tagInteraction.update({
                    content: '✅ レシートを登録しました（タグの追加に失敗しました）',
                    embeds: [embed],
                    components: [],
                  });
                }
              }
            });

            // Handle timeout
            tagCollector?.on('end', (collected, reason) => {
              if (reason === 'time' && collected.size === 0) {
                i.editReply({
                  content: '✅ レシートを登録しました！',
                  embeds: [embed],
                  components: [],
                }).catch(() => {});
              }
            });
          } else {
            // No tags exist, just confirm
            await i.editReply({
              content: '✅ レシートを登録しました！',
              embeds: [embed],
              components: [],
            });
          }
        } catch (error) {
          console.error('Confirm error:', error);
          await i.editReply({
            content: 'エラーが発生しました。レシートは保存されています。',
            embeds: [embed],
            components: [],
          });
        }
        collector.stop();
      } else if (action === 'edit') {
        // Create modal for editing
        const modal = new ModalBuilder()
          .setCustomId(`receipt_edit_modal_${receipt.id}`)
          .setTitle('レシート情報を編集');

        const storeInput = new TextInputBuilder()
          .setCustomId('store_name')
          .setLabel('店舗名')
          .setStyle(TextInputStyle.Short)
          .setValue(receipt.store_name || '')
          .setRequired(false);

        const amountInput = new TextInputBuilder()
          .setCustomId('amount')
          .setLabel('金額')
          .setStyle(TextInputStyle.Short)
          .setValue(receipt.amount?.toString() || '')
          .setRequired(false);

        const dateInput = new TextInputBuilder()
          .setCustomId('date')
          .setLabel('日付 (YYYY-MM-DD)')
          .setStyle(TextInputStyle.Short)
          .setValue(receipt.receipt_date || '')
          .setRequired(false);

        const noteInput = new TextInputBuilder()
          .setCustomId('note')
          .setLabel('メモ')
          .setStyle(TextInputStyle.Paragraph)
          .setValue(receipt.notes || '')
          .setRequired(false);

        modal.addComponents(
          new ActionRowBuilder<TextInputBuilder>().addComponents(storeInput),
          new ActionRowBuilder<TextInputBuilder>().addComponents(amountInput),
          new ActionRowBuilder<TextInputBuilder>().addComponents(dateInput),
          new ActionRowBuilder<TextInputBuilder>().addComponents(noteInput)
        );

        await i.showModal(modal);

        // Wait for modal submission
        try {
          const modalInteraction = await i.awaitModalSubmit({
            time: 300000,
            filter: mi => mi.customId === `receipt_edit_modal_${receipt.id}`,
          });

          const storeName = modalInteraction.fields.getTextInputValue('store_name');
          const amount = modalInteraction.fields.getTextInputValue('amount');
          const date = modalInteraction.fields.getTextInputValue('date');
          const editedNote = modalInteraction.fields.getTextInputValue('note');

          // Update receipt
          const updatedReceipt = await updateReceipt(receipt.id, {
            store_name: storeName || undefined,
            amount: amount ? parseFloat(amount) : undefined,
            receipt_date: date || undefined,
            notes: editedNote || undefined,
          });

          // Update embed
          embed.fields[0].value = updatedReceipt.store_name || '不明';
          embed.fields[1].value = updatedReceipt.amount ? `¥${updatedReceipt.amount.toLocaleString()}` : '不明';
          embed.fields[2].value = updatedReceipt.receipt_date || '不明';

          if (editedNote) {
            const noteField = embed.fields.find(f => f.name === 'メモ');
            if (noteField) {
              noteField.value = editedNote;
            } else {
              embed.fields.push({
                name: 'メモ',
                value: editedNote,
                inline: false,
              });
            }
          }

          await modalInteraction.reply({
            embeds: [embed],
            components: [row],
            ephemeral: true,
          });
        } catch (error) {
          console.error('Modal interaction error:', error);
        }
      } else if (action === 'delete') {
        await i.deferUpdate();
        try {
          await updateReceipt(receipt.id, { deleted_at: new Date().toISOString() });
          await i.editReply({
            content: '❌ レシートの登録をキャンセルしました。',
            embeds: [],
            components: [],
          });
        } catch (error) {
          console.error('Delete error:', error);
          await i.editReply({
            content: 'エラーが発生しました。',
            embeds: [],
            components: [],
          });
        }
        collector.stop();
      }
    });

  } catch (error) {
    console.error('Upload error:', error);
    await interaction.editReply({
      content: `エラーが発生しました: ${error instanceof Error ? error.message : 'Unknown error'}`,
    });
  }
}