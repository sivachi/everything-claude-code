-- 通知設定テーブル
CREATE TABLE IF NOT EXISTS receipt_notification_settings (
  id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES receipt_users(id) ON DELETE CASCADE,
  discord_user_id TEXT NOT NULL,
  channel_id TEXT NOT NULL,
  is_enabled BOOLEAN DEFAULT true,
  notify_time TEXT NOT NULL DEFAULT '21:00', -- HH:MM format
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id)
);

-- インデックス
CREATE INDEX idx_notification_settings_user_id ON receipt_notification_settings(user_id);
CREATE INDEX idx_notification_settings_notify_time ON receipt_notification_settings(notify_time) WHERE is_enabled = true;

-- RLS
ALTER TABLE receipt_notification_settings ENABLE ROW LEVEL SECURITY;

-- ユーザーは自分の通知設定のみアクセス可能
CREATE POLICY "Users can manage their own notification settings" ON receipt_notification_settings
  FOR ALL
  USING (auth.uid()::text = user_id::text);

-- 更新時刻の自動更新
CREATE TRIGGER update_notification_settings_updated_at
  BEFORE UPDATE ON receipt_notification_settings
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at();