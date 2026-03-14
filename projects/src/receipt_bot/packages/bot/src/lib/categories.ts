// freee標準の経費勘定科目
export const EXPENSE_CATEGORIES = {
  // よく使われる経費科目（Discord選択肢用）
  COMMON: [
    { name: '消耗品費', value: 'SUPPLIES', description: '10万円未満の消耗品、備品など' },
    { name: '事務用品費', value: 'OFFICE_SUPPLIES', description: '文房具、事務用消耗品など' },
    { name: '旅費交通費', value: 'TRAVEL', description: '電車賃、バス代、タクシー代、出張費など' },
    { name: '会議費', value: 'MEETING', description: '会議・打ち合わせの飲食代など' },
    { name: '交際費', value: 'ENTERTAINMENT', description: '接待交際費、お中元・お歳暮など' },
    { name: '新聞図書費', value: 'BOOKS', description: '新聞、書籍、雑誌、資料など' },
    { name: '通信費', value: 'COMMUNICATION', description: '電話代、インターネット代、郵送費など' },
    { name: '水道光熱費', value: 'UTILITIES', description: '電気、ガス、水道代など' },
    { name: '支払手数料', value: 'COMMISSION', description: '振込手数料、各種手数料など' },
    { name: '車両費', value: 'VEHICLE', description: 'ガソリン代、駐車場代、車両維持費など' },
    { name: '地代家賃', value: 'RENT', description: '事務所・店舗の家賃、地代など' },
    { name: '広告宣伝費', value: 'ADVERTISING', description: '広告、宣伝活動費用' },
    { name: '外注費', value: 'OUTSOURCING', description: '外部委託費用' },
    { name: '修繕費', value: 'REPAIR', description: '設備・機器の修理費用' },
    { name: '雑費', value: 'MISC', description: 'その他の少額経費' },
  ],

  // 全ての経費科目（データベース用）
  ALL: [
    // 人件費系
    { code: 'TRAINING', name: '研修費', description: '社員研修、セミナー参加費など' },
    { code: 'WELFARE', name: '福利厚生費', description: '社員の福利厚生に関する費用' },
    { code: 'RECRUITMENT', name: '採用教育費', description: '採用活動、新人教育に関する費用' },
    
    // 営業・販売系
    { code: 'OUTSOURCING', name: '外注費', description: '外部委託費用' },
    { code: 'SHIPPING', name: '荷造運賃', description: '商品の梱包・配送費用' },
    { code: 'ADVERTISING', name: '広告宣伝費', description: '広告、宣伝活動費用' },
    { code: 'ENTERTAINMENT', name: '交際費', description: '接待交際費、お中元・お歳暮など' },
    { code: 'MEETING', name: '会議費', description: '会議・打ち合わせの飲食代など' },
    { code: 'TRAVEL', name: '旅費交通費', description: '電車賃、バス代、タクシー代、出張費など' },
    { code: 'COMMUNICATION', name: '通信費', description: '電話代、インターネット代、郵送費など' },
    { code: 'SALES_COMMISSION', name: '販売手数料', description: '販売に関する手数料' },
    { code: 'PROMOTION', name: '販売促進費', description: '販促キャンペーン、ノベルティなど' },
    
    // 事務・管理系
    { code: 'SUPPLIES', name: '消耗品費', description: '10万円未満の消耗品、備品など' },
    { code: 'OFFICE_SUPPLIES', name: '事務用品費', description: '文房具、事務用消耗品など' },
    { code: 'REPAIR', name: '修繕費', description: '設備・機器の修理費用' },
    { code: 'UTILITIES', name: '水道光熱費', description: '電気、ガス、水道代など' },
    { code: 'BOOKS', name: '新聞図書費', description: '新聞、書籍、雑誌、資料など' },
    { code: 'MEMBERSHIP', name: '諸会費', description: '各種団体の会費、年会費など' },
    { code: 'COMMISSION', name: '支払手数料', description: '振込手数料、各種手数料など' },
    { code: 'VEHICLE', name: '車両費', description: 'ガソリン代、駐車場代、車両維持費など' },
    
    // 不動産・賃貸系
    { code: 'RENT', name: '地代家賃', description: '事務所・店舗の家賃、地代など' },
    { code: 'RENTAL', name: '賃借料', description: '機器・設備のレンタル料など' },
    { code: 'LEASE', name: 'リース料', description: 'リース契約に基づく支払い' },
    
    // その他
    { code: 'INSURANCE', name: '保険料', description: '各種保険の保険料' },
    { code: 'TAX', name: '租税公課', description: '事業税、固定資産税など（法人税等除く）' },
    { code: 'PROFESSIONAL', name: '支払報酬料', description: '弁護士、税理士などへの報酬' },
    { code: 'DONATION', name: '寄付金', description: '寄付金、協賛金など' },
    { code: 'FUEL', name: '燃料費', description: '灯油、ガスなどの燃料費' },
    { code: 'R_AND_D', name: '研究開発費', description: '研究開発に関する費用' },
    { code: 'MISC', name: '雑費', description: 'その他の少額経費' },
    { code: 'MANAGEMENT', name: '管理諸費', description: '管理部門の諸経費' },
  ]
};

// Discord選択肢の最大数（25個）に収まるように、2つのグループに分ける
export const CATEGORY_GROUPS = {
  COMMON: EXPENSE_CATEGORIES.COMMON.slice(0, 15),
  OTHERS: EXPENSE_CATEGORIES.COMMON.slice(15),
};