# BÁO CÁO PHÁT TRIỂN CUỐI CÙNG — Universal Video Skills

## 1. Tổng quan

Dự án xây dựng một hệ thống dựng video tự động, thực thi được, cho repository
`npn160603-hash/universal-video-skills`. Toàn bộ mã là mã thật chạy được, kèm kiểm thử thật và
kết xuất (render) thật. Trạng thái của mỗi tính năng được phân loại trung thực; không có tính năng
nào được xem là "đã xác minh" chỉ dựa trên tài liệu.

- **Nhánh Git:** `initial-pipeline`
- **Commit cuối (cục bộ):** xem `git log` — các Phase 0–15 đã được commit cục bộ.
- **Remote:** `origin/initial-pipeline` vẫn ở `e84a7c7`. **Chưa đẩy (push) thêm commit nào** —
  chờ cho phép rõ ràng.
- **Bộ kiểm thử:** 547 test PASS, 5 test SKIP (các test cần dữ liệu bản đồ Natural Earth qua biến
  môi trường `UVS_NATURAL_EARTH_SHP`). Chạy: `python3 -m unittest discover -s tests -t .`
- **Quy mô:** 37 module Python trong `uvs/`, 47 tệp kiểm thử.

## 2. Trạng thái 16 Phase

| Phase | Tên | Trạng thái |
|---|---|---|
| 0 | Kiểm toán repository | VERIFIED |
| 1 | Kiến trúc lõi | PARTIAL |
| 2 | Đạo diễn AI / tự sự | PARTIAL |
| 3 | Trí tuệ media | PARTIAL |
| 4 | Động cơ chuyển động | PARTIAL |
| 5 | Bản đồ động | PARTIAL |
| 6 | Infographics & minh họa | PARTIAL |
| 7 | Giọng nói, phụ đề, căn chỉnh | PARTIAL |
| 8 | Thiết kế âm thanh | PARTIAL |
| 9 | Màu & ghép lớp | PARTIAL |
| 10 | Hệ thống style | VERIFIED |
| 11 | Động cơ quyết định biên tập | VERIFIED |
| 12 | API/SDK biên tập cục bộ | PARTIAL |
| 13 | Hiệu năng & xuất bản | VERIFIED |
| 14 | QA tự động | VERIFIED |
| 15 | Demo & kiểm định cuối | PARTIAL |

Chi tiết từng tính năng: `docs/PHASE_STATUS.json` và `docs/audit/CAPABILITY_MATRIX.md`.

## 3. Nợ kỹ thuật (technical debt)

- **D-01** (style lock chỉ lấy look của cảnh 0) — **ĐÃ SỬA** ở Phase 10 (Style Lock, xác minh đầu-cuối).
- **D-02** (không kiểm tra `spec.json`) — **ĐÃ SỬA** ở Phase 15 (`pipeline.validate_spec`).
- **D-07** (font fallback sai làm lệch đo chữ) — **ĐÃ SỬA** ở Phase 15 (quét thư mục font khi thiếu `fc-match`).

## 4. Điểm nổi bật đã xác minh

- Động cơ chuyển động dựng khung hình và mã hóa MP4 thật, kiểm tra từng pixel (vị trí, xoay, độ mờ, thứ tự vẽ).
- Bản đồ động dùng dữ liệu Natural Earth thật (177 quốc gia), đường cong trắc địa, camera.
- 10 loại biểu đồ, 6 loại timeline, 7 loại sơ đồ, 8 ẩn dụ thị giác — tất cả render thật.
- 7 style phụ đề (gồm tiếng Việt có dấu) burn qua libass.
- Phát hiện nhịp/tempo (sai số < 5% trên click track), QA âm thanh đo thật (LUFS, true peak, clipping).
- Quản lý màu, ghép màu giữa các cảnh (shot matching), 20 look.
- 10 style biên tập đầy đủ + Style Lock; động cơ quyết định có chấm điểm và ghi lý do.
- API cục bộ + SDK Python + client TypeScript + harness tham chiếu (loopback-only).
- Phát hiện phần cứng/encoder thật, hồ sơ xuất bản, cache render, benchmark đo thật.
- QA tự động với sửa lỗi an toàn (có giới hạn, không bao giờ lặp vô hạn), báo cáo JSON + Markdown.

## 5. Giới hạn chính (xem FINAL_KNOWN_LIMITATIONS.md)

- ASR/TTS thật: BLOCKED (chưa cài engine; không tải mô hình lớn khi chưa được phép).
- Tích hợp trực tiếp vào editor: BLOCKED (chưa xác nhận repository).
- Demo A/C/E là minh họa kỹ thuật (visual sinh tự động, âm thanh tổng hợp), không phải media thật.

## 6. Hành động cần phê duyệt

Xem `FINAL_APPROVAL_CHECKLIST.md`. Không merge, không publish, không deploy, không push thêm khi chưa được phép.
