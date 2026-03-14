import { Client } from 'discord.js';
import { format } from 'date-fns';
import { ja } from 'date-fns/locale';
import { getUsersToNotify } from '../commands/receipt/notify';
import { sendDailySummary } from '../commands/receipt/summary';

export class NotificationScheduler {
  private client: Client;
  private intervalId?: NodeJS.Timeout;

  constructor(client: Client) {
    this.client = client;
  }

  start() {
    // 毎分実行
    this.intervalId = setInterval(() => {
      this.checkAndSendNotifications();
    }, 60000); // 1分ごと

    console.log('Notification scheduler started');
  }

  stop() {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      console.log('Notification scheduler stopped');
    }
  }

  private async checkAndSendNotifications() {
    try {
      // 現在時刻を HH:MM 形式で取得
      const now = new Date();
      const currentTime = format(now, 'HH:mm');

      // 通知が必要なユーザーを取得
      const usersToNotify = await getUsersToNotify(currentTime);

      if (usersToNotify.length === 0) {
        return;
      }

      console.log(`Sending daily summaries to ${usersToNotify.length} users at ${currentTime}`);

      // 各ユーザーに通知を送信
      for (const settings of usersToNotify) {
        try {
          await sendDailySummary(
            settings.user_id,
            settings.discord_user_id,
            settings.channel_id,
            this.client
          );
        } catch (error) {
          console.error(`Failed to send summary to user ${settings.user_id}:`, error);
        }
      }
    } catch (error) {
      console.error('Scheduler error:', error);
    }
  }
}