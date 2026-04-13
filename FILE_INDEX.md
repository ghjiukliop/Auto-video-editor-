# 📚 SRT Translator Optimized - File Index

## 🎯 File Chính (Script)

### 1. **srt_translator_optimized.py** ⭐⭐⭐
**Script chính - Dịch SRT + TTS với tất cả tính năng tối ưu**

Tính năng:
- ✅ Checkpoint/Resume (lưu progress.json)
- ✅ Dịch JSON-based (tránh lệch dòng)
- ✅ TTS Queue Management (Semaphore 5-10 task)
- ✅ Logging chuyên nghiệp (process.log)
- ✅ Text Cleaning (Regex mạnh)

Cách chạy:
```bash
python srt_translator_optimized.py
```

Output:
- `translated_final.srt`: File SRT đã dịch
- `output_audio/`: Thư mục MP3 (line_*.mp3)
- `process.log`: Nhật ký chi tiết
- `progress.json`: Checkpoint tiến độ

---

### 2. **QUICK_START.py** 🚀
**Hướng dẫn bắt đầu nhanh nhất - Interactive menu**

Cách chạy:
```bash
python QUICK_START.py
```

Chức năng:
- Kiểm tra & cài dependencies
- Setup API Key
- Chuẩn bị file input
- Chọn cấu hình (DEFAULT, SPEED, QUALITY, etc)
- Hướng dẫn chạy script chính

---

### 3. **setup_dependencies.py** 🔧
**Công cụ kiểm tra & cài dependencies**

Cách chạy:
```bash
python setup_dependencies.py
```

Chức năng:
- Kiểm tra package cài đặt
- Hướng dẫn cài API Key
- Kiểm tra file input.srt

---

### 4. **test_checkpoint.py** 🧪
**Demo tính năng checkpoint & recovery**

Cách chạy:
```bash
python test_checkpoint.py
```

Chức năng:
- Demo: Chạy, dừng (Ctrl+C), tiếp tục
- Show: Xem checkpoint file hiện tại
- Reset: Xóa checkpoint để chạy lại từ đầu

---

## 📖 File Hướng Dẫn (Documentation)

### 5. **SRT_TRANSLATOR_README.md** 📚
**Hướng dẫn chi tiết, đầy đủ nhất**

Nội dung:
- Tính năng chính
- Cài đặt & chạy
- Cấu hình tùy chỉnh
- Tips & optimization
- Troubleshooting

---

### 6. **config_examples.py** ⚙️
**Các ví dụ cấu hình cho tình huống khác nhau**

Cấu hình sẵn:
- `CONFIG_DEFAULT`: Cân bằng tốc độ & chất lượng (KHUYẾN KHÍCH)
- `CONFIG_SPEED`: Ưu tiên tốc độ (file lớn 10000+ dòng)
- `CONFIG_QUALITY`: Chất lượng cao (phim lịch sử, tài liệu)
- `CONFIG_MALE_VOICE`: Giọng nam
- `CONFIG_SMALL_FILE`: File nhỏ (<1000 dòng)

---

## 📦 File Dependencies

### 7. **requirements-translator.txt**
**File requirements cho pip**

Packages:
- `google-generativeai>=0.7.0` - Google Gemini API
- `pysubs2>=1.1.1` - Xử lý SRT
- `edge-tts>=6.1.8` - Text-to-Speech Microsoft
- `python-dotenv>=1.0.0` - Quản lý env variables

Cài đặt:
```bash
pip install -r requirements-translator.txt
```

---

## 🎓 Hướng Dẫn Sử Dụng (Quick Reference)

### Lần đầu tiên:

1. **Cài dependencies**
   ```bash
   python QUICK_START.py
   # Hoặc
   pip install -r requirements-translator.txt
   ```

2. **Setup API Key**
   ```bash
   # Windows PowerShell
   [Environment]::SetEnvironmentVariable("GOOGLE_API_KEY", "YOUR_KEY", "User")
   
   # Linux/Mac
   export GOOGLE_API_KEY="YOUR_KEY"
   ```

3. **Chuẩn bị file input**
   - Đặt file `input.srt` cùng thư mục script

4. **Chạy script**
   ```bash
   python srt_translator_optimized.py
   ```

### Nếu bị dừng đột ngột:

- Chỉ cần chạy lại: `python srt_translator_optimized.py`
- Script sẽ tư động tiếp tục từ dòng cuối cùng đã xử lý (nhờ `progress.json`)

### Troubleshoot:

- Kiểm tra `process.log` để xem chi tiết lỗi
- Xem `SRT_TRANSLATOR_README.md` mục "Xử Lý Lỗi"

---

## 📊 Tóm Tắt Tính Năng vs File

| Tính Năng | File |
|-----------|------|
| Checkpoint/Resume | srt_translator_optimized.py |
| Dịch JSON-based | srt_translator_optimized.py |
| TTS Queue Management | srt_translator_optimized.py |
| Logging chuyên nghiệp | srt_translator_optimized.py + process.log |
| Text Cleaning | srt_translator_optimized.py |
| Interactive Setup | QUICK_START.py |
| Dependency Check | setup_dependencies.py |
| Test Checkpoint | test_checkpoint.py |
| Config Examples | config_examples.py |
| Documentation | SRT_TRANSLATOR_README.md |

---

## 🚀 Recommended Workflow

```
1️⃣  python QUICK_START.py          # Setup & cấu hình
    |
2️⃣  python srt_translator_optimized.py  # Chạy dịch
    |
    ├─ Nếu lỗi → Xem process.log
    ├─ Nếu bị dừng → Chạy lại, tự resume
    └─ Nếu xong → Kiểm tra output/
```

---

## 💡 Một Số Mẹo

### Optimize Tốc Độ
- Tăng `batch_size` từ 35 → 50
- Tăng `tts_concurrent` từ 6 → 8
- Dùng `gemini-1.5-flash` (nhanh hơn)

### Optimize Chất Lượng
- Giảm `batch_size` từ 35 → 25
- Giảm `tts_concurrent` từ 6 → 4
- Dùng `gemini-1.5-pro` (chất lượng cao)

### Nếu API Bị Rate-Limit
- Giảm `batch_size` xuống 20-25
- Tăng `await asyncio.sleep()` từ 3 → 5s
- Giảm `tts_concurrent` xuống 3

---

## 📝 File Output Tự Động Tạo

Khi chạy script, sẽ tự động tạo:

```
📁 Thư mục/
├─ 📄 translated_final.srt       (File SRT đã dịch)
├─ 📁 output_audio/              (Folder MP3)
│  ├─ line_00000.mp3
│  ├─ line_00001.mp3
│  └─ ...
├─ 📄 process.log                (Nhật ký chi tiết)
└─ 📄 progress.json              (Checkpoint)
```

---

## 🆘 Support & Resources

- **Hướng dẫn chi tiết**: `SRT_TRANSLATOR_README.md`
- **Ví dụ cấu hình**: `config_examples.py`
- **Test checkpoint**: `python test_checkpoint.py`
- **Check dependencies**: `python setup_dependencies.py`

---

*Last Updated: 2026-04-13*
*Version: 1.0 (Stable)*
