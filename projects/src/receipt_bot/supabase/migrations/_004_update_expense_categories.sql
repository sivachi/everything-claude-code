-- 既存のcategory_rulesを削除してから、カテゴリを削除
DELETE FROM receipt_category_rules WHERE user_id IS NULL;
DELETE FROM receipt_expense_categories;

-- freee標準の経費勘定科目を挿入
INSERT INTO receipt_expense_categories (code, name, description, sort_order) VALUES
  -- 人件費系
  ('TRAINING', '研修費', '社員研修、セミナー参加費など', 10),
  ('WELFARE', '福利厚生費', '社員の福利厚生に関する費用', 20),
  ('RECRUITMENT', '採用教育費', '採用活動、新人教育に関する費用', 30),
  
  -- 営業・販売系
  ('OUTSOURCING', '外注費', '外部委託費用', 40),
  ('SHIPPING', '荷造運賃', '商品の梱包・配送費用', 50),
  ('ADVERTISING', '広告宣伝費', '広告、宣伝活動費用', 60),
  ('ENTERTAINMENT', '交際費', '接待交際費、お中元・お歳暮など', 70),
  ('MEETING', '会議費', '会議・打ち合わせの飲食代など', 80),
  ('TRAVEL', '旅費交通費', '電車賃、バス代、タクシー代、出張費など', 90),
  ('COMMUNICATION', '通信費', '電話代、インターネット代、郵送費など', 100),
  ('SALES_COMMISSION', '販売手数料', '販売に関する手数料', 110),
  ('PROMOTION', '販売促進費', '販促キャンペーン、ノベルティなど', 120),
  
  -- 事務・管理系
  ('SUPPLIES', '消耗品費', '10万円未満の消耗品、備品など', 130),
  ('OFFICE_SUPPLIES', '事務用品費', '文房具、事務用消耗品など', 140),
  ('REPAIR', '修繕費', '設備・機器の修理費用', 150),
  ('UTILITIES', '水道光熱費', '電気、ガス、水道代など', 160),
  ('BOOKS', '新聞図書費', '新聞、書籍、雑誌、資料など', 170),
  ('MEMBERSHIP', '諸会費', '各種団体の会費、年会費など', 180),
  ('COMMISSION', '支払手数料', '振込手数料、各種手数料など', 190),
  ('VEHICLE', '車両費', 'ガソリン代、駐車場代、車両維持費など', 200),
  
  -- 不動産・賃貸系
  ('RENT', '地代家賃', '事務所・店舗の家賃、地代など', 210),
  ('RENTAL', '賃借料', '機器・設備のレンタル料など', 220),
  ('LEASE', 'リース料', 'リース契約に基づく支払い', 230),
  
  -- その他
  ('INSURANCE', '保険料', '各種保険の保険料', 240),
  ('TAX', '租税公課', '事業税、固定資産税など（法人税等除く）', 250),
  ('PROFESSIONAL', '支払報酬料', '弁護士、税理士などへの報酬', 260),
  ('DONATION', '寄付金', '寄付金、協賛金など', 270),
  ('FUEL', '燃料費', '灯油、ガスなどの燃料費', 280),
  ('R_AND_D', '研究開発費', '研究開発に関する費用', 290),
  ('MISC', '雑費', 'その他の少額経費', 300),
  ('MANAGEMENT', '管理諸費', '管理部門の諸経費', 310);

