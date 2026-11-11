# KẾT QUẢ KIỂM THỬ CUỐI CÙNG

## Tổng hợp

- **Lệnh:** `python3 -m unittest discover -s tests -t .`
- **Kết quả:** 547 PASS, 5 SKIP, 0 FAIL.
- **Thời gian:** ~150–160 giây (2 vCPU).
- **5 test SKIP:** các test bản đồ dùng dữ liệu Natural Earth thật — cần biến môi trường
  `UVS_NATURAL_EARTH_SHP` trỏ tới tệp `.shp`. Khi chạy kèm biến này, cả 5 đều PASS
  (dữ liệu lấy từ wheel `geopandas` 0.14.4, miền công cộng, không đính kèm trong repo).

## Phân bố theo phase (số test thêm mới)

| Phase | Test thêm |
|---|---|
| 1 | 74 (+5 render) |
| 2 | 36 |
| 3 | 30 |
| 4 | 25 |
| 5 | 33 |
| 6 | 50 |
| 7 | 32 |
| 8 | 21 |
| 9 | 21 |
| 10 | 15 |
| 11 | 19 |
| 12 | 21 |
| 13 | 16 |
| 14 | 16 |
| 15 | 13 |
| Nợ KT (D-02/D-07) | 9 |

## Loại kiểm thử

- **Unit test** (không cần ffmpeg): logic, kiểm tra pixel trên khung dựng bằng PIL, phân tích số liệu.
- **Render test** (cần ffmpeg): mã hóa MP4/âm thanh thật, giải mã lại để kiểm tra số khung, kích thước,
  LUFS, true peak, phát hiện lỗi.
- **Mutation check** (Phase 4): bỏ phép nghịch đảo ma trận / độ mờ / biến đổi thế giới đều làm test
  thất bại — chứng tỏ test kiểm tra thực chất chứ không rỗng.

## Cách xác minh trung thực

Mọi con số đo (LUFS, true peak, tempo, số khung, kích thước, khoảng cách màu) đều lấy từ công cụ chạy
trên media thật (ffmpeg/ffprobe/numpy), không bịa. Các tính năng BLOCKED (ASR/TTS thật) được đánh dấu
rõ và không được tính là đã xác minh.
