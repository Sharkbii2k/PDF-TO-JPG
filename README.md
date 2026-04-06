# Delivery Note PDF Tool

Web tool Flask để upload nhiều file PDF Delivery Note, tự đọc ETA, phân loại theo Line No (1F/2F), convert trang đầu thành JPG 300 DPI và trả về file ZIP.

## Cấu trúc project

- `app.py`: backend Flask + giao diện HTML/CSS/JS bằng `render_template_string`
- `requirements.txt`: dependencies Python
- `Dockerfile`: image dùng cho Render
- `render.yaml`: cấu hình Render Blueprint cơ bản
- `.gitignore`: bỏ qua file tạm

## Chạy local

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Mở: `http://127.0.0.1:5000`

## Push lên GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/USERNAME/REPO_NAME.git
git push -u origin main
```

## Deploy lên Render

### Cách 1: Dùng Web Service từ GitHub
1. Tạo repo GitHub và push code lên.
2. Vào Render -> **New +** -> **Web Service**.
3. Kết nối GitHub và chọn repo.
4. Render sẽ nhận `Dockerfile` ở thư mục gốc và build tự động.
5. Sau khi deploy xong, mở URL service để dùng.

### Cách 2: Dùng Blueprint với `render.yaml`
1. Push code lên GitHub.
2. Vào Render -> **New +** -> **Blueprint**.
3. Chọn repo chứa project.
4. Render đọc `render.yaml` và tạo service.

## Ghi chú tối ưu RAM

- Chỉ xử lý từng PDF một.
- Chỉ convert trang đầu tiên.
- Dùng thư mục tạm trên disk thay vì giữ dữ liệu trong RAM.
- Gọi `gc.collect()` sau mỗi file.
- Gunicorn chạy `1 worker`, `2 threads` để phù hợp Render Free.
