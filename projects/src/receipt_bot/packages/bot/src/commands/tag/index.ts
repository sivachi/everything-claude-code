import { ChatInputCommandInteraction, EmbedBuilder, ModalBuilder, TextInputBuilder, TextInputStyle, ActionRowBuilder, ModalSubmitInteraction } from 'discord.js';
import { getOrCreateUser, getUserTags, getOrCreateTag } from '../../lib/supabase';

export async function tagListCommand(interaction: ChatInputCommandInteraction) {
  await interaction.deferReply({ ephemeral: true });

  try {
    const user = await getOrCreateUser(
      interaction.user.id,
      interaction.user.username
    );

    const tags = await getUserTags(user.id);

    if (tags.length === 0) {
      await interaction.editReply({
        content: 'タグがまだ作成されていません。`/tag create` でタグを作成してください。',
      });
      return;
    }

    const embed = new EmbedBuilder()
      .setTitle('📋 あなたのタグ一覧')
      .setColor(0x0099FF)
      .setDescription(tags.map(tag => `🏷️ **${tag.name}** ${tag.color ? `(${tag.color})` : ''}\n${tag.description || '説明なし'}`).join('\n\n'))
      .setTimestamp();

    await interaction.editReply({
      embeds: [embed],
    });
  } catch (error) {
    console.error('Tag list error:', error);
    await interaction.editReply({
      content: 'タグ一覧の取得中にエラーが発生しました。',
    });
  }
}

export async function tagCreateCommand(interaction: ChatInputCommandInteraction) {
  try {
    const user = await getOrCreateUser(
      interaction.user.id,
      interaction.user.username
    );

    // Show modal for creating new tag
    const modal = new ModalBuilder()
      .setCustomId(`tag_create_modal_${interaction.id}`)
      .setTitle('新しいタグを作成');

    const nameInput = new TextInputBuilder()
      .setCustomId('name')
      .setLabel('タグ名')
      .setStyle(TextInputStyle.Short)
      .setRequired(true)
      .setMaxLength(50)
      .setPlaceholder('例: 食費');

    const colorInput = new TextInputBuilder()
      .setCustomId('color')
      .setLabel('カラーコード')
      .setStyle(TextInputStyle.Short)
      .setRequired(false)
      .setValue('#808080')
      .setPlaceholder('例: #FF5733');

    modal.addComponents(
      new ActionRowBuilder<TextInputBuilder>().addComponents(nameInput),
      new ActionRowBuilder<TextInputBuilder>().addComponents(colorInput)
    );

    await interaction.showModal(modal);

    // Wait for modal submission
    try {
      const modalInteraction = await interaction.awaitModalSubmit({
        time: 300000,
        filter: (mi: ModalSubmitInteraction) => mi.customId === `tag_create_modal_${interaction.id}` && mi.user.id === interaction.user.id,
      });

      const name = modalInteraction.fields.getTextInputValue('name');
      const color = modalInteraction.fields.getTextInputValue('color') || '#808080';

      // Create tag
      const tag = await getOrCreateTag(user.id, name, color);

      await modalInteraction.reply({
        content: `✅ タグ「${name}」を作成しました！`,
        ephemeral: true,
      });
    } catch (error) {
      console.error('Tag create modal error:', error);
    }
  } catch (error) {
    console.error('Tag create error:', error);
    await interaction.reply({
      content: 'タグ作成中にエラーが発生しました。',
      ephemeral: true,
    });
  }
}