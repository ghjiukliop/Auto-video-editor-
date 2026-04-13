# 🎬 SRT Translator Optimized - Vietnamese Dubbing Solution

**Giải pháp dịch SRT Trung → Việt tự động với AI + TTS, hỗ trợ file siêu dài (10.000+ dòng)**

---

## ✨ Tính Năng Chính

✅ **Checkpoint & Resume** - Lưu tiến độ, tiếp tục nếu bị dừng  
✅ **Dịch JSON-based** - AI trả về JSON, không bao giờ lệch dòng  
✅ **TTS Queue Management** - Giới hạn 6-10 task TTS, tránh bị rate-limit  
✅ **Logging Chuyên Nghiệp** - Ghi nhật ký chi tiết vào file  
✅ **Text Cleaning** - Xóa ký tự rác, dấu punctuation Trung Quốc  
✅ **Config Presets** - 5 cấu hình sẵn (Speed, Quality, Male Voice, v.v)  

---

## 🚀 Bắt Đầu Nhanh Nhất (5 phút)

### 1. Cài Dependencies
```bash
pip install -r requirements-translator.txt
```

### 2. Setup API Key
```bash
# Get API: https://ai.google.dev/
[Environment]::SetEnvironmentVariable("GOOGLE_API_KEY", "YOUR_KEY", "User")  # Windows
export GOOGLE_API_KEY="YOUR_KEY"  # Linux/Mac
```

### 3. Chuẩn Bị File Input
- Đặt `input.srt` cùng thư mục script

### 4. Chạy
```bash
python srt_translator_optimized.py
```

**Output**: `translated_final.srt`, `output_audio/`, `process.log`, `progress.json`

📖 **Chi tiết hơn?** → Xem [GETTING_STARTED.md](GETTING_STARTED.md)

---

## 📁 Danh Sách File

### 🎯 **QUAN TRỌNG NHẤT** (Script Chính)
```
📄 srt_translator_optimized.py      ⭐ Script chính - Tất cả tính năng
📄 QUICK_START.py                   🚀 Interactive setup guide
```

### 📚 Hướng Dẫn & Documentation
```
📖 GETTING_STARTED.md               ⚡ Bắt đầu nhanh (5 phút)
📖 SRT_TRANSLATOR_README.md         📚 Hướng dẫn chi tiết đầy đủ
📖 FILE_INDEX.md                    📑 Chi mục tất cả file
📖 IMPLEMENTATION_SUMMARY.md        🔧 Cách implement từng tính năng
📖 README.md                        📋 File này
```

### ⚙️ Công Cụ & Cấu Hình
```
📄 config_examples.py               ⚙️ 5 config presets
📄 setup_dependencies.py            🔧 Check dependencies
📄 test_checkpoint.py               🧪 Test checkpoint feature
📄 requirements-translator.txt      📦 Pip requirements
```

### 🎮 Scripts Chạy (Menu Interactive)
```
📄 RUN_TRANSLATOR.bat               🎮 Menu Windows
📄 run_translator.sh                🎮 Menu Linux/Mac
```

---

## 💡 Cách Dùng Từng File

### 🎯 Lần Đầu Tiên?
```bash
python QUICK_START.py
# Hoặc
RUN_TRANSLATOR.bat        # Windows
bash run_translator.sh    # Linux/Mac
```
→ Hướng dẫn từng bước, check dependencies, setup API Key

### 🎬 Chạy Dịch?
```bash
python srt_translator_optimized.py
# Hoặc chọn từ menu: "2. RUN TRANSLATOR"
```

### 🧪 Test Checkpoint?
```bash
python test_checkpoint.py
# Hoặc chọn từ menu: "3. TEST"
```

### 📝 Xem Log?
```bash
tail -f process.log    # Real-time (Linux/Mac)
type process.log       # Windows
# Hoặc chọn từ menu: "5. VIEW LOGS"
```

### 📊 Xem Progress?
```bash
cat progress.json      # Linux/Mac
type progress.json     # Windows
# Hoặc chọn từ menu: "6. VIEW PROGRESS"
```

---

## 🎓 Ví Dụ Realworld

### Scenario 1: Dịch file 10.000 dòng lần đầu
```bash
# Lần đầu
python QUICK_START.py          # Setup, chọn config
python srt_translator_optimized.py  # Chạy dịch (30-60 phút)

# Output:
# ✅ translated_final.srt (10.000 dòng dịch)
# ✅ output_audio/ (10.000 file MP3)
# ✅ process.log (chi tiết JSON)
# ✅ progress.json (checkpoint)
```

### Scenario 2: Bị dừng giữa chừng, tiếp tục
```bash
# Chạy lại - auto-resume từ dòng cuối
python srt_translator_optimized.py

# Log sẽ show:
# "📌 Tiếp tục từ dòng 5000 (lần trước xử lý đến 4999)"
```

### Scenario 3: Customize config (nhanh hơn)
```python
# Mở srt_translator_optimized.py
CONFIG = {
    ...
    "batch_size": 50,       # Tăng từ 35 → 50 (batch lớn = nhanh)
    "tts_concurrent": 8,    # Tăng từ 6 → 8 (TTS nhiều = nhanh)
    ...
}

# Chạy
python srt_translator_optimized.py
```

---

## 📊 So Sánh Trước / Sau

