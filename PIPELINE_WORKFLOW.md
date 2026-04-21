# 🎬 YouTube Automation Pipeline - Quy Trình Hoạt Động

## 📊 Tổng Quan

Pipeline xử lý video tự động từ đầu vào đến đầu ra hoàn chỉnh:

```
📹 Video Input
    ↓
[STEP 1] 🎵 Tách Audio
    ↓
[STEP 2] 🎤 Nhận Diện Giọng Nói (Whisper)
    ↓
[STEP 3] 🌐 Dịch Phụ Đề (Gemini/Ollama)
    ↓
[STEP 4] 🎬 Tạo Video Hoàn Chỉnh
    ↓
🎥 Video Output
```

---

## 📁 Cấu Trúc Thư Mục

```
YoutubeAutomation/
├── input/
│   ├── VideoInput/          ← Thả video MP4 vào đây
│   ├── AudioInput/          ← Lưu audio được tách (auto)
│   └── SrtInput/            ← Lưu phụ đề gốc (nếu có)
├── output/
│   ├── SrtOutput/           ← Phụ đề đã dịch
│   └── AudioOutput/         ← TTS audio
├── output_videos/           ← Video final (MP4 hoàn chỉnh)
├── modules/                 ← Các module xử lý
├── config.py               ← Cấu hình (Gemini, Ollama)
└── main.py                 ← Entry point
```

---

## 🚀 STEP 1: Tách Audio

**File:** `modules/extract_audio_optimized.py`

```
Video Input (MP4)
    ↓ [FFmpeg]
WAV Audio (44.1kHz, Stereo)
    ↓
Lưu vào: input/AudioInput/{video_name}.wav
```

**Tính Năng:**
- ✅ Parallel processing (multi-thread FFmpeg)
- ✅ Caching (không tách lại nếu đã có)
- ✅ Support MP4, MKV, AVI, etc.

---

## 🎤 STEP 2: Nhận Diện Giọng Nói (Whisper)

**File:** `modules/speech_to_text.py`

### 2️⃣ A. Segment-Based Mode (✨ NEW)

**Khi nào dùng:** Nếu có SRT input ở `input/SrtInput/{video_name}.srt`

```
Audio Input + SRT Input (có timing)
    ↓ [extract_audio_segments()]
Tách thành 15 segments (theo SRT timing)
    ↓ [transcribe_segments_with_whisper()]
Chạy Whisper từng segment riêng
    ↓ [merge_segment_transcriptions()]
Gộp + Điều chỉnh timing từng segment
    ↓
SRT Output (Whisper)
```

**Ưu Điểm:**
- ✅ Lời thoại "ngắt" đúng theo segment
- ✅ Timing chính xác
- ✅ Xử lý nhanh hơn (segments nhỏ)

### 2️⃣ B. Full-Audio Mode (Fallback)

**Khi nào dùng:** Không có SRT input

```
Audio Input (toàn bộ)
    ↓ [Whisper Model]
Nhận diện giọng nói liên tục
    ↓
SRT Output
```

---

## 🌐 STEP 3: Dịch Phụ Đề

**File:** `main.py` → `translate_srt()`

### Translation Engine Priority:

```
SRT Input (Tiếng Trung)
    ↓
1️⃣ TRY GEMINI (Nếu có GEMINI_API_KEY)
    ├─ Kiểm tra kết nối API
    ├─ Chia thành batches (50 dòng/batch)
    ├─ Dịch với gemini-3.1-flash-lite
    └─ Success? → Return
    │
    └─ Fail? → Fallback
    ↓
2️⃣ FALLBACK: OLLAMA (Local)
    ├─ Kiểm tra kết nối Ollama
    ├─ Chia thành batches (5 dòng/batch)
    ├─ Dịch với local LLM (gemma:7b)
    └─ Return
    ↓
SRT Output (Tiếng Việt)
```

### Chi Tiết Từng Bộ Dịch:

#### **Gemini 3.1 Flash Lite** 💎
```python
Model: gemini-3.1-flash-lite
Batch Size: 50 dòng
Max Retries: 3 lần
Rate Limit Handling: Exponential backoff
```

