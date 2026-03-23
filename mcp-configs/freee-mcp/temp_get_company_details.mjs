
import fs from 'fs';
import path from 'path';

const CLIENT_ID = "668055678584424";
const CLIENT_SECRET = "0_hED5SppgVgBuRXPlcYIkEgyVFMJQAMgDv3lLxWj7LIr98foBFVptn9cr02OtbLdOP3SaGFa8F98r7CiOIKGg";
const TOKEN_PATH = "/Users/tadaakikurata/works/freee-mcp/.token.json";

function loadToken() {
    return JSON.parse(fs.readFileSync(TOKEN_PATH, 'utf-8'));
}

function saveToken(token) {
    fs.writeFileSync(TOKEN_PATH, JSON.stringify(token, null, 2));
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
    saveToken(data);
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
        const company = await freeeAPI(`/companies/${companyId}`);
        console.log(JSON.stringify(company, null, 2));
    } catch (e) {
        console.error(e.message);
        process.exit(1);
    }
}

main();
