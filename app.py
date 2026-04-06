import gc
import os
import re
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime
from typing import List, Optional, Tuple

import pdfplumber
from flask import Flask, jsonify, render_template_string, request, send_file
from pdf2image import convert_from_path
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024  # 300MB, adjust if needed.

ETA_PATTERN = re.compile(r"\bETA\s*:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\b", re.IGNORECASE)
LINE_PATTERN = re.compile(r"\b(C[12])\s*-\s*([0-9][A-Z0-9]*)\b", re.IGNORECASE)

PAGE_HTML = r"""
<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <title>PDF Delivery Note Tool</title>
  <style>
    :root {
      --bg: #f4f7fb;
      --card: #ffffff;
      --text: #10233f;
      --muted: #5c6b82;
      --primary: #1769ff;
      --primary-dark: #0f52cc;
      --border: #d9e2ef;
      --danger: #cc2f2f;
      --success: #128a52;
      --shadow: 0 12px 32px rgba(16, 35, 63, 0.10);
      --radius: 20px;
    }

    * { box-sizing: border-box; }

    html, body {
      margin: 0;
      padding: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      -webkit-text-size-adjust: 100%;
    }

    body {
      min-height: 100vh;
      padding:
        max(16px, env(safe-area-inset-top))
        16px
        max(20px, env(safe-area-inset-bottom))
        16px;
    }

    .wrap {
      width: 100%;
      max-width: 760px;
      margin: 0 auto;
    }

    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      overflow: hidden;
    }

    .hero {
      padding: 22px 18px 18px;
      background: linear-gradient(180deg, #eef5ff 0%, #ffffff 100%);
      border-bottom: 1px solid var(--border);
    }

    .title {
      margin: 0;
      font-size: 28px;
      line-height: 1.15;
      font-weight: 800;
      letter-spacing: -0.02em;
    }

    .subtitle {
      margin: 10px 0 0;
      color: var(--muted);
      font-size: 15px;
      line-height: 1.55;
    }

    .content {
      padding: 18px;
    }

    .label {
      display: block;
      margin-bottom: 10px;
      font-size: 16px;
      font-weight: 700;
    }

    .dropzone {
      border: 2px dashed #9db8e8;
      border-radius: 18px;
      background: #f9fbff;
      padding: 16px;
    }

    .file-input {
      display: block;
      width: 100%;
      min-height: 56px;
      padding: 14px;
      font-size: 16px;
      line-height: 1.4;
      color: var(--text);
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: 14px;
      outline: none;
      -webkit-appearance: none;
      appearance: none;
    }

    .file-input:focus {
      border-color: var(--primary);
      box-shadow: 0 0 0 4px rgba(23, 105, 255, 0.12);
    }

    .tips {
      margin-top: 12px;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.6;
    }

    .actions {
      margin-top: 18px;
      display: grid;
      gap: 12px;
    }

    .btn {
      width: 100%;
      min-height: 56px;
      border: 0;
      border-radius: 16px;
      padding: 14px 18px;
      font-size: 18px;
      font-weight: 800;
      letter-spacing: 0.01em;
      cursor: pointer;
      -webkit-appearance: none;
      appearance: none;
      touch-action: manipulation;
      transition: transform .02s ease, background .2s ease, opacity .2s ease;
    }

    .btn:active {
      transform: scale(0.99);
    }

    .btn-primary {
      color: #ffffff;
      background: var(--primary);
    }

    .btn-primary:disabled {
      cursor: not-allowed;
      opacity: 0.65;
      background: #8eb0f0;
    }

    .status {
      margin-top: 16px;
      min-height: 24px;
      font-size: 15px;
      line-height: 1.6;
      color: var(--muted);
      word-break: break-word;
    }

    .status.error { color: var(--danger); }
    .status.success { color: var(--success); }

    .list {
      margin: 10px 0 0;
      padding-left: 18px;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.7;
    }

    .overlay {
      position: fixed;
      inset: 0;
      background: rgba(10, 20, 38, 0.55);
      display: none;
      align-items: center;
      justify-content: center;
      z-index: 9999;
      padding:
        max(16px, env(safe-area-inset-top))
        16px
        max(20px, env(safe-area-inset-bottom))
        16px;
    }

    .overlay.show { display: flex; }

    .overlay-card {
      width: 100%;
      max-width: 360px;
      background: #ffffff;
      border-radius: 20px;
      padding: 22px 18px;
      text-align: center;
      box-shadow: 0 16px 40px rgba(0, 0, 0, 0.22);
    }

    .spinner {
      width: 44px;
      height: 44px;
      margin: 0 auto 14px;
      border: 4px solid #dbe6fb;
      border-top-color: var(--primary);
      border-radius: 50%;
      animation: spin 0.9s linear infinite;
    }

    @keyframes spin {
      from { transform: rotate(0deg); }
      to { transform: rotate(360deg); }
    }

    .overlay-title {
      margin: 0;
      font-size: 19px;
      font-weight: 800;
    }

    .overlay-text {
      margin: 10px 0 0;
      color: var(--muted);
      font-size: 15px;
      line-height: 1.6;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <div class="hero">
        <h1 class="title">PDF Delivery Note Tool</h1>
        <p class="subtitle">
          Upload nhiều file PDF cùng lúc. Hệ thống sẽ tự đọc ETA, xác định Line No để chia vào thư mục 1F hoặc 2F,
          chuyển trang đầu sang ảnh PNG 300 DPI để giữ nét chữ sát bản gốc hơn và trả về 1 file ZIP.
        </p>
      </div>

      <div class="content">
        <form id="uploadForm">
          <label class="label" for="files">Chọn file PDF</label>
          <div class="dropzone">
            <input id="files" class="file-input" type="file" name="files" accept=".pdf" multiple required>
            <div class="tips">
              Hỗ trợ chọn nhiều file từ ứng dụng Tệp trên iPhone. Tool sẽ xử lý tuần tự từng file để tiết kiệm RAM.
            </div>
          </div>

          <div class="actions">
            <button id="submitBtn" class="btn btn-primary" type="submit">Bắt đầu xử lý</button>
          </div>
        </form>

        <div id="status" class="status"></div>
        <ul id="fileList" class="list"></ul>
      </div>
    </div>
  </div>

  <div id="loadingOverlay" class="overlay" aria-hidden="true">
    <div class="overlay-card">
      <div class="spinner" aria-hidden="true"></div>
      <h2 class="overlay-title">Đang xử lý PDF...</h2>
      <p class="overlay-text">
        Vui lòng giữ nguyên trang này. Server đang đọc ETA, phân loại Line No, xuất ảnh PNG chất lượng cao và nén ZIP.
      </p>
    </div>
  </div>

  <script>
    const form = document.getElementById('uploadForm');
    const fileInput = document.getElementById('files');
    const statusBox = document.getElementById('status');
    const fileList = document.getElementById('fileList');
    const submitBtn = document.getElementById('submitBtn');
    const overlay = document.getElementById('loadingOverlay');

    let isProcessing = false;

    function setStatus(message, type = '') {
      statusBox.className = 'status' + (type ? ' ' + type : '');
      statusBox.textContent = message || '';
    }

    function setBusy(busy) {
      isProcessing = busy;
      submitBtn.disabled = busy;
      fileInput.disabled = busy;
      overlay.classList.toggle('show', busy);
      window.onbeforeunload = busy
        ? function (event) {
            event.preventDefault();
            event.returnValue = 'Đang xử lý file. Rời khỏi trang có thể làm gián đoạn quá trình.';
            return event.returnValue;
          }
        : null;
    }

    function showSelectedFiles() {
      fileList.innerHTML = '';
      const files = Array.from(fileInput.files || []);
      if (!files.length) {
        setStatus('');
        return;
      }

      files.forEach((file) => {
        const li = document.createElement('li');
        li.textContent = `${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`;
        fileList.appendChild(li);
      });

      setStatus(`Đã chọn ${files.length} file PDF.`, 'success');
    }

    function getFilenameFromDisposition(headerValue) {
      if (!headerValue) return 'result.zip';

      const utf8Match = headerValue.match(/filename\*=UTF-8''([^;]+)/i);
      if (utf8Match && utf8Match[1]) {
        return decodeURIComponent(utf8Match[1]);
      }

      const asciiMatch = headerValue.match(/filename="?([^";]+)"?/i);
      if (asciiMatch && asciiMatch[1]) {
        return asciiMatch[1];
      }

      return 'result.zip';
    }

    async function downloadBlob(blob, filename) {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.rel = 'noopener';
      a.style.display = 'none';
      document.body.appendChild(a);
      a.click();
      setTimeout(() => {
        URL.revokeObjectURL(url);
        a.remove();
      }, 1000);
    }

    fileInput.addEventListener('change', showSelectedFiles);

    form.addEventListener('submit', async function (event) {
      event.preventDefault();

      const files = Array.from(fileInput.files || []);
      if (!files.length) {
        setStatus('Vui lòng chọn ít nhất 1 file PDF.', 'error');
        return;
      }

      const invalid = files.find((file) => !file.name.toLowerCase().endsWith('.pdf'));
      if (invalid) {
        setStatus(`File không hợp lệ: ${invalid.name}. Chỉ chấp nhận PDF.`, 'error');
        return;
      }

      const formData = new FormData();
      files.forEach((file) => formData.append('files', file));

      try {
        setBusy(true);
        setStatus(`Đang upload và xử lý ${files.length} file...`);

        const response = await fetch('/process', {
          method: 'POST',
          body: formData,
          cache: 'no-store'
        });

        if (!response.ok) {
          let message = 'Xử lý thất bại.';
          try {
            const data = await response.json();
            if (data && data.error) {
              message = data.error;
            }
          } catch (_) {}
          throw new Error(message);
        }

        const blob = await response.blob();
        const filename = getFilenameFromDisposition(response.headers.get('Content-Disposition'));
        await downloadBlob(blob, filename);

        const processed = response.headers.get('X-Processed-Count');
        const skipped = response.headers.get('X-Skipped-Count');
        const detail = processed
          ? `Hoàn tất. Đã xử lý ${processed} file${skipped ? `, bỏ qua ${skipped} file.` : '.'}`
          : 'Hoàn tất. File ZIP đang được tải về.';

        setStatus(detail, 'success');
      } catch (error) {
        setStatus(error.message || 'Đã xảy ra lỗi không xác định.', 'error');
      } finally {
        setBusy(false);
      }
    });
  </script>
</body>
</html>
"""


