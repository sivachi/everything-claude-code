import { createClient } from '@supabase/supabase-js';
import dotenv from 'dotenv';

dotenv.config();

if (!process.env.SUPABASE_URL || !process.env.SUPABASE_SERVICE_KEY) {
  throw new Error('Missing Supabase environment variables');
}

export const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY,
  {
    auth: {
      autoRefreshToken: false,
      persistSession: false,
    },
  }
);

export interface User {
  id: string;
  discord_id: string;
  discord_username: string;
  email?: string;
  default_category_id?: number;
  created_at: string;
  updated_at: string;
}

export interface ExpenseCategory {
  id: number;
  code: string;
  name: string;
  description?: string;
  parent_id?: number;
  is_active: boolean;
  sort_order: number;
  created_at: string;
}

export interface Receipt {
  id: string;
  user_id: string;
  discord_user_id: string;
  image_url: string;
  thumbnail_url?: string;
  ocr_raw_text?: string;
  store_name?: string;
  amount?: number;
  tax_amount?: number;
  receipt_date?: string;
  category_id?: number;
  category_confidence?: number;
  is_category_confirmed: boolean;
  notes?: string;
  created_at: string;
  updated_at: string;
  deleted_at?: string;
  category?: ExpenseCategory;
  tags?: Tag[];
}

