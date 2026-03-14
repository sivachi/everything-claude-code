-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create expense_categories table
CREATE TABLE receipt_expense_categories (
  id SERIAL PRIMARY KEY,
  code TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  parent_id INTEGER REFERENCES receipt_expense_categories(id),
  is_active BOOLEAN DEFAULT TRUE,
  sort_order INTEGER DEFAULT 0,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert freee standard categories
INSERT INTO receipt_expense_categories (code, name, description, sort_order) VALUES
  ('SUPPLIES', '消耗品費', '10万円未満の消耗品、事務用品など', 1),
  ('TRAVEL', '旅費交通費', '電車賃、バス代、タクシー代など', 2),
  ('MEETING', '会議費', '会議・打ち合わせの飲食代など', 3),
  ('ENTERTAINMENT', '交際費', '接待、お中元・お歳暮など', 4),
  ('BOOKS', '新聞図書費', '新聞、書籍、雑誌など', 5),
  ('COMMUNICATION', '通信費', '電話代、インターネット代など', 6),
  ('UTILITIES', '水道光熱費', '電気、ガス、水道代など', 7),
  ('COMMISSION', '支払手数料', '振込手数料、代引き手数料など', 8),
  ('MISC', '雑費', 'その他の少額経費', 9);

-- Create users table
CREATE TABLE receipt_users (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  discord_id TEXT UNIQUE NOT NULL,
  discord_username TEXT NOT NULL,
  email TEXT,
  default_category_id INTEGER REFERENCES receipt_expense_categories(id),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create receipts table
CREATE TABLE receipt_receipts (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES receipt_users(id) ON DELETE CASCADE,
  discord_user_id TEXT NOT NULL,
  image_url TEXT NOT NULL,
  thumbnail_url TEXT,
  ocr_raw_text TEXT,
  
  -- Extracted data
  store_name TEXT,
  amount DECIMAL(10, 2),
  tax_amount DECIMAL(10, 2),
  receipt_date DATE,
  
  -- Classification
  category_id INTEGER REFERENCES receipt_expense_categories(id),
  category_confidence DECIMAL(3, 2), -- 0.00 ~ 1.00
  is_category_confirmed BOOLEAN DEFAULT FALSE,
  
  -- Metadata
  notes TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  deleted_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes
CREATE INDEX idx_receipts_user_id ON receipt_receipts(user_id);
CREATE INDEX idx_receipts_discord_user_id ON receipt_receipts(discord_user_id);
CREATE INDEX idx_receipts_receipt_date ON receipt_receipts(receipt_date);
CREATE INDEX idx_receipts_category_id ON receipt_receipts(category_id);
CREATE INDEX idx_receipts_created_at ON receipt_receipts(created_at);

-- Create category_rules table
CREATE TABLE receipt_category_rules (
  id SERIAL PRIMARY KEY,
  user_id UUID REFERENCES receipt_users(id) ON DELETE CASCADE,
  keyword TEXT NOT NULL,
  category_id INTEGER NOT NULL REFERENCES receipt_expense_categories(id),
  priority INTEGER DEFAULT 0,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert global rules
INSERT INTO receipt_category_rules (keyword, category_id, priority) VALUES
  ('コンビニ', (SELECT id FROM receipt_expense_categories WHERE code = 'SUPPLIES'), 100),
  ('セブンイレブン', (SELECT id FROM receipt_expense_categories WHERE code = 'SUPPLIES'), 100),
  ('ファミリーマート', (SELECT id FROM receipt_expense_categories WHERE code = 'SUPPLIES'), 100),
  ('ローソン', (SELECT id FROM receipt_expense_categories WHERE code = 'SUPPLIES'), 100),
  ('電車', (SELECT id FROM receipt_expense_categories WHERE code = 'TRAVEL'), 100),
  ('タクシー', (SELECT id FROM receipt_expense_categories WHERE code = 'TRAVEL'), 100),
  ('JR', (SELECT id FROM receipt_expense_categories WHERE code = 'TRAVEL'), 100),
  ('書店', (SELECT id FROM receipt_expense_categories WHERE code = 'BOOKS'), 100),
  ('本屋', (SELECT id FROM receipt_expense_categories WHERE code = 'BOOKS'), 100),
  ('カフェ', (SELECT id FROM receipt_expense_categories WHERE code = 'MEETING'), 90),
  ('スターバックス', (SELECT id FROM receipt_expense_categories WHERE code = 'MEETING'), 90),
  ('レストラン', (SELECT id FROM receipt_expense_categories WHERE code = 'MEETING'), 80);

-- Create monthly_summaries table for caching
CREATE TABLE receipt_monthly_summaries (
  id SERIAL PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES receipt_users(id) ON DELETE CASCADE,
  year INTEGER NOT NULL,
  month INTEGER NOT NULL,
  category_id INTEGER REFERENCES receipt_expense_categories(id),
  receipt_count INTEGER DEFAULT 0,
  total_amount DECIMAL(12, 2) DEFAULT 0,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(user_id, year, month, category_id)
);

-- Create function to update timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON receipt_users
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_receipts_updated_at BEFORE UPDATE ON receipt_receipts
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_monthly_summaries_updated_at BEFORE UPDATE ON receipt_monthly_summaries
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();