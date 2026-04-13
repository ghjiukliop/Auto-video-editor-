# 🎬 SRT Translator Optimized - Hướng Dẫn Sử Dụng

## 📋 Tính Năng Chính

### 1. **Cơ Chế Checkpoint** ✅
- Lưu tiến độ vào `progress.json` sau mỗi batch
- Nếu bị dừng đột ngột (mất mạng, lỗi API), chỉ cần chạy lại sẽ tự tiếp tục từ dòng cuối
- Không cần xử lý lại các dòng đã hoàn thành

### 2. **Dịch JSON-based** 🎯
- Yêu cầu Gemini trả về JSON format: `{"0": "dòng dịch 0", "1": "dòng dịch 1", ...}`
- Tránh hoàn toàn việc AI trả về sai thứ tự dòng
- Validate JSON để đảm bảo không bỏ sót dòng nào

### 3. **TTS Queue Management** 🎤
- Giới hạn max **6 task TTS chạy đồng thời** (tránh bị Microsoft chặn)
- Dùng `asyncio.Semaphore` để queuing
- Retry 3 lần với exponential backoff (2s, 4s, 8s)

### 4. **Logging Chuyên Nghiệp** 📝
- Ghi chi tiết vào `process.log` với timestamp
- Format: `[HH:MM:SS] | LEVEL | Function | Message`
- Vừa file vừa console output

### 5. **Text Cleaning** 🧹
- Xóa markdown (**, __, etc)
- Xóa ngoặc vuông & nhọn
- Chuyển dấu câu Trung Quốc → Việt Nam
- Xóa ký tự điều khiển lạ

---

## 🚀 Cài Đặt & Chạy

### 1. **Cài Dependencies**
```bash
pip install google-generativeai pysubs2 edge-tts
```

### 2. **Cấu Hình API Key**
```bash
# Windows PowerShell
[Environment]::SetEnvironmentVariable("GOOGLE_API_KEY", "YOUR_KEY_HERE", "User")

# Linux/Mac
export GOOGLE_API_KEY="YOUR_KEY_HERE"

# Hoặc sửa trực tiếp trong script
CONFIG = {
    "api_key": "YOUR_KEY_HERE",  # Dán API key Google Gemini
    ...
}
```

### 3. **Chuẩn Bị File Input**
```
- Đặt file `input.srt` cùng thư mục script
- Hoặc sửa CONFIG["input_srt"] = "đường/dẫn/file.srt"
```

### 4. **Chạy Script**
```bash
python srt_translator_optimized.py
```

### 5. **Kết Quả Output**
```
translated_final.srt        # File SRT đã dịch (cập nhật realtime)
output_audio/               # Thư mục chứa MP3 dòng (line_00000.mp3, line_00001.mp3, ...)
process.log                 # Nhật ký chi tiết
progress.json               # Checkpoint tiến độ (tự động update)
```

---

## ⚙️ Cấu Hình Tùy Chỉnh

```python
CONFIG = {
    # API & Model
    "api_key": "YOUR_GOOGLE_API_KEY",
    "model": "gemini-1.5-flash",  # Nhanh & rẻ, hoặc dùng gemini-1.5-pro cho chất lượng cao
    
    # TTS
    "voice": "vi-VN-HoaiMyNeural",  # Giọng Hoài My (nữ), hoặc:
    # "vi-VN-NamMinhNeural"         # Giọng Nam Minh (nam)
    
    # File I/O
    "input_srt": "input.srt",
    "output_srt": "translated_final.srt",
    "audio_folder": "output_audio",
    
    # Processing
    "batch_size": 35,          # Dòng/batch (nên 30-50)
    "tts_concurrent": 6,       # Số task TTS chạy cùng lúc (tránh bị rate-limit, 5-10 là tốt)
    
    # Files
    "checkpoint_file": "progress.json",
    "log_file": "process.log",
}
```

---

## 💡 Mẹo & Lưu Ý

### Tối Ưu Tốc Độ
- Tăng `batch_size` lên 50 nếu muốn dịch 1 lần với context lớn hơn
- Tăng `tts_concurrent` lên 8-10 nếu server không bị lag
- Dùng `gemini-1.5-flash` (rẻ) hoặc `gemini-2.0-flash` (mới nhất)

### Chất Lượng Dịch
- Tuỳ chỉnh prompt trong hàm `translate_batch_json()` để thêm hướng dẫn dịch
- Thêm glossary (danh sách tên riêng) nếu muốn đồng nhất tên nhân vật

### Debug & Troubleshoot
- Kiểm tra `process.log` chi tiết để tìm dòng nào lỗi
- Nếu bị rate-limit, tăng delay: `await asyncio.sleep(5)` thay vì 3
- Nếu TTS bị timeout, giảm `tts_concurrent` xuống còn 3-4

### Resume Chạy Lại
```bash
# Chạy lại sẽ tự tiếp tục từ dòng cuối:
python srt_translator_optimized.py

# Nếu muốn reset & chạy từ đầu:
rm progress.json
python srt_translator_optimized.py
```

---

## 📊 Ví Dụ Output

### Dòng Log
```
2026-04-13 14:32:10,123 | INFO     | main                | 🚀 BẮT ĐẦU: SRT Translator Optimized
2026-04-13 14:32:11,456 | INFO     | main                | 📖 Đã nạp 10000 dòng từ input.srt
2026-04-13 14:32:11,789 | INFO     | main                | 📌 Tiếp tục từ dòng 2500 (lần trước xử lý đến 2499)
2026-04-13 14:32:12,012 | INFO     | main                | 📦 BATCH: dòng 2500-2534/9999
2026-04-13 14:32:45,678 | INFO     | translate_batch_json| ✅ Dịch thành công 35 dòng
2026-04-13 14:32:46,890 | INFO     | main                | 🎵 TTS 35 dòng (tối đa 6 cùng lúc)...
2026-04-13 14:33:15,234 | DEBUG    | speak_line          | ✅ TTS dòng 2500 thành công
...
2026-04-13 14:45:00,000 | INFO     | main                | 🎉 HOÀN THÀNH!
```

### Checkpoint JSON
```json
{
  "last_processed_line": 2534,
  "total_lines": 10000,
  "timestamp": "2026-04-13T14:32:46.123456"
}
```

---

## ⚠️ Xử Lý Lỗi

| Lỗi | Nguyên Nhân | Giải Pháp |
|-----|-----------|---------|
| `FileNotFoundError: input.srt` | File không tồn tại | Đặt file input.srt cùng thư mục hoặc sửa `input_srt` config |
| `API key not valid` | API key sai | Kiểm tra lại Google API key |
| `No audio received` | TTS delay quá lâu | Giảm `tts_concurrent` xuống 3-4 |
| `JSON decode error` | AI trả về response không hợp lệ | Thường do prompt quá phức tạp, giảm batch_size |
| `Timeout` | Request timeout | Tăng timeout trong code hoặc kiểm tra mạng |

---

## 📚 Công Nghệ Dùng

- **Google Gemini**: Dịch AI (gemini-1.5-flash tốc độ hoặc gemini-1.5-pro chất lượng)
- **edge-tts**: Text-to-Speech Microsoft (Hoài My, Nam Minh, v.v)
- **pysubs2**: Xử lý file SRT
- **asyncio**: Async task management
- **json**: Response parsing

---

## 📞 Support

Nếu gặp vấn đề:
1. Kiểm tra `process.log` để thấy lỗi chi tiết
2. Xem mục "Xử Lý Lỗi" ở trên
3. Thử reset bằng `rm progress.json` và chạy lại

---

*Last Updated: 2026-04-13*
