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

// Get income deals for recent months
console.log('=== 収入取引（2025年1月〜3月） ===');
const deals = await api('/deals', { company_id: companyId, type: 'income', start_issue_date: '2025-01-01', end_issue_date: '2025-03-31', limit: 100 });
if (deals.deals) {
  deals.deals.forEach(d => {
    const details = (d.details || []).map(det => det.account_item_name + ':' + det.amount).join(', ');
    console.log(d.issue_date + ' | ' + details + ' | partner: ' + (d.partner ? d.partner.name : 'N/A'));
  });
  console.log('件数:', deals.deals.length);
} else {
  console.log(JSON.stringify(deals, null, 2));
}

console.log('');
console.log('=== 収入取引（2024年10月〜12月） ===');
const deals2 = await api('/deals', { company_id: companyId, type: 'income', start_issue_date: '2024-10-01', end_issue_date: '2024-12-31', limit: 100 });
if (deals2.deals) {
  deals2.deals.forEach(d => {
    const details = (d.details || []).map(det => det.account_item_name + ':' + det.amount).join(', ');
    console.log(d.issue_date + ' | ' + details + ' | partner: ' + (d.partner ? d.partner.name : 'N/A'));
  });
  console.log('件数:', deals2.deals.length);
}

console.log('');
console.log('=== 請求書一覧（2024年10月〜2025年3月） ===');
const invoices = await api('/invoices', { company_id: companyId, start_issue_date: '2024-10-01', end_issue_date: '2025-03-31' });
if (invoices.invoices) {
  invoices.invoices.forEach(inv => {
    console.log(inv.issue_date + ' | ' + inv.invoice_number + ' | ' + inv.total_amount + ' | ' + inv.invoice_status + ' | partner: ' + (inv.partner_name || 'N/A'));
  });
  console.log('件数:', invoices.invoices.length);
} else {
  console.log(JSON.stringify(invoices, null, 2));
}
