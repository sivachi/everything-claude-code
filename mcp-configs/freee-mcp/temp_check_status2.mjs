import fs from 'fs';

const token = JSON.parse(fs.readFileSync(new URL('.token.json', import.meta.url), 'utf-8'));
const accessToken = token.access_token;
const companyId = 12342495;

async function api(endpoint, params = {}) {
  const url = new URL('https://api.freee.co.jp/api/1' + endpoint);
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
  }
  const res = await fetch(url.toString(), { headers: { Authorization: 'Bearer ' + accessToken } });
  return res.json();
}

// Get full deal details
console.log('=== 収入取引の詳細（2024年7月〜2026年3月） ===');
const deals = await api('/deals', { company_id: companyId, type: 'income', start_issue_date: '2024-07-01', end_issue_date: '2026-03-31', limit: 100 });
if (deals.deals) {
  deals.deals.forEach(d => {
    console.log(JSON.stringify(d, null, 2));
    console.log('---');
  });
  console.log('総件数:', deals.deals.length);
} else {
  console.log(JSON.stringify(deals, null, 2));
}

// Also check PL by month
console.log('\n=== 月次PL（売上関連）2025年度 ===');
for (let month = 1; month <= 3; month++) {
  const pl = await api('/reports/trial_pl', { company_id: companyId, fiscal_year: 2025, start_month: month, end_month: month });
  if (pl.trial_pl && pl.trial_pl.balances) {
    const revenue = pl.trial_pl.balances.filter(b => b.account_item_name && (b.account_item_name.includes('売上') || b.account_item_name.includes('収入')));
    console.log(`${month}月:`, revenue.map(r => r.account_item_name + '=' + r.closing_balance));
  }
}

console.log('\n=== 月次PL（売上関連）2024年度後半 ===');
for (let month = 7; month <= 12; month++) {
  const pl = await api('/reports/trial_pl', { company_id: companyId, fiscal_year: 2024, start_month: month, end_month: month });
  if (pl.trial_pl && pl.trial_pl.balances) {
    const revenue = pl.trial_pl.balances.filter(b => b.account_item_name && (b.account_item_name.includes('売上') || b.account_item_name.includes('収入')));
    console.log(`${month}月:`, revenue.map(r => r.account_item_name + '=' + r.closing_balance));
  }
}
