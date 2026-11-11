# DANH SÁCH PHÊ DUYỆT CUỐI CÙNG

## Trạng thái hiện tại

- Nhánh: `initial-pipeline`. Các Phase 0–15 đã commit **cục bộ**.
- Remote `origin/initial-pipeline` vẫn ở `e84a7c7`. **Chưa đẩy thêm commit nào.**
- 547 test PASS, 5 SKIP (cần dữ liệu bản đồ). Không có FAIL.
- Chưa merge, chưa publish, chưa deploy.

## Việc đã KHÔNG tự ý làm (đúng ràng buộc)

- [x] Không force-push, không ghi đè `main`, không merge vào `main`.
- [x] Không xóa nhánh hay tài sản của người dùng.
- [x] Không phát hành/triển khai công khai, không dùng API trả phí.
- [x] Không tải mô hình AI lớn khi chưa được phép.
- [x] Không tự chọn repository editor; không chỉnh sửa repo editor nào.
- [x] Không gửi dữ liệu người dùng ra bên thứ ba.

## Cần người dùng quyết định / phê duyệt

1. **Đẩy (push) các commit cục bộ lên `initial-pipeline`?**
   - Chỉ fast-forward; chạy pre-push guard; xác minh bằng `git ls-remote`. Chờ bạn cho phép.
2. **Xác nhận repository editor** cho tích hợp trực tiếp (Phase 12). Hiện BLOCKED.
3. **Cho phép cài engine ASR/TTS** (vd. whisper/vosk/espeak-ng) nếu muốn có giọng nói/nhận dạng thật.
   Việc này cần tải mô hình/cài gói hệ thống — cần bạn cho phép.
4. **Cung cấp media thật** (cảnh quay, giọng đọc, nhạc có bản quyền) nếu muốn demo media thật thay vì
   minh họa kỹ thuật.

## Ghi chú thay đổi hệ thống đã thực hiện (trong sandbox)

- Đã cài `pyshp` và dùng `psutil` (có sẵn). `pyshp` đã thêm vào `requirements.txt`.
- Trích xuất dữ liệu Natural Earth 110m vào `/tmp` (không commit) từ wheel geopandas 0.14.4.

## Kết luận

Hệ thống là một bộ dựng video tự động thật, có thể tái sử dụng, với mã chạy được và kiểm thử thật
trên 15 phase. Các phần BLOCKED được ghi rõ và chờ phê duyệt/phụ thuộc. Không thực hiện bước không
thể đảo ngược nào khi chưa có xác nhận của bạn.