-- 新しいグローバルルールを挿入
INSERT INTO receipt_category_rules (keyword, category_id, priority) VALUES
  -- コンビニ・スーパー
  ('コンビニ', (SELECT id FROM receipt_expense_categories WHERE code = 'SUPPLIES'), 100),
  ('セブンイレブン', (SELECT id FROM receipt_expense_categories WHERE code = 'SUPPLIES'), 100),
  ('ファミリーマート', (SELECT id FROM receipt_expense_categories WHERE code = 'SUPPLIES'), 100),
  ('ローソン', (SELECT id FROM receipt_expense_categories WHERE code = 'SUPPLIES'), 100),
  ('ミニストップ', (SELECT id FROM receipt_expense_categories WHERE code = 'SUPPLIES'), 100),
  ('スーパー', (SELECT id FROM receipt_expense_categories WHERE code = 'SUPPLIES'), 90),
  
  -- 文房具
  ('文房具', (SELECT id FROM receipt_expense_categories WHERE code = 'OFFICE_SUPPLIES'), 100),
  ('文具', (SELECT id FROM receipt_expense_categories WHERE code = 'OFFICE_SUPPLIES'), 100),
  ('ロフト', (SELECT id FROM receipt_expense_categories WHERE code = 'OFFICE_SUPPLIES'), 90),
  ('東急ハンズ', (SELECT id FROM receipt_expense_categories WHERE code = 'SUPPLIES'), 90),
  
  -- 交通
  ('JR', (SELECT id FROM receipt_expense_categories WHERE code = 'TRAVEL'), 100),
  ('電車', (SELECT id FROM receipt_expense_categories WHERE code = 'TRAVEL'), 100),
  ('タクシー', (SELECT id FROM receipt_expense_categories WHERE code = 'TRAVEL'), 100),
  ('バス', (SELECT id FROM receipt_expense_categories WHERE code = 'TRAVEL'), 100),
  ('新幹線', (SELECT id FROM receipt_expense_categories WHERE code = 'TRAVEL'), 100),
  ('航空', (SELECT id FROM receipt_expense_categories WHERE code = 'TRAVEL'), 100),
  ('ホテル', (SELECT id FROM receipt_expense_categories WHERE code = 'TRAVEL'), 95),
  
  -- 飲食
  ('レストラン', (SELECT id FROM receipt_expense_categories WHERE code = 'MEETING'), 90),
  ('カフェ', (SELECT id FROM receipt_expense_categories WHERE code = 'MEETING'), 90),
  ('スターバックス', (SELECT id FROM receipt_expense_categories WHERE code = 'MEETING'), 90),
  ('ドトール', (SELECT id FROM receipt_expense_categories WHERE code = 'MEETING'), 90),
  ('居酒屋', (SELECT id FROM receipt_expense_categories WHERE code = 'ENTERTAINMENT'), 95),
  
  -- 書籍
  ('書店', (SELECT id FROM receipt_expense_categories WHERE code = 'BOOKS'), 100),
  ('本屋', (SELECT id FROM receipt_expense_categories WHERE code = 'BOOKS'), 100),
  ('紀伊國屋', (SELECT id FROM receipt_expense_categories WHERE code = 'BOOKS'), 100),
  ('ジュンク堂', (SELECT id FROM receipt_expense_categories WHERE code = 'BOOKS'), 100),
  ('Amazon', (SELECT id FROM receipt_expense_categories WHERE code = 'BOOKS'), 80),
  
  -- ガソリン
  ('ガソリン', (SELECT id FROM receipt_expense_categories WHERE code = 'VEHICLE'), 100),
  ('エネオス', (SELECT id FROM receipt_expense_categories WHERE code = 'VEHICLE'), 100),
  ('出光', (SELECT id FROM receipt_expense_categories WHERE code = 'VEHICLE'), 100),
  ('駐車場', (SELECT id FROM receipt_expense_categories WHERE code = 'VEHICLE'), 100),
  
  -- 通信
  ('ドコモ', (SELECT id FROM receipt_expense_categories WHERE code = 'COMMUNICATION'), 100),
  ('au', (SELECT id FROM receipt_expense_categories WHERE code = 'COMMUNICATION'), 100),
  ('ソフトバンク', (SELECT id FROM receipt_expense_categories WHERE code = 'COMMUNICATION'), 100),
  ('郵便', (SELECT id FROM receipt_expense_categories WHERE code = 'COMMUNICATION'), 100),
  
  -- 光熱費
  ('電気', (SELECT id FROM receipt_expense_categories WHERE code = 'UTILITIES'), 100),
  ('ガス', (SELECT id FROM receipt_expense_categories WHERE code = 'UTILITIES'), 100),
  ('水道', (SELECT id FROM receipt_expense_categories WHERE code = 'UTILITIES'), 100);