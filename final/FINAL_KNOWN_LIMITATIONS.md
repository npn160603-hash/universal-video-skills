# GIỚI HẠN ĐÃ BIẾT — CUỐI CÙNG

## Bị chặn (BLOCKED) — cần phụ thuộc hoặc cho phép

- **ASR thật** (nhận dạng giọng nói): chưa cài whisper/vosk; không tải mô hình lớn khi chưa được phép.
  Đã có: giao diện provider, phát hiện năng lực, fallback nhận timestamp bên ngoài.
- **TTS giọng nói thật**: chưa cài espeak-ng/piper; cài qua apt là thay đổi hệ thống, cần cho phép.
  Đã có: provider WAV thật không-mô-hình (silence, click-track) để kiểm thử timing/trộn âm.
- **Tích hợp trực tiếp vào editor**: chưa xác nhận repository mục tiêu.
- **Cảnh quay/giọng đọc/nhạc có bản quyền thật**: không có sẵn/không được cấp phép.

## Hoạt động một phần (PARTIAL)

- Tự sự: dựa trên luật, từ vựng thiên tiếng Anh; chưa có mô hình ngôn ngữ; chưa có match cut / parallel montage.
- Tìm media: chỉ khớp từ vựng (không embedding); không phân tích nội dung hình ảnh.
- Chuyển động: chỉ render shape/image/group; chưa render text/video/mask/camera; keyframe gắn vào node, chưa gắn vào clip timeline.
- Bản đồ: chưa có nhãn quốc gia, choropleth, phép chiếu địa cầu.
- Theo dõi beat: xác minh trên click track; nhạc phức có thể sai (lỗi quãng tám).
- Shot matching: chỉnh màu trung bình từng kênh, chưa khớp toàn histogram/độ tương phản.
- API: endpoint render phủ biểu đồ; render video đầy đủ chạy trong tiến trình (pipeline) chứ chưa thành job streaming.

## Đã sửa trong đợt này

- D-01 (style lock theo cảnh 0) → Style Lock ở cấp dự án (Phase 10).
- D-02 (không kiểm tra spec) → `pipeline.validate_spec` (Phase 15).
- D-07 (font fallback) → quét thư mục font khi thiếu fc-match (Phase 15).

## An toàn & bản quyền

- Dữ liệu Natural Earth: miền công cộng, KHÔNG đính kèm trong repo.
- Không gói kèm nhạc/cảnh quay/font/preset độc quyền trái phép.
- Mọi con số đều đo thật; không bịa số liệu hay cải thiện tốc độ.
