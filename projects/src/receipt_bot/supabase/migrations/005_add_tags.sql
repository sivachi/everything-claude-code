-- Create tags table
CREATE TABLE receipt_tags (
  id SERIAL PRIMARY KEY,
  user_id UUID REFERENCES receipt_users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  color TEXT DEFAULT '#808080', -- Hex color code
  description TEXT,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(user_id, name)
);

-- Create receipt_tags junction table
CREATE TABLE receipt_receipt_tags (
  id SERIAL PRIMARY KEY,
  receipt_id UUID REFERENCES receipt_receipts(id) ON DELETE CASCADE,
  tag_id INTEGER REFERENCES receipt_tags(id) ON DELETE CASCADE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(receipt_id, tag_id)
);

-- Create indexes
CREATE INDEX idx_tags_user_id ON receipt_tags(user_id);
CREATE INDEX idx_receipt_tags_receipt_id ON receipt_receipt_tags(receipt_id);
CREATE INDEX idx_receipt_tags_tag_id ON receipt_receipt_tags(tag_id);

-- Enable RLS
ALTER TABLE receipt_tags ENABLE ROW LEVEL SECURITY;
ALTER TABLE receipt_receipt_tags ENABLE ROW LEVEL SECURITY;

-- RLS policies for tags
CREATE POLICY "Users can view own tags"
ON receipt_tags FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Users can create own tags"
ON receipt_tags FOR INSERT
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own tags"
ON receipt_tags FOR UPDATE
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own tags"
ON receipt_tags FOR DELETE
USING (auth.uid() = user_id);

-- RLS policies for receipt_receipt_tags
CREATE POLICY "Users can view own receipt tags"
ON receipt_receipt_tags FOR SELECT
USING (
  EXISTS (
    SELECT 1 FROM receipt_receipts r
    WHERE r.id = receipt_receipt_tags.receipt_id
    AND r.user_id = auth.uid()
  )
);

CREATE POLICY "Users can add tags to own receipts"
ON receipt_receipt_tags FOR INSERT
WITH CHECK (
  EXISTS (
    SELECT 1 FROM receipt_receipts r
    WHERE r.id = receipt_id
    AND r.user_id = auth.uid()
  )
);

CREATE POLICY "Users can remove tags from own receipts"
ON receipt_receipt_tags FOR DELETE
USING (
  EXISTS (
    SELECT 1 FROM receipt_receipts r
    WHERE r.id = receipt_receipt_tags.receipt_id
    AND r.user_id = auth.uid()
  )
);

-- Add trigger for updated_at
CREATE TRIGGER update_tags_updated_at BEFORE UPDATE ON receipt_tags
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to get or create tag
CREATE OR REPLACE FUNCTION get_or_create_tag(
  p_user_id UUID,
  p_tag_name TEXT,
  p_color TEXT DEFAULT '#808080'
)
RETURNS INTEGER AS $$
DECLARE
  v_tag_id INTEGER;
BEGIN
  -- Try to find existing tag
  SELECT id INTO v_tag_id
  FROM receipt_tags
  WHERE user_id = p_user_id
  AND name = p_tag_name;
  
  -- If not found, create new tag
  IF v_tag_id IS NULL THEN
    INSERT INTO receipt_tags (user_id, name, color)
    VALUES (p_user_id, p_tag_name, p_color)
    RETURNING id INTO v_tag_id;
  END IF;
  
  RETURN v_tag_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to add tag to receipt
CREATE OR REPLACE FUNCTION add_tag_to_receipt(
  p_receipt_id UUID,
  p_tag_id INTEGER
)
RETURNS BOOLEAN AS $$
BEGIN
  INSERT INTO receipt_receipt_tags (receipt_id, tag_id)
  VALUES (p_receipt_id, p_tag_id)
  ON CONFLICT (receipt_id, tag_id) DO NOTHING;
  
  RETURN TRUE;
EXCEPTION
  WHEN OTHERS THEN
    RETURN FALSE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to remove tag from receipt
CREATE OR REPLACE FUNCTION remove_tag_from_receipt(
  p_receipt_id UUID,
  p_tag_id INTEGER
)
RETURNS BOOLEAN AS $$
BEGIN
  DELETE FROM receipt_receipt_tags
  WHERE receipt_id = p_receipt_id
  AND tag_id = p_tag_id;
  
  RETURN TRUE;
EXCEPTION
  WHEN OTHERS THEN
    RETURN FALSE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;