**Prompt:** "Dịch danh sách sau sang TIẾNG VIỆT"

**Format:**
```
Input:  0|我叫悠雨
Output: 0|Tôi tên là Du Vũ

Input:  1|我穿越到了一个有着魔法少女的世界
Output: 1|Tôi đã chuyển sang một thế giới có cô gái phép thuật
```

#### **Ollama (Local LLM)** 🚀
```python
Model: gemma:7b (hoặc tuỳ chọn)
Batch Size: 5 dòng
Host: http://localhost:11434
Timeout: Infinity (offline)
```

**Prompt:** "Dịch từng câu sau sang TIẾNG VIỆT (không phải tiếng Anh, không phải tiếng Trung)"

---

## 🎬 STEP 4: Compose Video

**File:** `pipeline_full.py`

```
Video Input (toàn bộ)
    ├─ Tách audio cũ
    ├─ Tạo TTS (Text-to-Speech)
    │   └─ Chuyển text (Tiếng Việt) thành audio
    ├─ Gộp audio TTS
    ├─ Thêm phụ đề
    └─ Encode MP4 mới
        ↓
Video Output (Final)
```

**Tính Năng:**
- ✅ Sync phụ đề (SRT timing)
- ✅ Replace audio gốc bằng TTS
- ✅ Áp dụng các filter/effect nếu cần

---

## 🔄 Smart Resume

Pipeline **tự động quét** project status:

```
1. Video trong input/VideoInput/ chưa có audio?
   → NEXT_STEP = STEP 1 (Tách Audio)

2. Có audio nhưng chưa có SRT?
   → NEXT_STEP = STEP 2 (Whisper)

3. Có SRT nhưng chưa dịch?
   → NEXT_STEP = STEP 3 (Dịch)

4. Có SRT dịch nhưng chưa compose?
   → NEXT_STEP = STEP 4 (Compose Video)

5. Tất cả xong?
   → STATUS = COMPLETED ✅
```

**Ví dụ:**
```bash
# Lần đầu chạy
python main.py
# → Bước 1, 2, 3, 4 chạy lần lượt

# Lần thứ 2 (có lỗi ở bước 3)
python main.py
# → Quét & phát hiện: Step 3 chưa xong
# → Bỏ qua Step 1,2 (đã hoàn thành)
# → Chỉ chạy Step 3, 4
```

---

## 📊 Progress Tracking

Mỗi lần chạy hiển thị:

```
Progress: yan magical 2
──────────────────────────────────────────────────────────────────────
   STEP 1: ✅ DONE (Audio Extract)
   STEP 2: ✅ DONE (SRT Create)
   STEP 3: ⏳ IN PROGRESS (Translation)
   STEP 4: ⏳ PENDING (Video Compose)
──────────────────────────────────────────────────────────────────────

Total Videos:
   ⏳ Pending: 1
   ⏳ In Progress: 1
   ✅ Completed: 5
```

---

## ⚙️ Cấu Hình

### `config.py` / `Key/allkey.env`

```python
# ========== GEMINI ==========
GEMINI_MODEL = "gemini-3.1-flash-lite"
GEMINI_API_KEY = "your-api-key-here"

# ========== OLLAMA ==========
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL = "gemma:7b"
OLLAMA_BATCH_SIZE = 5

# ========== WHISPER ==========
WHISPER_MODEL = "base"  # tiny, base, small, medium, large

# ========== TTS ==========
TTS_ENGINE = "gtts"  # gtts, google_cloud, pyttsx3
TTS_LANGUAGE = "vi"
```

---

## 🎯 Quy Trình Chi Tiết

### **Lần Đầu Tiên**