def normalize_text(text: str) -> str:
    """Normalize extracted PDF text so regex is more reliable."""
    text = text or ""
    text = text.replace("\r", "\n").replace("\u00a0", " ")

    # Join line-no patterns split by line breaks, e.g. C1-\n064D -> C1-064D
    text = re.sub(r"(C[12])\s*-\s*\n\s*([A-Z0-9]+)", r"\1-\2", text, flags=re.IGNORECASE)

    # General fix for hyphenated tokens broken by line breaks.
    text = re.sub(r"([A-Za-z0-9])\s*-\s*\n\s*([A-Za-z0-9])", r"\1-\2", text)

    # Collapse internal whitespace without losing structure completely.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


def parse_eta(text: str) -> Optional[datetime]:
    match = ETA_PATTERN.search(text)
    if not match:
        return None

    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def parse_folder_from_line_no(text: str) -> Tuple[Optional[str], Optional[str]]:
    match = LINE_PATTERN.search(text)
    if not match:
        return None, None

    prefix = match.group(1).upper()
    suffix = match.group(2).upper()
    line_no = f"{prefix}-{suffix}"

    if prefix == "C1":
        return "1F", line_no
    if prefix == "C2":
        return "2F", line_no
    return None, line_no


def extract_folder_from_tables(page) -> Tuple[Optional[str], Optional[str]]:
    """Extract folder using the Line No. column when pdfplumber can read the table."""
    try:
        tables = page.extract_tables() or []
    except Exception:
        tables = []

    for table in tables:
        if not table or not table[0]:
            continue

        header = [(cell or "") for cell in table[0]]
        line_col_idx = None

        for idx, cell in enumerate(header):
            header_text = re.sub(r"\s+", " ", (cell or "")).strip().lower()
            if "line" in header_text and "no" in header_text:
                line_col_idx = idx
                break

        if line_col_idx is None:
            continue

        for row in table[1:]:
            if not row or line_col_idx >= len(row):
                continue

            cell_text = row[line_col_idx] or ""
            normalized_cell = re.sub(r"\s+", "", cell_text).upper()
            folder, line_no = parse_folder_from_line_no(normalized_cell)
            if folder is not None:
                return folder, line_no

    return None, None


