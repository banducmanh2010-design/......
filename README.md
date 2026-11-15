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
   - `GEMINI_MODEL`: mặc định `gemini-2.5-flash`.
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