### Trước (Script Cơ Bản)
❌ Không checkpoint - Bị dừng phải chạy lại từ đầu  
❌ AI có thể trả về sai thứ tự - Dòng không khớp  
❌ TTS bị rate-limit → Lỗi "No audio received"  
❌ Không log chi tiết - Khó debug  
❌ Không làm sạch - Text rác → TTS lỗi  

### Sau (SRT Translator Optimized)
✅ Checkpoint auto-resume - Tiếp tục từ dòng cuối  
✅ JSON parsing chặt chẽ - Luôn đúng thứ tự  
✅ Semaphore limit 6 task - Không bao giờ bị rate-limit  
✅ Logging chi tiết - Biết từng dòng nào xử lý  
✅ Auto-clean text - Dấu punctuation Trung→Việt  

---

## ⚙️ Tùy Chỉnh Config

### Config Presets (Sẵn có 5 cái):
```python
from config_examples import CONFIG_DEFAULT
from config_examples import CONFIG_SPEED      # Nhanh nhất
from config_examples import CONFIG_QUALITY    # Chất lượng cao
from config_examples import CONFIG_MALE_VOICE # Giọng nam
from config_examples import CONFIG_SMALL_FILE # File nhỏ
```

### Hoặc Customize thủ công:
```python
CONFIG = {
    "api_key": "YOUR_KEY",
    "model": "gemini-1.5-flash",          # flash=nhanh, pro=chất lượng
    "voice": "vi-VN-HoaiMyNeural",        # Hoài My hoặc NamMinhNeural
    "input_srt": "input.srt",
    "output_srt": "translated_final.srt",
    "audio_folder": "output_audio",
    "batch_size": 35,                     # 20-50 (lớn=nhanh, nhỏ=chất lượng)
    "tts_concurrent": 6,                  # 3-10 (cao=nhanh, thấp=ổn định)
    "checkpoint_file": "progress.json",
    "log_file": "process.log",
}
```

---

## 🎯 Sơ Đồ Workflow

```
┌─────────────────┐
│  input.srt      │ (File SRT gốc Trung)
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│  CHECKPOINT/RESUME CHECK    │ (Tải progress.json nếu có)
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  BATCH PROCESSING LOOP      │
│  (Batch 1 → Batch N)        │
│                             │
│  1. Translate to JSON       │ (Gemini API)
│  2. Validate JSON Response  │ (No missing lines)
│  3. Update SRT              │ (Thay text dòng)
│  4. TTS (Semaphore Queue)   │ (Max 6 task đồng thời)
│  5. Save Checkpoint         │ (progress.json)
│  6. Log Everything          │ (process.log)
│                             │
└────────┬────────────────────┘
         │
         ▼
┌──────────────────────┐
│  OUTPUT              │
├──────────────────────┤
│ ✅ translated_final.srt │
│ ✅ output_audio/        │
│ ✅ process.log          │
│ ✅ progress.json        │
└──────────────────────┘
```

---

## 📞 FAQ & Troubleshoot

### Q: Bị rate-limit, "No audio received"
**A:** Giảm `tts_concurrent` từ 6 → 3-4 trong CONFIG

### Q: "JSON decode error" từ AI
**A:** AI trả về response không hợp lệ - thường do prompt quá phức tạp
- Giảm `batch_size` từ 35 → 20
- Hoặc đổi model từ `gemini-1.5-flash` → `gemini-1.5-pro`

### Q: Bị dừng giữa chừng, sao khi chạy lại không resume?
**A:** Script có auto-resume, nhưng kiểm tra:
- File `progress.json` tồn tại?
- Dòng cuối đó là gì? (Xem log: `cat progress.json`)

### Q: Muốn dịch nhanh hơn
**A:** Tăng:
- `batch_size`: 35 → 50-60
- `tts_concurrent`: 6 → 10
- `model`: `gemini-1.5-flash` (rẻ & nhanh)

### Q: Muốn dịch chất lượng cao hơn
**A:** Giảm:
- `batch_size`: 35 → 20-25
- `tts_concurrent`: 6 → 3-4
- `model`: `gemini-1.5-pro` (chất lượng)

---

## 🔮 Công Nghệ Dùng

- **Google Gemini 1.5** - Dịch AI (JSON format)
- **Microsoft Edge TTS** - Lồng tiếng (Hoài My, Nam Minh)
- **Python asyncio** - Parallel processing
- **pysubs2** - Xử lý file SRT
- **Logging** - Ghi nhật ký

---

## 📈 Performance

| Điều kiện | Tốc độ |
|-----------|--------|
| File 100 dòng, batch_size=35, tts_concurrent=6 | ~2 phút |
| File 1000 dòng | ~15-20 phút |
| File 10000 dòng | ~2-3 giờ |

**Lưu ý**: Thời gian phụ thuộc vào:
- Tốc độ internet (API call)
- Độ dài dòng (TTS time)
- Cấu hình (batch_size, tts_concurrent)

---

## 📄 License & Credits

Script được tối ưu hoàn toàn từ yêu cầu người dùng:
- ✅ Checkpoint management
- ✅ JSON-based translation
- ✅ TTS queue management
- ✅ Professional logging
- ✅ Text cleaning

---

## 🚀 Getting Started Now

**Cách nhanh nhất:**
```bash
python QUICK_START.py
# Hoặc
RUN_TRANSLATOR.bat  # Windows
bash run_translator.sh # Linux/Mac
```

**Chi tiết?** → Xem [GETTING_STARTED.md](GETTING_STARTED.md)

---

*Version: 1.0 (Stable) | Last Updated: 2026-04-13*