def extract_pdf_info(pdf_path: str) -> Tuple[Optional[datetime], Optional[str], Optional[str]]:
    """
    Scan pages one by one to keep memory usage low.
    Stop early when ETA and folder are both found.
    """
    eta_value: Optional[datetime] = None
    folder: Optional[str] = None
    line_no: Optional[str] = None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = normalize_text(page.extract_text() or "")

            if eta_value is None:
                eta_value = parse_eta(text)

            if folder is None:
                folder, line_no = extract_folder_from_tables(page)

            if folder is None:
                folder, line_no = parse_folder_from_line_no(text)

            del text
            gc.collect()

            if eta_value is not None and folder is not None:
                break

    return eta_value, folder, line_no


def save_upload_stream(file_storage, output_path: str) -> None:
    """Save uploaded file to disk in chunks to avoid loading whole file into RAM."""
    file_storage.stream.seek(0)
    with open(output_path, "wb") as output_file:
        shutil.copyfileobj(file_storage.stream, output_file, length=1024 * 1024)


def render_first_page_to_png(pdf_path: str, output_png_path: str, temp_render_dir: str) -> None:
    """
    Convert only the first page at 300 DPI.
    Use paths_only=True so pdf2image writes directly to disk instead of keeping PIL images in RAM.
    """
    generated_paths = convert_from_path(
        pdf_path,
        dpi=300,
        first_page=1,
        last_page=1,
        fmt="png",
        use_pdftocairo=True,
        transparent=False,
        output_folder=temp_render_dir,
        paths_only=True,
        thread_count=1,
    )

    if not generated_paths:
        raise RuntimeError("Không thể chuyển trang đầu của PDF sang ảnh PNG.")

    shutil.move(generated_paths[0], output_png_path)


