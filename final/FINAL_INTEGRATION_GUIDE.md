# HƯỚNG DẪN TÍCH HỢP CUỐI CÙNG

## 1. Dùng như thư viện Python

```python
from uvs import narrative, styles, decision
from uvs.captions import Word

words = [Word("Chúng", 0.0, 0.4), Word("ta", 0.4, 0.7), ...]
plan = narrative.build(words, "real_life_storytelling", title="...")
lock = styles.StyleLock.resolve("emotional_storytelling")
ctx = decision.EditContext(plan=plan, style=lock, fps=30)
edit = decision.decide(ctx)        # quyết định + chỉ dẫn timeline thực thi được
```

## 2. Dùng qua API cục bộ (loopback)

Khởi động server (chỉ bind 127.0.0.1):

```bash
python3 -m uvs.server /đường/dẫn/workspace --port 8721
```

SDK Python:

```python
from uvs.sdk import UVSClient
cli = UVSClient("http://127.0.0.1:8721")
cli.info()
tl = cli.generate_timeline(words, "viral_storytelling")
job = cli.render_chart(spec, "charts/a.mp4"); cli.wait_for_job(job)
```

Client TypeScript: `sdk/typescript/uvs-client.ts` (đã type-check với `tsc --strict`).
Ví dụ request/response: `sdk/examples/requests.md`. Harness mẫu: `sdk/examples/reference_harness.py`.

## 3. Tích hợp vào editor web local

- Phase 12 cung cấp **API/SDK độc lập + adapter tham chiếu**. Harness là **minh họa**, KHÔNG phải
  tích hợp với editor cụ thể của bạn.
- **Tích hợp trực tiếp vào repository editor: ĐANG BỊ CHẶN (BLOCKED)** cho tới khi bạn xác nhận
  repository chính xác. Chưa có repo editor nào (Auto-Editing-OutlierY, Premiere-Auto-Cut-v0.6.12,
  ME-OutlierY, AESpace-v1 hay khác) được chọn hay chỉnh sửa.
- Khi bạn xác nhận repo, bước tiếp theo là viết một adapter nối các endpoint `/v1/` vào luồng của editor.

## 4. An toàn

- Mọi đường dẫn tệp đều giới hạn trong thư mục workspace (chặn traversal/tuyệt đối/symlink).
- Server chỉ bind loopback; từ chối host không phải loopback.
- Không shell-out trên chuỗi người dùng; giới hạn kích thước body 4 MiB.
- Trước khi mở ra ngoài loopback: cần thêm token xác thực và hạn mức tài nguyên theo job.

## 5. Phụ thuộc

Xem `FINAL_KNOWN_LIMITATIONS.md` và `requirements.txt`: Python 3.13, Pillow, numpy, jsonschema,
pyshp, psutil; ffmpeg/ffprobe trên PATH. Dữ liệu bản đồ Natural Earth KHÔNG đính kèm (tải từ wheel
geopandas, miền công cộng).
