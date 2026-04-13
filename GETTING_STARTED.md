# 🎬 SRT Translator Optimized - Getting Started (5 phút)

Hướng dẫn bắt đầu **NHANH NHẤT** - Chỉ cần 5 phút để setup & chạy.

---

## ⚡ Quick Start (Cho người vội)

### Bước 1: Cài Dependencies (1 phút)
```bash
pip install -r requirements-translator.txt
```

### Bước 2: Setup API Key (1 phút)
Lấy API Key từ Google Gemini: https://ai.google.dev/

Đặt vào biến môi trường:
```bash
# Windows PowerShell
[Environment]::SetEnvironmentVariable("GOOGLE_API_KEY", "YOUR_KEY_HERE", "User")

# Linux/Mac
export GOOGLE_API_KEY="YOUR_KEY_HERE"
```

### Bước 3: Chuẩn bị File Input (0 phút)
- Đặt file `input.srt` cùng thư mục script

### Bước 4: Chạy Script (2 phút)
```bash
# Windows
python srt_translator_optimized.py

# Linux/Mac
python3 srt_translator_optimized.py
```

### Kết Quả:
```
✅ translated_final.srt       (File SRT đã dịch)
✅ output_audio/              (Folder MP3)
✅ process.log                (Nhật ký chi tiết)
✅ progress.json              (Checkpoint)
```

---

## 🎯 Chạy Từ Menu Interactive (KHUYẾN KHÍCH)

### Windows:
```bash
RUN_TRANSLATOR.bat
```
→ Menu cho phép chọn lệnh dễ dàng

### Linux/Mac:
```bash
bash run_translator.sh
```
→ Menu CLI giống Windows

**Từ menu này bạn có thể:**
1. Quick Start (setup lần đầu)
2. Run Translator (chạy dịch)
3. Test Checkpoint
4. Setup Dependencies
5. View Logs
6. View Progress

---

## 📖 Hướng Dẫn Chi Tiết

Nếu muốn hiểu chi tiết hơn, xem các file:

| File | Mục Đích |
|------|---------|
| `SRT_TRANSLATOR_README.md` | 📚 Hướng dẫn đầy đủ (tất cả tính năng) |
| `FILE_INDEX.md` | 📚 Chỉ mục tất cả file |
| `IMPLEMENTATION_SUMMARY.md` | 🔧 Cách implement từng tính năng |
| `config_examples.py` | ⚙️ Các ví dụ cấu hình |

---

## 🎓 Ví Dụ: Lần Đầu Chạy

### 1. Setup lần đầu:
```bash
python QUICK_START.py
```
→ Hướng dẫn từng bước

### 2. Hoặc dùng menu:
```bash
RUN_TRANSLATOR.bat    # Windows
bash run_translator.sh # Linux/Mac
```
→ Chọn "1. QUICK START"

### 3. Chạy dịch:
```bash
python srt_translator_optimized.py
# Hoặc từ menu: Chọn "2. RUN TRANSLATOR"
```

### 4. Nếu bị dừng (Ctrl+C):
```bash
python srt_translator_optimized.py  # Chạy lại
# Auto-resume từ dòng cuối nhờ checkpoint!
```

---

## 💡 Tips

### Optimize Tốc Độ:
```python
# Mở file srt_translator_optimized.py
CONFIG = {
    ...
    "batch_size": 50,       # Tăng từ 35 → 50 (nhanh hơn)
    "tts_concurrent": 8,    # Tăng từ 6 → 8 (nhanh hơn)
    ...
}
```

### Optimize Chất Lượng:
```python
CONFIG = {
    ...
    "model": "gemini-1.5-pro",  # Chất lượng tốt hơn
    "batch_size": 25,           # Batch nhỏ hơn
    "tts_concurrent": 4,        # Ít task hơn
    ...
}
```

### Xem Log Chi Tiết:
```bash
# Tail log file (real-time)
tail -f process.log              # Linux/Mac
type process.log | more          # Windows

# Từ menu: Chọn "5. VIEW LOGS"
```

### Xem Progress:
```bash
cat progress.json    # Linux/Mac
type progress.json   # Windows

# Từ menu: Chọn "6. VIEW PROGRESS"
```

---

## ⚠️ Troubleshoot Nhanh

| Vấn đề | Giải Pháp |
|--------|---------|
| `ModuleNotFoundError: No module named 'google'` | Chạy: `pip install -r requirements-translator.txt` |
| `API key not valid` | Kiểm tra `GOOGLE_API_KEY` env var hoặc sửa config |
| `FileNotFoundError: input.srt` | Đặt file input.srt cùng thư mục script |
| `No audio received` | Giảm `tts_concurrent` từ 6 → 3-4 |
| Bị dừng giữa chừng | Chạy lại, sẽ auto-resume từ dòng cuối |

---

## 🚀 Next Steps

1. **Lần đầu**: Chạy `QUICK_START.py` hoặc dùng menu `RUN_TRANSLATOR.bat/sh`
2. **Chạy dịch**: `python srt_translator_optimized.py`
3. **Nếu cần chi tiết**: Xem `SRT_TRANSLATOR_README.md`
4. **Custom config**: Chỉnh sửa `CONFIG = {...}` trong script

---

## 📞 Quick Reference

```bash
# Cài dependencies
pip install -r requirements-translator.txt

# Setup lần đầu
python QUICK_START.py

# Chạy dịch
python srt_translator_optimized.py

# Test checkpoint
python test_checkpoint.py

# Check dependencies
python setup_dependencies.py

# Dùng menu (Windows)
RUN_TRANSLATOR.bat

# Dùng menu (Linux/Mac)
bash run_translator.sh
```

---

## ✅ Checklist Trước Chạy

- [ ] Cài pip packages: `pip install -r requirements-translator.txt`
- [ ] Set `GOOGLE_API_KEY` environment variable
- [ ] Đặt file `input.srt` cùng thư mục
- [ ] Check file `srt_translator_optimized.py` tồn tại
- [ ] Chạy: `python srt_translator_optimized.py`

**Xong! 🎉**

---

*Duration: ~ 5 minutes*  
*Last Updated: 2026-04-13*
