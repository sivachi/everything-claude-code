
import fs from 'fs';
import path from 'path';

const CLIENT_ID = "668055678584424";
const CLIENT_SECRET = "0_hED5SppgVgBuRXPlcYIkEgyVFMJQAMgDv3lLxWj7LIr98foBFVptn9cr02OtbLdOP3SaGFa8F98r7CiOIKGg";
const TOKEN_PATH = "/Users/tadaakikurata/works/freee-mcp/.token.json";

function loadToken() {
    return JSON.parse(fs.readFileSync(TOKEN_PATH, 'utf-8'));
}

async function refreshAccessToken(refreshToken) {
    const res = await fetch("https://accounts.secure.freee.co.jp/public_api/token", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
            grant_type: "refresh_token",
            client_id: CLIENT_ID,
            client_secret: CLIENT_SECRET,
            refresh_token: refreshToken,
        }),
    });
    if (!res.ok) throw new Error(`Token refresh failed: ${res.status}`);
    const data = await res.json();
    data.created_at = Math.floor(Date.now() / 1000);
    fs.writeFileSync(TOKEN_PATH, JSON.stringify(data, null, 2));
    return data;
}

async function getAccessToken() {
    let token = loadToken();
    const tokenAge = Date.now() / 1000 - (token.created_at || 0);
    if (tokenAge > 18000) {
        token = await refreshAccessToken(token.refresh_token);
    }
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
    if (!res.ok) {
        const body = await res.text();
        throw new Error(`freee API error ${res.status}: ${body}`);
    }
    return res.json();
}

async function main() {
    try {
        const companyId = 12342495;
        const pl = await freeeAPI("/reports/trial_pl", { company_id: companyId, fiscal_year: 2025 });

        // Find Sales (売上高)
        // The response structure of trial_pl is complex. It usually has trial_pl.balances[]
        // Each balance has account_item_name and closing_balance

        const balances = pl.trial_pl.balances || [];
        const salesItem = balances.find(b => b.account_item_name === "売上高");

        if (salesItem) {
            console.log(`Sales (売上高): ${salesItem.closing_balance}`);
        } else {
            console.log("Sales (売上高) not found in the PL report.");
            // Log all balances to see what's available
            console.log("All balances:");
            balances.forEach(b => {
                if (b.closing_balance !== 0) {
                    console.log(`- ${b.account_item_name}: ${b.closing_balance}`);
                }
            });
        }
    } catch (e) {
        console.error(e.message);
        process.exit(1);
    }
}

main();
