-- Create storage bucket for receipts
INSERT INTO storage.buckets (id, name, public, avif_autodetection, file_size_limit, allowed_mime_types)
VALUES (
  'receipts', 
  'receipts', 
  false,
  false,
  10485760, -- 10MB
  ARRAY['image/jpeg', 'image/png', 'image/webp']
);

-- Storage policies for receipts bucket
-- Users can upload to their own folder
CREATE POLICY "Users can upload own receipts"
ON storage.objects FOR INSERT
WITH CHECK (
  bucket_id = 'receipts' AND
  auth.uid()::text = (string_to_array(name, '/'))[1]
);

-- Users can view their own receipts
CREATE POLICY "Users can view own receipts"
ON storage.objects FOR SELECT
USING (
  bucket_id = 'receipts' AND
  auth.uid()::text = (string_to_array(name, '/'))[1]
);

-- Users can delete their own receipts
CREATE POLICY "Users can delete own receipts"
ON storage.objects FOR DELETE
USING (
  bucket_id = 'receipts' AND
  auth.uid()::text = (string_to_array(name, '/'))[1]
);

-- Enable RLS on tables
ALTER TABLE receipt_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE receipt_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE receipt_category_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE receipt_monthly_summaries ENABLE ROW LEVEL SECURITY;

-- RLS policies for users table
CREATE POLICY "Users can view own profile"
ON receipt_users FOR SELECT
USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
ON receipt_users FOR UPDATE
USING (auth.uid() = id)
WITH CHECK (auth.uid() = id);

-- RLS policies for receipts table
CREATE POLICY "Users can view own receipts"
ON receipt_receipts FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own receipts"
ON receipt_receipts FOR INSERT
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own receipts"
ON receipt_receipts FOR UPDATE
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own receipts"
ON receipt_receipts FOR DELETE
USING (auth.uid() = user_id);

-- RLS policies for category_rules
CREATE POLICY "Users can view all global rules and own rules"
ON receipt_category_rules FOR SELECT
USING (user_id IS NULL OR auth.uid() = user_id);

CREATE POLICY "Users can insert own rules"
ON receipt_category_rules FOR INSERT
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own rules"
ON receipt_category_rules FOR UPDATE
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own rules"
ON receipt_category_rules FOR DELETE
USING (auth.uid() = user_id);

-- RLS policies for monthly_summaries
CREATE POLICY "Users can view own summaries"
ON receipt_monthly_summaries FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Service role can manage summaries"
ON receipt_monthly_summaries FOR ALL
USING (auth.role() = 'service_role');