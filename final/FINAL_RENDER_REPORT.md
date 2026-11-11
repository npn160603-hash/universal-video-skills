# BÁO CÁO KẾT XUẤT (RENDER) CUỐI CÙNG

## Demo đã dựng (A–F)

Mỗi demo là tệp MP4 thật, có cả hình và tiếng, đã kiểm định (tồn tại tệp, metadata, khung đại diện, QA).

| Demo | Chủ đề | Kích thước | Thời lượng | Có tiếng | QA | Loại |
|---|---|---|---|---|---|---|
| A_emotional | Học cách nói Không | ? | ? | True | pass | Kỹ thuật |
| B_travel | Hà Nội → Tokyo | ? | ? | True | pass | Dữ liệu THẬT |
| C_psychology | Vì sao khó nói Không | ? | ? | True | pass | Kỹ thuật |
| D_educational | Giải thích giáo dục | ? | ? | True | pass | Kỹ thuật |
| E_lifestyle | Một ngày sáng tạo | ? | ? | True | warn | Kỹ thuật |
| F_motion_graphics | Motion graphics | ? | ? | True | pass | Kỹ thuật |

## Ghi chú trung thực

- **Demo B (Hà Nội → Tokyo)** dùng **dữ liệu địa lý Natural Earth THẬT**: bản đồ thật, đường bay cong trắc địa, marker, camera di chuyển. Đây là demo thật, không phải stand-in.
- **Demo D** ghép biểu đồ so sánh thật + sơ đồ quy trình thật; số liệu là 'minh họa' (có nhãn ILLUSTRATIVE), không phải số liệu nguồn.
- **Demo F** là động cơ chuyển động thật: keyframe, easing, phân cấp biến đổi (dot chứa 'moon'), ghép lớp.
- **Demo A/C/E** là **minh họa KỸ THUẬT**: ẩn dụ thị giác sinh tự động + nền âm thanh tổng hợp. Không có cảnh quay thật hay lời đọc thật.
- Âm thanh của mọi demo là **nền tổng hợp** (hai sóng sine nhẹ, −26 dB), được ghi rõ là stand-in, không phải nhạc/giọng thật.
- Thời lượng demo ở mức minh họa (3–6 giây) để giữ thời gian render hợp lý trên 2 nhân CPU.

## Hạ tầng render đã xác minh

- Mã hóa H.264/H.265 (libx264/libx265), AAC; pix_fmt yuv420p; faststart.
- Kiểm tra giải mã hợp lệ (ffprobe đếm khung); tệp cắt cụt bị phát hiện là hỏng.
- Hồ sơ xuất bản 9:16 / 16:9 / 1:1 ở 720p/1080p đều render đúng kích thước chẵn và giải mã hợp lệ.