import { ChatInputCommandInteraction, ChannelType } from 'discord.js';
import { getOrCreateUser } from '../../lib/supabase';
import { supabase } from '../../lib/supabase';

interface NotificationSetting {
  id: string;
  user_id: string;
  discord_user_id: string;
  channel_id: string;
  is_enabled: boolean;
  notify_time: string; // HH:MM format
  created_at: string;
  updated_at: string;
}

// 通知設定を取得
export async function getNotificationSettings(userId: string): Promise<NotificationSetting | null> {
  const { data, error } = await supabase
    .from('receipt_notification_settings')
    .select('*')
    .eq('user_id', userId)
    .single();

  if (error && error.code !== 'PGRST116') { // PGRST116 = no rows found
    throw new Error(`Failed to fetch notification settings: ${error.message}`);
  }

  return data;
}

// 通知設定を作成・更新
export async function upsertNotificationSettings(
  userId: string,
  discordUserId: string,
  channelId: string,
  isEnabled: boolean,
  notifyTime: string
): Promise<NotificationSetting> {
  const { data, error } = await supabase
    .from('receipt_notification_settings')
    .upsert({
      user_id: userId,
      discord_user_id: discordUserId,
      channel_id: channelId,
      is_enabled: isEnabled,
      notify_time: notifyTime,
      updated_at: new Date().toISOString(),
    }, {
      onConflict: 'user_id',
    })
    .select()
    .single();

  if (error) {
    throw new Error(`Failed to upsert notification settings: ${error.message}`);
  }

  return data;
}

// 通知設定コマンド
export async function notifyCommand(interaction: ChatInputCommandInteraction) {
  const subcommand = interaction.options.getSubcommand();

  if (subcommand === 'setup') {
    await setupNotification(interaction);
  } else if (subcommand === 'status') {
    await showNotificationStatus(interaction);
  } else if (subcommand === 'stop') {
    await stopNotification(interaction);
  }
}

// 通知設定を行う
async function setupNotification(interaction: ChatInputCommandInteraction) {
  await interaction.deferReply({ ephemeral: true });

  try {
    const user = await getOrCreateUser(
      interaction.user.id,
      interaction.user.username
    );

    const channel = interaction.options.getChannel('channel', true);
    const time = interaction.options.getString('time') || '21:00';

    // チャンネルがテキストチャンネルか確認
    if (channel.type !== ChannelType.GuildText) {
      await interaction.editReply({
        content: '❌ テキストチャンネルを指定してください。',
      });
      return;
    }

    // 時刻フォーマットの検証（HH:MM）
    const timeRegex = /^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$/;
    if (!timeRegex.test(time)) {
      await interaction.editReply({
        content: '❌ 時刻は HH:MM 形式で指定してください（例: 21:00）',
      });
      return;
    }

    // 通知設定を保存
    await upsertNotificationSettings(
      user.id,
      interaction.user.id,
      channel.id,
      true,
      time
    );

    await interaction.editReply({
      content: `✅ 毎日 ${time} に <#${channel.id}> へサマリーを送信するよう設定しました。`,
    });
  } catch (error) {
    console.error('Notify setup error:', error);
    await interaction.editReply({
      content: '通知設定中にエラーが発生しました。',
    });
  }
}

// 通知設定を確認
async function showNotificationStatus(interaction: ChatInputCommandInteraction) {
  await interaction.deferReply({ ephemeral: true });

  try {
    const user = await getOrCreateUser(
      interaction.user.id,
      interaction.user.username
    );

    const settings = await getNotificationSettings(user.id);

    if (!settings) {
      await interaction.editReply({
        content: '📭 通知は設定されていません。\n`/receipt notify setup` で設定してください。',
      });
      return;
    }

    const status = settings.is_enabled ? '有効' : '無効';
    await interaction.editReply({
      content: `📬 **通知設定**\n状態: ${status}\nチャンネル: <#${settings.channel_id}>\n時刻: ${settings.notify_time}`,
    });
  } catch (error) {
    console.error('Notify status error:', error);
    await interaction.editReply({
      content: '通知設定の確認中にエラーが発生しました。',
    });
  }
}

// 通知を停止
async function stopNotification(interaction: ChatInputCommandInteraction) {
  await interaction.deferReply({ ephemeral: true });

  try {
    const user = await getOrCreateUser(
      interaction.user.id,
      interaction.user.username
    );

    const settings = await getNotificationSettings(user.id);

    if (!settings) {
      await interaction.editReply({
        content: '通知は設定されていません。',
      });
      return;
    }

    // 通知を無効化
    await upsertNotificationSettings(
      user.id,
      interaction.user.id,
      settings.channel_id,
      false,
      settings.notify_time
    );

    await interaction.editReply({
      content: '✅ 通知を停止しました。',
    });
  } catch (error) {
    console.error('Notify stop error:', error);
    await interaction.editReply({
      content: '通知停止中にエラーが発生しました。',
    });
  }
}

// 通知が必要なユーザーを取得（スケジューラー用）
export async function getUsersToNotify(currentTime: string): Promise<NotificationSetting[]> {
  const { data, error } = await supabase
    .from('receipt_notification_settings')
    .select('*')
    .eq('is_enabled', true)
    .eq('notify_time', currentTime);

  if (error) {
    throw new Error(`Failed to fetch users to notify: ${error.message}`);
  }

  return data || [];
}