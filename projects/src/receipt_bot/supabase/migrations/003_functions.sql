-- Function to get or create user
CREATE OR REPLACE FUNCTION get_or_create_user(
  p_discord_id TEXT,
  p_discord_username TEXT
)
RETURNS UUID AS $$
DECLARE
  v_user_id UUID;
BEGIN
  -- Try to find existing user
  SELECT id INTO v_user_id
  FROM receipt_users
  WHERE discord_id = p_discord_id;
  
  -- If not found, create new user
  IF v_user_id IS NULL THEN
    INSERT INTO receipt_users (discord_id, discord_username)
    VALUES (p_discord_id, p_discord_username)
    RETURNING id INTO v_user_id;
  ELSE
    -- Update username if changed
    UPDATE receipt_users
    SET discord_username = p_discord_username
    WHERE id = v_user_id
    AND discord_username != p_discord_username;
  END IF;
  
  RETURN v_user_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to update monthly summary
CREATE OR REPLACE FUNCTION update_monthly_summary()
RETURNS TRIGGER AS $$
BEGIN
  -- Update summary for new receipt
  IF TG_OP = 'INSERT' THEN
    INSERT INTO receipt_monthly_summaries (
      user_id, 
      year, 
      month, 
      category_id, 
      receipt_count, 
      total_amount
    )
    VALUES (
      NEW.user_id,
      EXTRACT(YEAR FROM NEW.receipt_date),
      EXTRACT(MONTH FROM NEW.receipt_date),
      NEW.category_id,
      1,
      NEW.amount
    )
    ON CONFLICT (user_id, year, month, category_id)
    DO UPDATE SET
      receipt_count = receipt_monthly_summaries.receipt_count + 1,
      total_amount = receipt_monthly_summaries.total_amount + NEW.amount,
      updated_at = NOW();
      
  -- Handle updates
  ELSIF TG_OP = 'UPDATE' THEN
    -- If date or category changed, update both old and new summaries
    IF OLD.receipt_date != NEW.receipt_date OR OLD.category_id != NEW.category_id THEN
      -- Decrease old summary
      UPDATE receipt_monthly_summaries
      SET 
        receipt_count = receipt_count - 1,
        total_amount = total_amount - OLD.amount
      WHERE 
        user_id = OLD.user_id
        AND year = EXTRACT(YEAR FROM OLD.receipt_date)
        AND month = EXTRACT(MONTH FROM OLD.receipt_date)
        AND category_id = OLD.category_id;
      
      -- Increase new summary
      INSERT INTO receipt_monthly_summaries (
        user_id, 
        year, 
        month, 
        category_id, 
        receipt_count, 
        total_amount
      )
      VALUES (
        NEW.user_id,
        EXTRACT(YEAR FROM NEW.receipt_date),
        EXTRACT(MONTH FROM NEW.receipt_date),
        NEW.category_id,
        1,
        NEW.amount
      )
      ON CONFLICT (user_id, year, month, category_id)
      DO UPDATE SET
        receipt_count = receipt_monthly_summaries.receipt_count + 1,
        total_amount = receipt_monthly_summaries.total_amount + NEW.amount,
        updated_at = NOW();
    -- If only amount changed
    ELSIF OLD.amount != NEW.amount THEN
      UPDATE receipt_monthly_summaries
      SET total_amount = total_amount - OLD.amount + NEW.amount
      WHERE 
        user_id = NEW.user_id
        AND year = EXTRACT(YEAR FROM NEW.receipt_date)
        AND month = EXTRACT(MONTH FROM NEW.receipt_date)
        AND category_id = NEW.category_id;
    END IF;
    
  -- Handle deletes
  ELSIF TG_OP = 'DELETE' THEN
    UPDATE receipt_monthly_summaries
    SET 
      receipt_count = receipt_count - 1,
      total_amount = total_amount - OLD.amount
    WHERE 
      user_id = OLD.user_id
      AND year = EXTRACT(YEAR FROM OLD.receipt_date)
      AND month = EXTRACT(MONTH FROM OLD.receipt_date)
      AND category_id = OLD.category_id;
  END IF;
  
  -- Return appropriate value based on operation
  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  ELSE
    RETURN NEW;
  END IF;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for monthly summary updates
CREATE TRIGGER update_monthly_summary_trigger
AFTER INSERT OR UPDATE OR DELETE ON receipt_receipts
FOR EACH ROW
EXECUTE FUNCTION update_monthly_summary();

-- Function to suggest category based on keywords
CREATE OR REPLACE FUNCTION suggest_category(
  p_store_name TEXT,
  p_user_id UUID DEFAULT NULL
)
RETURNS TABLE(
  category_id INTEGER,
  category_code TEXT,
  category_name TEXT,
  confidence DECIMAL(3,2)
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    cr.category_id,
    ec.code,
    ec.name,
    CASE 
      WHEN cr.user_id IS NOT NULL THEN 0.95  -- User-specific rules have higher confidence
      ELSE 0.80  -- Global rules
    END as confidence
  FROM receipt_category_rules cr
  JOIN receipt_expense_categories ec ON cr.category_id = ec.id
  WHERE 
    cr.is_active = true
    AND (cr.user_id IS NULL OR cr.user_id = p_user_id)
    AND lower(p_store_name) LIKE '%' || lower(cr.keyword) || '%'
  ORDER BY 
    cr.user_id NULLS LAST,  -- User rules first
    cr.priority DESC,
    LENGTH(cr.keyword) DESC  -- Longer matches first
  LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Function to get receipt stats
CREATE OR REPLACE FUNCTION get_receipt_stats(
  p_user_id UUID,
  p_start_date DATE,
  p_end_date DATE
)
RETURNS TABLE(
  total_amount DECIMAL(12,2),
  receipt_count BIGINT,
  category_breakdown JSONB
) AS $$
BEGIN
  RETURN QUERY
  WITH stats AS (
    SELECT 
      COALESCE(SUM(r.amount), 0) as total,
      COUNT(*) as count
    FROM receipt_receipts r
    WHERE 
      r.user_id = p_user_id
      AND r.receipt_date BETWEEN p_start_date AND p_end_date
      AND r.deleted_at IS NULL
  ),
  categories AS (
    SELECT 
      jsonb_agg(
        jsonb_build_object(
          'category_id', ec.id,
          'category_code', ec.code,
          'category_name', ec.name,
          'amount', COALESCE(SUM(r.amount), 0),
          'count', COUNT(r.id),
          'percentage', ROUND(
            CASE 
              WHEN (SELECT total FROM stats) > 0 
              THEN (SUM(r.amount) / (SELECT total FROM stats) * 100)
              ELSE 0
            END, 2
          )
        ) ORDER BY SUM(r.amount) DESC
      ) as breakdown
    FROM receipt_expense_categories ec
    LEFT JOIN receipt_receipts r ON 
      r.category_id = ec.id 
      AND r.user_id = p_user_id
      AND r.receipt_date BETWEEN p_start_date AND p_end_date
      AND r.deleted_at IS NULL
    GROUP BY ec.id, ec.code, ec.name
    HAVING COUNT(r.id) > 0
  )
  SELECT 
    s.total,
    s.count,
    c.breakdown
  FROM stats s, categories c;
END;
$$ LANGUAGE plpgsql;