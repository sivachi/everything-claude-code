-- Storage バケットが存在しない場合は作成
DO $$ 
BEGIN
    -- Check if bucket exists
    IF NOT EXISTS (SELECT 1 FROM storage.buckets WHERE id = 'receipts') THEN
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
    END IF;
END $$;