export interface Tag {
  id: number;
  user_id: string;
  name: string;
  color: string;
  description?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CategoryRule {
  id: number;
  user_id?: string;
  keyword: string;
  category_id: number;
  priority: number;
  is_active: boolean;
  created_at: string;
}

export async function getOrCreateUser(discordId: string, username: string): Promise<User> {
  const { data, error } = await supabase.rpc('get_or_create_user', {
    p_discord_id: discordId,
    p_discord_username: username,
  });

  if (error) {
    throw new Error(`Failed to get or create user: ${error.message}`);
  }

  // Fetch the full user data
  const { data: user, error: fetchError } = await supabase
    .from('receipt_users')
    .select('*')
    .eq('id', data)
    .single();

  if (fetchError || !user) {
    throw new Error('Failed to fetch user data');
  }

  return user;
}

export async function getCategories(): Promise<ExpenseCategory[]> {
  const { data, error } = await supabase
    .from('receipt_expense_categories')
    .select('*')
    .eq('is_active', true)
    .order('sort_order');

  if (error) {
    throw new Error(`Failed to fetch categories: ${error.message}`);
  }

  return data || [];
}

export async function uploadReceiptImage(
  userId: string,
  file: Buffer,
  fileName: string
): Promise<{ url: string; path: string }> {
  const path = `${userId}/${Date.now()}-${fileName}`;
  
  const { data, error } = await supabase.storage
    .from('receipts')
    .upload(path, file, {
      contentType: 'image/jpeg',
      upsert: false,
    });

  if (error) {
    throw new Error(`Failed to upload image: ${error.message}`);
  }

  const { data: { publicUrl } } = supabase.storage
    .from('receipts')
    .getPublicUrl(path);

  return { url: publicUrl, path };
}

export async function createReceipt(receipt: Partial<Receipt>): Promise<Receipt> {
  const { data, error } = await supabase
    .from('receipt_receipts')
    .insert(receipt)
    .select('*, category:receipt_expense_categories(*)')
    .single();

  if (error) {
    throw new Error(`Failed to create receipt: ${error.message}`);
  }

  return data;
}

export async function getUserTags(userId: string): Promise<Tag[]> {
  const { data, error } = await supabase
    .from('receipt_tags')
    .select('*')
    .eq('user_id', userId)
    .eq('is_active', true)
    .order('name');

  if (error) {
    throw new Error(`Failed to fetch tags: ${error.message}`);
  }

  return data || [];
}

export async function getOrCreateTag(userId: string, tagName: string, color?: string): Promise<Tag> {
  const { data, error } = await supabase.rpc('get_or_create_tag', {
    p_user_id: userId,
    p_tag_name: tagName,
    p_color: color || '#808080',
  });

  if (error) {
    throw new Error(`Failed to get or create tag: ${error.message}`);
  }

  // Fetch the full tag data
  const { data: tag, error: fetchError } = await supabase
    .from('receipt_tags')
    .select('*')
    .eq('id', data)
    .single();

  if (fetchError || !tag) {
    throw new Error('Failed to fetch tag data');
  }

  return tag;
}

export async function addTagToReceipt(receiptId: string, tagId: number): Promise<boolean> {
  const { data, error } = await supabase.rpc('add_tag_to_receipt', {
    p_receipt_id: receiptId,
    p_tag_id: tagId,
  });

  if (error) {
    throw new Error(`Failed to add tag to receipt: ${error.message}`);
  }

  return data;
}

export async function removeTagFromReceipt(receiptId: string, tagId: number): Promise<boolean> {
  const { data, error } = await supabase.rpc('remove_tag_from_receipt', {
    p_receipt_id: receiptId,
    p_tag_id: tagId,
  });

  if (error) {
    throw new Error(`Failed to remove tag from receipt: ${error.message}`);
  }

  return data;
}

export async function getReceiptWithTags(receiptId: string): Promise<Receipt> {
  const { data, error } = await supabase
    .from('receipt_receipts')
    .select(`
      *,
      category:receipt_expense_categories(*),
      tags:receipt_receipt_tags(tag:receipt_tags(*))
    `)
    .eq('id', receiptId)
    .single();

  if (error) {
    throw new Error(`Failed to fetch receipt with tags: ${error.message}`);
  }

  // Flatten the tags structure
  if (data && data.tags) {
    data.tags = data.tags.map((rt: any) => rt.tag);
  }

  return data;
}

export async function getReceiptById(receiptId: string): Promise<Receipt | null> {
  const { data, error } = await supabase
    .from('receipt_receipts')
    .select('*')
    .eq('id', receiptId)
    .is('deleted_at', null)
    .single();

  if (error) {
    console.error(`Failed to fetch receipt: ${error.message}`);
    return null;
  }

  return data;
}

export async function deleteReceipt(receiptId: string): Promise<void> {
  const { error } = await supabase
    .from('receipt_receipts')
    .delete()
    .eq('id', receiptId);

  if (error) {
    throw new Error(`Failed to delete receipt: ${error.message}`);
  }
}

export async function updateReceipt(
  id: string,
  updates: Partial<Receipt>
): Promise<Receipt> {
  const { data, error } = await supabase
    .from('receipt_receipts')
    .update(updates)
    .eq('id', id)
    .select('*, category:receipt_expense_categories(*)')
    .single();

  if (error) {
    throw new Error(`Failed to update receipt: ${error.message}`);
  }

  return data;
}

export async function getReceipts(
  userId: string,
  options: {
    month?: string;
    categoryCode?: string;
    limit?: number;
    offset?: number;
  } = {}
): Promise<{ receipts: Receipt[]; total: number }> {
  let query = supabase
    .from('receipt_receipts')
    .select('*, category:receipt_expense_categories(*)', { count: 'exact' })
    .eq('user_id', userId)
    .is('deleted_at', null)
    .order('receipt_date', { ascending: false });

  if (options.month) {
    const [year, month] = options.month.split('-');
    const startDate = `${year}-${month}-01`;
    const endDate = new Date(parseInt(year), parseInt(month), 0).toISOString().split('T')[0];
    query = query.gte('receipt_date', startDate).lte('receipt_date', endDate);
  }

  if (options.categoryCode) {
    const { data: category } = await supabase
      .from('receipt_expense_categories')
      .select('id')
      .eq('code', options.categoryCode)
      .single();
    
    if (category) {
      query = query.eq('category_id', category.id);
    }
  }

  if (options.limit) {
    query = query.limit(options.limit);
  }

  if (options.offset) {
    query = query.range(options.offset, options.offset + (options.limit || 10) - 1);
  }

  const { data, error, count } = await query;

  if (error) {
    throw new Error(`Failed to fetch receipts: ${error.message}`);
  }

  return { receipts: data || [], total: count || 0 };
}

export async function suggestCategory(
  storeName: string,
  userId?: string
): Promise<{ categoryId: number; categoryCode: string; categoryName: string; confidence: number } | null> {
  const { data, error } = await supabase.rpc('suggest_category', {
    p_store_name: storeName,
    p_user_id: userId,
  });

  if (error) {
    console.error('Failed to suggest category:', error);
    return null;
  }

  if (!data || data.length === 0) {
    return null;
  }

  const suggestion = data[0];
  return {
    categoryId: suggestion.category_id,
    categoryCode: suggestion.category_code,
    categoryName: suggestion.category_name,
    confidence: parseFloat(suggestion.confidence),
  };
}