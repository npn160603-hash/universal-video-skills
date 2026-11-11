# MA TRẬN NĂNG LỰC CUỐI CÙNG

Chú thích: VERIFIED = có mã + kiểm thử trên kết xuất thật; PARTIAL = một phần hoạt động;
BLOCKED = cần phụ thuộc/cho phép chưa có; IMPLEMENTED_UNVERIFIED = có mã nhưng chưa test đường đó.

| Lĩnh vực | Năng lực | Trạng thái |
|---|---|---|
| Kiến trúc | Định dạng project có version, scene graph, edit ops hoàn tác, asset registry, render backend | PARTIAL (scene graph nay đã render qua Phase 4) |
| Tự sự | Phân tích kịch bản, 4 cấu trúc, cỡ cảnh theo cảm xúc, ghi quyết định | PARTIAL (dựa luật, tiếng Anh là chính) |
| Media | Gắn thẻ sidecar, tìm kiếm từ vựng, cổng bản quyền, gán B-roll, nhịp cắt theo chuyển động | PARTIAL (không có embedding) |
| Chuyển động | Keyframe trên scene graph, render shape/image/group ra MP4 | PARTIAL (chưa render text/video/mask/camera) |
| Bản đồ | Natural Earth 177 nước, chiếu equirectangular/Mercator, đường trắc địa, marker, camera | PARTIAL (chưa nhãn/choropleth/globe) |
| Infographics | 10 biểu đồ, 6 timeline, 7 sơ đồ (chống chồng lấn), 8 ẩn dụ, điều khiển hoạt họa | PARTIAL |
| Phụ đề | 7 style, hiệu ứng chữ, QA bố cục, tiếng Việt NFC | VERIFIED |
| Giọng nói | Phát hiện năng lực, TTS không-mô-hình (WAV thật), fallback timestamp, VAD/silence | PARTIAL |
| ASR/TTS thật | Nhận dạng / tổng hợp giọng nói thật | BLOCKED |
| Âm thanh | Chuỗi voice (EQ, de-ess), tempo/beat, cắt theo beat, hướng cảm xúc, QA âm thanh | PARTIAL |
| Màu | Nguyên thủy màu, phân tích khung, shot matching, 20 look, ghép lớp, QA màu | PARTIAL |
| Style | 10 preset biên tập đầy đủ, Style Lock, kiểm tra | VERIFIED |
| Quyết định | 12 quyết định + 9 tiêu chí/cảnh, quy tắc bắt buộc, override giữ khi tái tạo | VERIFIED |
| API/SDK | API lõi, job manager, server loopback, SDK Python, client TS, harness | PARTIAL |
| Tích hợp editor | Tích hợp trực tiếp vào editor của người dùng | BLOCKED |
| Xuất bản | Phát hiện phần cứng/encoder, hồ sơ 9:16/16:9/1:1 × 720p/1080p, H.264/H.265, cache, benchmark | VERIFIED |
| QA | Phát hiện lỗi hình/âm/timeline, heuristic sáng tạo, sửa an toàn có giới hạn, báo cáo | VERIFIED |
| Demo | 6 demo A–F render + kiểm định | PARTIAL |

Nguồn đối chiếu: `docs/audit/CAPABILITY_MATRIX.md`, `docs/PHASE_STATUS.json`.