```bash
1. Thả video vào: input/VideoInput/yan_magical_2.mp4

2. python main.py

3. STEP 1: Tách Audio
   yan_magical_2.mp4 → input/AudioInput/yan_magical_2.wav ✅

4. STEP 2: Whisper Transcribe
   yan_magical_2.wav → input/SrtInput/yan_magical_2.srt ✅
   (Tự động phát hiện SRT input, dùng Segment Mode)

5. STEP 3: Dịch SRT
   input/SrtInput/yan_magical_2.srt 
   → (Gemini dịch) 
   → output/SrtOutput/yan_magical_2_translated.srt ✅

6. STEP 4: Compose Video
   yan_magical_2.mp4 + yan_magical_2_translated.srt
   → (TTS + Subtitle) 
   → output_videos/yan_magical_2_final.mp4 ✅
```

### **Nếu Có Lỗi Ở Giữa**

```bash
# Lỗi xảy ra ở STEP 3 (Dịch thất bại)
$ python main.py

# Quét & phát hiện
✅ STEP 1: Audio Extract (DONE)
✅ STEP 2: SRT Create (DONE)
❌ STEP 3: Translation (FAILED/PENDING)
⏳ STEP 4: Video Compose (WAITING)

# Fix lỗi & chạy lại
$ python main.py
# → TỰ ĐỘNG bỏ qua Step 1,2 → Chỉ chạy Step 3,4
```

---

## 🔧 Các Module Chính

| Module | Tác Vụ | Input | Output |
|--------|--------|-------|--------|
| **extract_audio_optimized.py** | Tách audio FFmpeg | MP4 | WAV |
| **speech_to_text.py** | Whisper transcribe | WAV | SRT |
| **speech_to_text.py** | Translate (Gemini/Ollama) | SRT | SRT (VN) |
| **pipeline_full.py** | Compose video | MP4 + SRT | MP4 (Final) |
| **audio_merger.py** | Gộp TTS audio | MP3 files | WAV (merged) |
| **video_composer.py** | Thêm subtitle & audio | MP4 + SRT + WAV | MP4 |

---

## 🎵 Audio Merger (Gap Optimization)

**File:** `modules/audio_merger.py`

```
TTS Audio Files (nhiều file MP3)
    ↓
[Gap Detection]
    Segment 1: 0-3s
    GAP: 3-8s (5 giây! ❌)
    Segment 2: 8-12s
    ↓
[Gap Compression]
    Thay 5s gap → 120ms gap ✅
    ↓
[Merge]
Merged Audio (ngắn gọn, không expand)
    ↓
output/AudioOutput/merged.wav
```

**Config:**
```python
MIN_SILENCE_GAP = 0.1s   # 100ms
MAX_SILENCE_GAP = 0.15s  # 150ms
DEFAULT_GAP = 0.12s      # 120ms
```

---

## 📈 Performance

| Bước | Thời Gian | Tốc Độ |
|------|-----------|--------|
| STEP 1 (Audio Extract) | 5-10s | ⚡ Nhanh |
| STEP 2 (Whisper) | 5-30 phút | 🐢 Tùy độ dài |
| STEP 3 (Translation) | 30s - 5 phút | ⚡ Nhanh (Gemini) / 🐢 Chậm (Ollama) |
| STEP 4 (Compose) | 5-30 phút | 🐢 Tùy độ dài |
| **TOTAL** | **20-60 phút** | (Tùy video) |

---

## ✅ Checklist Trước Chạy

```
[ ] Video đã thả vào input/VideoInput/
[ ] GEMINI_API_KEY được cấu hình (Key/allkey.env)
[ ] Ollama đang chạy (nếu dùng fallback)
[ ] Python 3.11+ được cài đặt
[ ] pip install -r requirements.txt
[ ] Whisper model (base) được download
[ ] FFmpeg được cài đặt
```

---

## 🚀 Chạy Pipeline

```bash
# Activate venv
.venv\Scripts\Activate

# Chạy pipeline
python main.py

# Kết quả
output_videos/yan_magical_2_final.mp4 ✅
```

---

## 🎯 Ví Dụ Một Dòng Bản Dịch

```
Gốc:    我叫悠雨,我穿越到了一个有着魔法少女的事件
Dịch:   Tôi tên là Du Vũ, tôi đã chuyển sang một sự kiện có cô gái phép thuật
Timing: 00:00:00,000 --> 00:00:03,480
```

---

**Đây là toàn bộ quy trình! 🎬✨**