def ensure_unique_filename(filename: str, used_names: set) -> str:
    safe_name = secure_filename(filename) or f"file_{uuid.uuid4().hex}.pdf"

    if not safe_name.lower().endswith(".pdf"):
        safe_name += ".pdf"

    base, ext = os.path.splitext(safe_name)
    candidate = safe_name
    counter = 1

    while candidate.lower() in used_names:
        candidate = f"{base}_{counter}{ext}"
        counter += 1

    used_names.add(candidate.lower())
    return candidate


def build_zip(zip_path: str, folder_1f: str, folder_2f: str) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for folder_name, folder_path in (("1F", folder_1f), ("2F", folder_2f)):
            zf.writestr(f"{folder_name}/", "")
            for root, _, files in os.walk(folder_path):
                for filename in sorted(files):
                    full_path = os.path.join(root, filename)
                    arcname = os.path.relpath(full_path, start=os.path.dirname(folder_path))
                    zf.write(full_path, arcname=arcname)


def process_files(uploaded_files: List) -> Tuple[str, str, int, int]:
    earliest_eta: Optional[datetime] = None
    processed_count = 0
    skipped_count = 0

    with tempfile.TemporaryDirectory(prefix="pdf_tool_") as tmp_root:
        input_dir = os.path.join(tmp_root, "input")
        render_temp_dir = os.path.join(tmp_root, "render_temp")
        folder_1f = os.path.join(tmp_root, "1F")
        folder_2f = os.path.join(tmp_root, "2F")

        os.makedirs(input_dir, exist_ok=True)
        os.makedirs(render_temp_dir, exist_ok=True)
        os.makedirs(folder_1f, exist_ok=True)
        os.makedirs(folder_2f, exist_ok=True)

        used_names = set()

        for uploaded_file in uploaded_files:
            if not uploaded_file or not uploaded_file.filename:
                skipped_count += 1
                continue

            unique_name = ensure_unique_filename(uploaded_file.filename, used_names)
            pdf_path = os.path.join(input_dir, unique_name)

            try:
                save_upload_stream(uploaded_file, pdf_path)
                eta_value, folder, _line_no = extract_pdf_info(pdf_path)

                if eta_value is not None and (earliest_eta is None or eta_value < earliest_eta):
                    earliest_eta = eta_value

                if folder is None:
                    skipped_count += 1
                    continue

                output_folder = folder_1f if folder == "1F" else folder_2f
                image_name = os.path.splitext(unique_name)[0] + ".png"
                output_png_path = os.path.join(output_folder, image_name)

                render_first_page_to_png(pdf_path, output_png_path, render_temp_dir)
                processed_count += 1
            finally:
                if os.path.exists(pdf_path):
                    try:
                        os.remove(pdf_path)
                    except OSError:
                        pass

                # Clean any residual render temp files after each PDF.
                for name in os.listdir(render_temp_dir):
                    temp_item = os.path.join(render_temp_dir, name)
                    try:
                        if os.path.isfile(temp_item):
                            os.remove(temp_item)
                    except OSError:
                        pass

                gc.collect()

        if processed_count == 0:
            raise ValueError("Không có file PDF nào được xử lý thành công. Hãy kiểm tra lại ETA và Line No trong file.")

        zip_basename = earliest_eta.strftime("%Y-%m-%d_%H_%M") if earliest_eta else "no_eta"
        zip_filename = f"{zip_basename}.zip"
        zip_path = os.path.join(tmp_root, zip_filename)
        build_zip(zip_path, folder_1f, folder_2f)

        final_zip_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4().hex}_{zip_filename}")
        shutil.copy2(zip_path, final_zip_path)

    return final_zip_path, zip_filename, processed_count, skipped_count


@app.route("/", methods=["GET"])
def index():
    return render_template_string(PAGE_HTML)


@app.route("/process", methods=["POST"])
def process_route():
    uploaded_files = request.files.getlist("files")
    valid_files = [f for f in uploaded_files if f and f.filename]

    if not valid_files:
        return jsonify({"error": "Vui lòng chọn ít nhất 1 file PDF."}), 400

    non_pdf = [f.filename for f in valid_files if not f.filename.lower().endswith(".pdf")]
    if non_pdf:
        return jsonify({"error": f"Chỉ chấp nhận file PDF. File không hợp lệ: {non_pdf[0]}"}), 400

    try:
        zip_path, download_name, processed_count, skipped_count = process_files(valid_files)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    response = send_file(
        zip_path,
        mimetype="application/zip",
        as_attachment=True,
        download_name=download_name,
        max_age=0,
        conditional=False,
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Processed-Count"] = str(processed_count)
    response.headers["X-Skipped-Count"] = str(skipped_count)
    response.call_on_close(lambda: os.path.exists(zip_path) and os.remove(zip_path))
    return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
