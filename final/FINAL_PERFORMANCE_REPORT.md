# BÁO CÁO HIỆU NĂNG CUỐI CÙNG

## Phần cứng (phát hiện thật)

- CPU: 2 nhân
- RAM: 8.41 GB
- GPU: KHÔNG có (none)
- Encoder video hoạt động: libx264, libx265, libvpx-vp9
- Encoder audio hoạt động: aac, libopus, libmp3lame

**Lưu ý:** ffmpeg có liệt kê encoder tăng tốc phần cứng (nvenc/qsv…) nhưng KHÔNG có GPU, nên các encoder đó KHÔNG được báo là 'hoạt động'. Encoder chỉ được tính khi test-encode thành công.

## Benchmark đã đo (không bịa số)

| Hồ sơ | Encoding FPS | Thời gian render (s) | Kích thước (byte) | Giải mã hợp lệ |
|---|---|---|---|---|
| 9x16_1080p_h264 | 192.9 | 0.467 | 182391 | True |
| 16x9_720p_h264 | 135.8 | 0.663 | 1166008 | True |

## Ma trận xuất bản

- 6/6 hồ sơ chuẩn (3 tỉ lệ × 2 độ phân giải) xuất bản được với libx264.

## Tối ưu hóa render đã xác minh

- **Render cache**: khóa theo hash nội dung; render không đổi được tái dùng (chỉ render 1 lần); tráo tệp tạm nguyên tử.
- **Benchmark**: đo thời gian thật, kích thước, FPS mã hóa, bộ nhớ (psutil), tính hợp lệ giải mã.
- **Hủy (cancel)** và **retry** job đã kiểm thử trong job manager.

## Giới hạn

- Chưa có đường tăng tốc phần cứng (môi trường không có GPU).
- Cache là theo cả tệp đầu ra, chưa phải diff từng đoạn.
- 1440p/4K đã định nghĩa nhưng không benchmark ở đây (chậm trên 2 nhân, không cần thiết).
- Không bao giờ bịa cải thiện tốc độ: mọi số đều từ phép đo thật.