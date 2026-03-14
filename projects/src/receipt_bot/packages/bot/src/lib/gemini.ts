import { GoogleGenerativeAI } from '@google/generative-ai';
import dotenv from 'dotenv';
import { z } from 'zod';
import { EXPENSE_CATEGORIES } from './categories';

dotenv.config();

if (!process.env.GEMINI_API_KEY) {
  throw new Error('Missing GEMINI_API_KEY environment variable');
}

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

// Schema for receipt OCR result with category
const ReceiptAnalysisSchema = z.object({
  storeName: z.string().nullable(),
  totalAmount: z.number().nullable(),
  taxAmount: z.number().nullable(),
  date: z.string().nullable(), // YYYY-MM-DD format
  items: z.array(z.string()).nullable(),
  category: z.object({
    code: z.string(),
    name: z.string(),
    confidence: z.number().min(0).max(1),
    reason: z.string(),
  }),
  ocrConfidence: z.number().min(0).max(1),
});

export type ReceiptAnalysis = z.infer<typeof ReceiptAnalysisSchema>;

export async function analyzeReceiptWithCategory(imageBuffer: Buffer): Promise<ReceiptAnalysis> {
  try {
    const model = genAI.getGenerativeModel({ model: 'gemini-1.5-flash' });

    // カテゴリーリストを作成
    const categoryList = EXPENSE_CATEGORIES.ALL
      .map(c => `- ${c.code}: ${c.name}（${c.description}）`)
      .join('\n');

    const prompt = `このレシート画像を解析して、以下の処理を行ってください：

1. レシート情報の抽出:
   - 店舗名
   - 合計金額（税込）
   - 税額（わかる場合）
   - 日付（YYYY-MM-DD形式）
   - 主な購入品目（最大5つ）

2. 経費科目の自動分類:
   以下のfreee標準の経費科目から最も適切なものを選択してください：

${categoryList}

判断基準:
- 店舗の業種・種類から推測
- 購入品目の内容から判断
- 一般的な経費処理の慣習に従う
- 不明な場合は「雑費（MISC）」を選択

JSON形式で回答してください：
{
  "storeName": "店舗名",
  "totalAmount": 1234,
  "taxAmount": 123,
  "date": "2024-01-01",
  "items": ["商品1", "商品2"],
  "category": {
    "code": "SUPPLIES",
    "name": "消耗品費",
    "confidence": 0.85,
    "reason": "コンビニでの日用品購入のため"
  },
  "ocrConfidence": 0.95
}

画像が不鮮明だったり、レシートでない場合は、該当する項目をnullにして、ocrConfidenceを低く設定してください。`;

    const imagePart = {
      inlineData: {
        data: imageBuffer.toString('base64'),
        mimeType: 'image/jpeg',
      },
    };

    const result = await model.generateContent([prompt, imagePart]);
    const response = await result.response;
    const text = response.text();

    // Extract JSON from the response
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      throw new Error('No JSON found in response');
    }

    const jsonData = JSON.parse(jsonMatch[0]);
    
    // 数値フィールドを適切に変換
    if (jsonData.totalAmount !== null && typeof jsonData.totalAmount === 'string') {
      jsonData.totalAmount = parseFloat(jsonData.totalAmount);
    }
    if (jsonData.taxAmount !== null && typeof jsonData.taxAmount === 'string') {
      jsonData.taxAmount = parseFloat(jsonData.taxAmount);
    }
    if (jsonData.category && typeof jsonData.category.confidence === 'string') {
      jsonData.category.confidence = parseFloat(jsonData.category.confidence);
    }
    if (typeof jsonData.ocrConfidence === 'string') {
      jsonData.ocrConfidence = parseFloat(jsonData.ocrConfidence);
    }
    
    const validatedData = ReceiptAnalysisSchema.parse(jsonData);

    return validatedData;
  } catch (error) {
    console.error('Error analyzing receipt:', error);
    
    // Return a default response with MISC category
    return {
      storeName: null,
      totalAmount: null,
      taxAmount: null,
      date: null,
      items: null,
      category: {
        code: 'MISC',
        name: '雑費',
        confidence: 0.1,
        reason: '画像解析エラーのため自動分類できませんでした',
      },
      ocrConfidence: 0,
    };
  }
}

// Legacy functions for backward compatibility
export type ReceiptData = {
  storeName: string | null;
  totalAmount: number | null;
  taxAmount: number | null;
  date: string | null;
  items: string[] | null;
  confidence: number;
};

export type CategorySuggestion = {
  category: string;
  confidence: number;
  reason: string;
};

export async function analyzeReceiptImage(imageBuffer: Buffer): Promise<ReceiptData> {
  const analysis = await analyzeReceiptWithCategory(imageBuffer);
  return {
    storeName: analysis.storeName,
    totalAmount: analysis.totalAmount,
    taxAmount: analysis.taxAmount,
    date: analysis.date,
    items: analysis.items,
    confidence: analysis.ocrConfidence,
  };
}

export async function suggestCategoryFromReceipt(
  receiptData: ReceiptData,
  categories: { code: string; name: string; description: string }[]
): Promise<CategorySuggestion | null> {
  // This function is now deprecated - use analyzeReceiptWithCategory instead
  // But we'll keep it for backward compatibility
  
  if (!receiptData.storeName && (!receiptData.items || receiptData.items.length === 0)) {
    return {
      category: 'MISC',
      confidence: 0.1,
      reason: 'レシート情報が不足しているため',
    };
  }

  try {
    const model = genAI.getGenerativeModel({ model: 'gemini-1.5-flash' });

    const categoryList = categories
      .map(c => `- ${c.code}: ${c.name}（${c.description}）`)
      .join('\n');

    const prompt = `以下のレシート情報から最も適切な経費科目を選んでください：

店舗名: ${receiptData.storeName || '不明'}
購入品目: ${receiptData.items?.join(', ') || '不明'}
金額: ${receiptData.totalAmount ? `¥${receiptData.totalAmount}` : '不明'}
日付: ${receiptData.date || '不明'}

freee標準の経費科目から選択してください:
${categoryList}

判断基準:
1. 店舗の業種・種類から推測
2. 購入品目の内容から判断
3. 一般的な経費処理の慣習に従う
4. 不明な場合は「雑費（MISC）」を選択

回答形式（JSON）:
{
  "category": "SUPPLIES",
  "confidence": 0.85,
  "reason": "文房具店での購入のため"
}`;

    const result = await model.generateContent(prompt);
    const response = await result.response;
    const text = response.text();

    // Extract JSON from the response
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      throw new Error('No JSON found in response');
    }

    const jsonData = JSON.parse(jsonMatch[0]);
    const validatedData = z.object({
      category: z.string(),
      confidence: z.number().min(0).max(1),
      reason: z.string(),
    }).parse(jsonData);

    return validatedData;
  } catch (error) {
    console.error('Error suggesting category:', error);
    return {
      category: 'MISC',
      confidence: 0.1,
      reason: 'カテゴリー推測エラー',
    };
  }
}