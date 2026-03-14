import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import http from "http";
import { google } from "googleapis";

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

const CLIENT_ID = process.env.GOOGLE_CLIENT_ID;
const CLIENT_SECRET = process.env.GOOGLE_CLIENT_SECRET;
const REDIRECT_URI = "http://localhost:8081/callback";
const TOKEN_PATH = path.join(__dirname, ".token.json");
const SCOPES = ["https://www.googleapis.com/auth/drive"];

const oauth2Client = new google.auth.OAuth2(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI);

// Token management
function loadToken() {
  if (fs.existsSync(TOKEN_PATH)) {
    const token = JSON.parse(fs.readFileSync(TOKEN_PATH, "utf-8"));
    oauth2Client.setCredentials(token);
    return token;
  }
  return null;
}

function saveToken(token) {
  fs.writeFileSync(TOKEN_PATH, JSON.stringify(token, null, 2));
}

function getDrive() {
  const token = loadToken();
  if (!token) throw new Error("未認証です。先に gdrive-auth ツールを実行してください。");
  return google.drive({ version: "v3", auth: oauth2Client });
}

// Auto-refresh token
oauth2Client.on("tokens", (tokens) => {
  const existing = loadToken() || {};
  const merged = { ...existing, ...tokens };
  saveToken(merged);
});

// MCP Server
const server = new McpServer({
  name: "gdrive",
  version: "1.0.0",
});

// Tool: OAuth認証
server.tool("gdrive-auth", "Google Drive APIのOAuth認証を行う（初回のみ必要）", {}, async () => {
  const authUrl = oauth2Client.generateAuthUrl({
    access_type: "offline",
    scope: SCOPES,
    prompt: "consent",
  });

  return new Promise((resolve) => {
    const httpServer = http.createServer(async (req, res) => {
      const url = new URL(req.url, "http://localhost:8081");
      if (url.pathname === "/callback") {
        const code = url.searchParams.get("code");
        if (code) {
          try {
            const { tokens } = await oauth2Client.getToken(code);
            oauth2Client.setCredentials(tokens);
            saveToken(tokens);
            res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
            res.end("<h1>Google Drive 認証成功！このタブを閉じてください。</h1>");
            httpServer.close();
            resolve({ content: [{ type: "text", text: "Google Drive認証が完了しました。" }] });
          } catch (e) {
            res.writeHead(500, { "Content-Type": "text/html; charset=utf-8" });
            res.end("<h1>認証失敗</h1>");
            httpServer.close();
            resolve({ content: [{ type: "text", text: `エラー: ${e.message}` }] });
          }
        }
      }
    });

    httpServer.listen(8081, () => {
      resolve({
        content: [{
          type: "text",
          text: `以下のURLをブラウザで開いて認証してください:\n\n${authUrl}\n\n認証後、自動的にトークンが保存されます。`,
        }],
      });
      setTimeout(() => { try { httpServer.close(); } catch (e) {} }, 300000);
    });
  });
});

// Tool: ファイル・フォルダ一覧
server.tool("gdrive-list", "Google Driveのファイル・フォルダ一覧を取得", {
  folder_id: z.string().optional().describe("フォルダID（省略時はルート）"),
  query: z.string().optional().describe("検索クエリ（ファイル名など）"),
}, async ({ folder_id, query }) => {
  const drive = getDrive();
  let q = "trashed = false";
  if (folder_id) q += ` and '${folder_id}' in parents`;
  if (query) q += ` and name contains '${query}'`;

  const res = await drive.files.list({
    q,
    fields: "files(id, name, mimeType, parents, modifiedTime, size)",
    pageSize: 100,
    orderBy: "name",
  });

  return { content: [{ type: "text", text: JSON.stringify(res.data.files, null, 2) }] };
});

// Tool: フォルダ作成
server.tool("gdrive-create-folder", "Google Driveにフォルダを作成", {
  name: z.string().describe("フォルダ名"),
  parent_id: z.string().optional().describe("親フォルダID（省略時はルート）"),
}, async ({ name, parent_id }) => {
  const drive = getDrive();
  const fileMetadata = {
    name,
    mimeType: "application/vnd.google-apps.folder",
  };
  if (parent_id) fileMetadata.parents = [parent_id];

  const res = await drive.files.create({
    requestBody: fileMetadata,
    fields: "id, name",
  });

  return { content: [{ type: "text", text: `フォルダ作成完了: ${res.data.name} (ID: ${res.data.id})` }] };
});

