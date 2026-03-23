
import fs from 'fs';
import path from 'path';

const CLIENT_ID = "668055678584424";
const CLIENT_SECRET = "0_hED5SppgVgBuRXPlcYIkEgyVFMJQAMgDv3lLxWj7LIr98foBFVptn9cr02OtbLdOP3SaGFa8F98r7CiOIKGg";
const TOKEN_PATH = "/Users/tadaakikurata/works/freee-mcp/.token.json";

function loadToken() {
    return JSON.parse(fs.readFileSync(TOKEN_PATH, 'utf-8'));
}

async function getAccessToken() {
    let token = loadToken();
    return token.access_token;
}

async function freeeAPI(endpoint, params = {}) {
    const accessToken = await getAccessToken();
    const url = new URL(`https://api.freee.co.jp/api/1${endpoint}`);
    for (const [k, v] of Object.entries(params)) {
        if (v !== undefined && v !== null) url.searchParams.set(k, v);
    }
    const res = await fetch(url.toString(), {
        headers: { Authorization: `Bearer ${accessToken}` },
    });
    return res.json();
}

async function main() {
    try {
        const companyId = 12342495;
        const pl = await freeeAPI("/reports/trial_pl", { company_id: companyId, fiscal_year: 2025 });
        const balances = pl.trial_pl.balances || [];

        console.log("--- Revenue Related Items ---");
        balances.forEach(b => {
            // Freee API doesn't explicitly categorize by type in trial_pl balance list, 
            // but we can look for common names or see the whole list.
            if (b.closing_balance !== 0 && (b.account_item_name.includes("売上") || b.account_item_name.includes("収入"))) {
                console.log(`${b.account_item_name}: ${b.closing_balance}`);
            }
        });
    } catch (e) {
        console.error(e.message);
    }
}

main();
