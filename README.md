# Zalo Gemini Bot

Bot Zalo trả lời tin nhắn bằng Google Gemini, chạy bằng Flask và có thể triển khai trên Render.

## 1. Chuẩn bị

- Một Zalo Bot đã tạo trong Zalo Bot Creator.
- Zalo Bot Token.
- Gemini API key lấy từ Google AI Studio.
- Tài khoản GitHub và Render.

**Bảo mật:** Nếu token/API key từng được gửi trong chat, ảnh chụp, hoặc đăng công khai, hãy thu hồi và tạo khóa mới. Chỉ nhập khóa mới trong phần Environment của Render. Không commit khóa vào GitHub.

## 2. Triển khai lên Render

1. Đăng nhập Render và chọn **New → Blueprint**.
2. Chọn repository này. Render đọc cấu hình từ `render.yaml`.
3. Tạo các biến môi trường được yêu cầu:
   - `ZALO_TOKEN`: Bot Token mới từ Zalo.
   - `GEMINI_API_KEY`: API key mới từ Google AI Studio.
   - `GEMINI_MODEL`: mặc định `gemini-3.8-flash`.
   - `WEBHOOK_SECRET`: tùy chọn; chỉ đặt nếu nền tảng webhook có thể gửi header `X-Webhook-Secret` tương ứng.
4. Chờ Render deploy thành công. Mở URL dịch vụ, ví dụ `https://ten-dich-vu.onrender.com/health`.
5. Kiểm tra JSON có `"status":"ok"`, `"zalo_configured":true` và `"gemini_configured":true`.

Gói miễn phí của Render có thể tự sleep khi không có truy cập; bot có thể phản hồi chậm ở tin nhắn đầu tiên sau thời gian nghỉ.

## 3. Cấu hình webhook Zalo

Trong phần quản lý Zalo Bot, cấu hình webhook URL là:

`https://TEN-DICH-VU.onrender.com/webhook`

Thay bằng URL thật mà Render cấp. Lưu cấu hình và kiểm tra trạng thái webhook trong trang quản lý bot.

## 4. Kiểm tra

Mở URL gốc của dịch vụ để xem trạng thái. Sau đó nhắn tin cho bot trên Zalo. Nếu bot không phản hồi, kiểm tra **Logs** trên Render và xác nhận webhook URL/token.

## 5. API endpoints

- `GET /`: thông tin dịch vụ.
- `GET /health`: kiểm tra tình trạng cấu hình.
- `POST /webhook`: nhận sự kiện từ Zalo Bot.

## Ghi chú

- Bot chỉ xử lý sự kiện có nội dung văn bản và ID cuộc trò chuyện/người gửi.
- Các loại sự kiện khác được xác nhận và bỏ qua.
- Tin nhắn dài được chia thành nhiều phần để phù hợp giới hạn gửi tin.
- Không chia sẻ Bot Token hoặc Gemini API key cho người khác.

## DUCMANH AI foundation (new)

- `GET /api/connections`: safe provider connection status; never returns credentials.
- `GET /api/plugins`: plugin availability/catalog.
- `POST /api/files/generate`: exports supplied content to HTML, TXT, Markdown, PDF, DOCX, PPTX, XLSX, or ZIP. Requires `X-Studio-Key` matching the Render `STUDIO_API_KEY` secret.
- `studio.py`: document export helpers.
- `connections.py`: provider registry (a provider is not considered connected until credentials/authorization are configured).
- `PLUGIN_CATALOG.md`: integration and security plan.
- `vscode-extension/`: initial VS Code companion extension scaffold; it does not yet send workspace data to the server.

### Enable File Studio
In Render → Environment, add `STUDIO_API_KEY` with a long random secret. Do not put it in GitHub or send it in Zalo messages. Then call `POST /api/files/generate` with header `X-Studio-Key` and JSON body such as:
`{"format":"html","filename":"my-site","content":"<!doctype html>..."}`.

Canva, OpenAI, Claude, DeepSeek, OpenRouter, GitHub, Render, Google Drive, Notion, Figma, and Dropbox require their own credentials/OAuth app setup. The catalog intentionally reports them as not connected until verified. No arbitrary generated code is executed by the web service.

### Connection Center technical specification
See [CONNECTION_CENTER_SPEC.md](CONNECTION_CENTER_SPEC.md) for the planned architecture, provider catalog, API contracts, authentication and credential security, VS Code pairing model, plugin marketplace, database design, and phased rollout. This is a design document; it does not mean those integrations are already connected.