// Tool: ファイルアップロード
server.tool("gdrive-upload", "ローカルファイルをGoogle Driveにアップロード", {
  local_path: z.string().describe("アップロードするローカルファイルのパス"),
  name: z.string().describe("Google Drive上でのファイル名"),
  folder_id: z.string().optional().describe("アップロード先フォルダID"),
}, async ({ local_path, name, folder_id }) => {
  const drive = getDrive();
  const fileMetadata = { name };
  if (folder_id) fileMetadata.parents = [folder_id];

  const media = {
    body: fs.createReadStream(local_path),
  };

  const res = await drive.files.create({
    requestBody: fileMetadata,
    media,
    fields: "id, name, webViewLink",
  });

  return { content: [{ type: "text", text: `アップロード完了: ${res.data.name}\nID: ${res.data.id}\nURL: ${res.data.webViewLink}` }] };
});

// Tool: ファイルリネーム
server.tool("gdrive-rename", "Google Drive上のファイル名を変更", {
  file_id: z.string().describe("ファイルID"),
  new_name: z.string().describe("新しいファイル名"),
}, async ({ file_id, new_name }) => {
  const drive = getDrive();
  const res = await drive.files.update({
    fileId: file_id,
    requestBody: { name: new_name },
    fields: "id, name",
  });

  return { content: [{ type: "text", text: `リネーム完了: ${res.data.name} (ID: ${res.data.id})` }] };
});

// Tool: ファイル移動
server.tool("gdrive-move", "Google Drive上のファイルを別フォルダに移動", {
  file_id: z.string().describe("ファイルID"),
  new_folder_id: z.string().describe("移動先フォルダID"),
}, async ({ file_id, new_folder_id }) => {
  const drive = getDrive();
  // Get current parents
  const file = await drive.files.get({ fileId: file_id, fields: "parents" });
  const previousParents = (file.data.parents || []).join(",");

  const res = await drive.files.update({
    fileId: file_id,
    addParents: new_folder_id,
    removeParents: previousParents,
    fields: "id, name, parents",
  });

  return { content: [{ type: "text", text: `移動完了: ${res.data.name} (ID: ${res.data.id})` }] };
});

// Tool: フォルダを探すか作成
server.tool("gdrive-find-or-create-folder", "指定パスのフォルダを探し、なければ作成する", {
  folder_path: z.string().describe("フォルダパス（例: 10_経理・会計/02_請求書（受領）/第5期_2026年1月期/202602_2月）"),
  root_folder_id: z.string().optional().describe("起点フォルダID（省略時はルート）"),
}, async ({ folder_path, root_folder_id }) => {
  const drive = getDrive();
  const parts = folder_path.split("/").filter(Boolean);
  let parentId = root_folder_id || "root";

  const results = [];
  for (const folderName of parts) {
    // Search for existing folder
    const q = `name = '${folderName}' and '${parentId}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false`;
    const searchRes = await drive.files.list({ q, fields: "files(id, name)" });

    if (searchRes.data.files && searchRes.data.files.length > 0) {
      parentId = searchRes.data.files[0].id;
      results.push(`既存: ${folderName} (${parentId})`);
    } else {
      const createRes = await drive.files.create({
        requestBody: {
          name: folderName,
          mimeType: "application/vnd.google-apps.folder",
          parents: [parentId],
        },
        fields: "id, name",
      });
      parentId = createRes.data.id;
      results.push(`新規作成: ${folderName} (${parentId})`);
    }
  }

  return {
    content: [{
      type: "text",
      text: `フォルダ確認完了:\n${results.join("\n")}\n\n最終フォルダID: ${parentId}`,
    }],
  };
});

// Start server
const transport = new StdioServerTransport();
loadToken(); // Load existing token on startup
await server.connect(transport);
