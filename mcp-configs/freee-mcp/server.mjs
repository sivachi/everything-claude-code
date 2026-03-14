import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import http from "http";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Load .env
const envPath = path.join(__dirname, ".env");
if (fs.existsSync(envPath)) {
  const envContent = fs.readFileSync(envPath, "utf-8");
  for (const line of envContent.split("\n")) {
    const match = line.match(/^([^#=]+)=(.*)$/);
    if (match) process.env[match[1].trim()] = match[2].trim();
  }
}

const CLIENT_ID = process.env.FREEE_CLIENT_ID;
const CLIENT_SECRET = process.env.FREEE_CLIENT_SECRET;
const REDIRECT_URI = "http://localhost:8080/callback";
const TOKEN_PATH = path.join(__dirname, ".token.json");

// Token management
function loadToken() {
  if (fs.existsSync(TOKEN_PATH)) {
    return JSON.parse(fs.readFileSync(TOKEN_PATH, "utf-8"));
  }
  return null;
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
  saveToken(data);
  return data;
}

async function getAccessToken() {
  let token = loadToken();
  if (!token) {
    throw new Error("未認証です。先に freee-auth ツールを実行してください。");
  }
  // Check if token is expired (freee tokens expire in 24h)
  const tokenAge = Date.now() / 1000 - (token.created_at || 0);
  if (tokenAge > 82800) { // refresh if older than 23h
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

// MCP Server
const server = new McpServer({
  name: "freee-accounting",
  version: "1.0.0",
});

// Tool: OAuth認証
server.tool("freee-auth", "freee APIのOAuth認証を行う（初回のみ必要）", {}, async () => {
  const authUrl = `https://accounts.secure.freee.co.jp/public_api/authorize?client_id=${CLIENT_ID}&redirect_uri=${encodeURIComponent(REDIRECT_URI)}&response_type=code&prompt=consent`;

  return new Promise((resolve) => {
    const httpServer = http.createServer(async (req, res) => {
      const url = new URL(req.url, "http://localhost:8080");
      if (url.pathname === "/callback") {
        const code = url.searchParams.get("code");
        if (code) {
          try {
            const tokenRes = await fetch("https://accounts.secure.freee.co.jp/public_api/token", {
              method: "POST",
              headers: { "Content-Type": "application/x-www-form-urlencoded" },
              body: new URLSearchParams({
                grant_type: "authorization_code",
                client_id: CLIENT_ID,
                client_secret: CLIENT_SECRET,
                code,
                redirect_uri: REDIRECT_URI,
              }),
            });
            const tokenData = await tokenRes.json();
            if (tokenData.access_token) {
              saveToken(tokenData);
              res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
              res.end("<h1>認証成功！このタブを閉じてください。</h1>");
              httpServer.close();
              resolve({ content: [{ type: "text", text: "freee認証が完了しました。APIが使えるようになりました。" }] });
            } else {
              res.writeHead(400, { "Content-Type": "text/html; charset=utf-8" });
              res.end("<h1>認証失敗</h1>");
              httpServer.close();
              resolve({ content: [{ type: "text", text: `認証失敗: ${JSON.stringify(tokenData)}` }] });
            }
          } catch (e) {
            res.writeHead(500);
            res.end("Error");
            httpServer.close();
            resolve({ content: [{ type: "text", text: `エラー: ${e.message}` }] });
          }
        }
      }
    });

    httpServer.listen(8080, () => {
      resolve({
        content: [{
          type: "text",
          text: `以下のURLをブラウザで開いて認証してください:\n\n${authUrl}\n\n認証後、自動的にトークンが保存されます。`,
        }],
      });
      // Close server after 5 minutes if no callback
      setTimeout(() => { try { httpServer.close(); } catch(e) {} }, 300000);
    });
  });
});

// Tool: 事業所一覧
server.tool("freee-companies", "freeeに登録されている事業所の一覧を取得", {}, async () => {
  const data = await freeeAPI("/companies");
  return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
});

// Tool: 事業所詳細
server.tool("freee-company", "事業所の詳細情報を取得", {
  company_id: z.number().describe("事業所ID"),
}, async ({ company_id }) => {
  const data = await freeeAPI(`/companies/${company_id}`);
  return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
});

// Tool: 取引一覧
server.tool("freee-deals", "取引（収入・支出）の一覧を取得", {
  company_id: z.number().describe("事業所ID"),
  start_date: z.string().optional().describe("開始日 (YYYY-MM-DD)"),
  end_date: z.string().optional().describe("終了日 (YYYY-MM-DD)"),
  type: z.enum(["income", "expense"]).optional().describe("取引種別: income(収入) or expense(支出)"),
  limit: z.number().optional().describe("取得件数 (デフォルト20, 最大100)"),
  offset: z.number().optional().describe("オフセット"),
}, async ({ company_id, start_date, end_date, type, limit, offset }) => {
  const data = await freeeAPI("/deals", { company_id, start_issue_date: start_date, end_issue_date: end_date, type, limit: limit || 20, offset });
  return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
});

// Tool: 勘定科目一覧
server.tool("freee-accounts", "勘定科目の一覧を取得", {
  company_id: z.number().describe("事業所ID"),
}, async ({ company_id }) => {
  const data = await freeeAPI("/account_items", { company_id });
  return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
});

// Tool: 試算表（損益計算書）
server.tool("freee-pl", "損益計算書（試算表）を取得", {
  company_id: z.number().describe("事業所ID"),
  fiscal_year: z.number().optional().describe("会計年度"),
  start_month: z.number().optional().describe("開始月 (1-12)"),
  end_month: z.number().optional().describe("終了月 (1-12)"),
}, async ({ company_id, fiscal_year, start_month, end_month }) => {
  const data = await freeeAPI("/reports/trial_pl", { company_id, fiscal_year, start_month, end_month });
  return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
});

// Tool: 試算表（貸借対照表）
server.tool("freee-bs", "貸借対照表（試算表）を取得", {
  company_id: z.number().describe("事業所ID"),
  fiscal_year: z.number().optional().describe("会計年度"),
  start_month: z.number().optional().describe("開始月 (1-12)"),
  end_month: z.number().optional().describe("終了月 (1-12)"),
}, async ({ company_id, fiscal_year, start_month, end_month }) => {
  const data = await freeeAPI("/reports/trial_bs", { company_id, fiscal_year, start_month, end_month });
  return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
});

// Tool: 請求書一覧
server.tool("freee-invoices", "請求書の一覧を取得", {
  company_id: z.number().describe("事業所ID"),
  start_issue_date: z.string().optional().describe("発行日開始 (YYYY-MM-DD)"),
  end_issue_date: z.string().optional().describe("発行日終了 (YYYY-MM-DD)"),
  invoice_status: z.enum(["draft", "applying", "remanded", "rejected", "approved", "unsubmitted", "submitted"]).optional().describe("請求書ステータス"),
}, async ({ company_id, start_issue_date, end_issue_date, invoice_status }) => {
  const data = await freeeAPI("/invoices", { company_id, start_issue_date, end_issue_date, invoice_status });
  return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
});

// Tool: 取引先一覧
server.tool("freee-partners", "取引先の一覧を取得", {
  company_id: z.number().describe("事業所ID"),
}, async ({ company_id }) => {
  const data = await freeeAPI("/partners", { company_id });
  return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
});

// Tool: 口座一覧
server.tool("freee-walletables", "口座（銀行口座・クレジットカード等）の一覧を取得", {
  company_id: z.number().describe("事業所ID"),
}, async ({ company_id }) => {
  const data = await freeeAPI("/walletables", { company_id });
  return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
});

// Tool: 経費精算一覧
server.tool("freee-expense-applications", "経費精算の一覧を取得", {
  company_id: z.number().describe("事業所ID"),
  status: z.enum(["draft", "in_progress", "approved", "rejected"]).optional().describe("ステータス"),
}, async ({ company_id, status }) => {
  const data = await freeeAPI("/expense_applications", { company_id, status });
  return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
});

// Start server
const transport = new StdioServerTransport();
await server.connect(transport);
