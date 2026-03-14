import { ChatInputCommandInteraction, EmbedBuilder } from 'discord.js';
import { getOrCreateUser, getCategories, supabase } from '../../lib/supabase';

export const category = {
  list: categoryListCommand,
  'set-default': categorySetDefaultCommand,
  'add-rule': categoryAddRuleCommand,
};

async function categoryListCommand(interaction: ChatInputCommandInteraction) {
  await interaction.deferReply();

  try {
    const categories = await getCategories();

    const embed = new EmbedBuilder()
      .setTitle('📁 経費科目一覧')
      .setColor(0x0099ff)
      .setDescription('利用可能な経費科目の一覧です');

    categories.forEach(cat => {
      embed.addFields({
        name: `${cat.name} (${cat.code})`,
        value: cat.description || '説明なし',
        inline: false,
      });
    });

    await interaction.editReply({
      embeds: [embed],
    });

  } catch (error) {
    console.error('Category list error:', error);
    await interaction.editReply({
      content: `エラーが発生しました: ${error instanceof Error ? error.message : 'Unknown error'}`,
    });
  }
}

async function categorySetDefaultCommand(interaction: ChatInputCommandInteraction) {
  await interaction.deferReply();

  try {
    // Get user
    const user = await getOrCreateUser(
      interaction.user.id,
      interaction.user.username
    );

    // Get category
    const categoryCode = interaction.options.getString('category', true);
    const categories = await getCategories();
    const category = categories.find(c => c.code === categoryCode);

    if (!category) {
      await interaction.editReply({
        content: 'カテゴリが見つかりませんでした。',
      });
      return;
    }

    // Update user's default category
    const { error } = await supabase
      .from('users')
      .update({ default_category_id: category.id })
      .eq('id', user.id);

    if (error) {
      throw new Error(error.message);
    }

    await interaction.editReply({
      content: `✅ デフォルトカテゴリを「${category.name}」に設定しました。`,
    });

  } catch (error) {
    console.error('Set default category error:', error);
    await interaction.editReply({
      content: `エラーが発生しました: ${error instanceof Error ? error.message : 'Unknown error'}`,
    });
  }
}

async function categoryAddRuleCommand(interaction: ChatInputCommandInteraction) {
  await interaction.deferReply();

  try {
    // Get user
    const user = await getOrCreateUser(
      interaction.user.id,
      interaction.user.username
    );

    // Get options
    const keyword = interaction.options.getString('keyword', true);
    const categoryCode = interaction.options.getString('category', true);

    // Get category
    const categories = await getCategories();
    const category = categories.find(c => c.code === categoryCode);

    if (!category) {
      await interaction.editReply({
        content: 'カテゴリが見つかりませんでした。',
      });
      return;
    }

    // Check if rule already exists
    const { data: existingRule } = await supabase
      .from('category_rules')
      .select('*')
      .eq('user_id', user.id)
      .eq('keyword', keyword)
      .single();

    if (existingRule) {
      await interaction.editReply({
        content: `⚠️ キーワード「${keyword}」のルールは既に存在します。`,
      });
      return;
    }

    // Add rule
    const { error } = await supabase
      .from('category_rules')
      .insert({
        user_id: user.id,
        keyword,
        category_id: category.id,
        priority: 100,
        is_active: true,
      });

    if (error) {
      throw new Error(error.message);
    }

    await interaction.editReply({
      content: `✅ 自動分類ルールを追加しました:\n` +
        `キーワード「${keyword}」→ カテゴリ「${category.name}」`,
    });

  } catch (error) {
    console.error('Add rule error:', error);
    await interaction.editReply({
      content: `エラーが発生しました: ${error instanceof Error ? error.message : 'Unknown error'}`,
    });
  }
}