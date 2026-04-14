# Ollama Translator with Verification - Hướng Dẫn Chi Tiết

## 📋 Tổng Quan

Class `TranslatorWithVerification` đã được hoàn toàn refactor để sử dụng **Ollama** thay vì Google Translate, với các cải tiến đáng kể:

✅ **Dịch từng câu một** (Granular Translation) - Không ghép batch  
✅ **3-Pass Verification System** - Dịch thô → Xác minh → Tinh chỉnh  
✅ **Atomic Write** - Ghi file tức thì từng câu  
✅ **Custom System Prompt** - Chuyên dụng cho lồng tiếng phim  
✅ **Logging chi tiết** - Theo dõi tiến độ rõ ràng  
✅ **Exception Handling** - Xử lý lỗi tốt, không làm dừng pipeline  

---

## 🚀 Cài Đặt & Chuẩn Bị

### 1. Cài Đặt Ollama

```bash
# Windows - download từ: https://ollama.ai/download
# Mac/Linux:
curl https://ollama.ai/install.sh | sh

# Khởi chạy Ollama server
ollama serve
```

### 2. Pull Model

```bash
# Pull model mặc định (qwen2.5:7b)
ollama pull qwen2.5:7b

# Hoặc pull model khác nếu muốn
ollama pull llama2
ollama pull mistral
ollama pull neural-chat
```

### 3. Cài Python Packages

```bash
# Các package cần thiết
pip install ollama>=0.1.0
pip install srt>=3.5.0
pip install python-dotenv

# Nếu chưa cài, cài toàn bộ requirements
pip install -r requirements.txt
```

### 4. Cấu Hình Config

File: `config.py`

```python
# Ollama Model & Host
OLLAMA_MODEL = "qwen2.5:7b"      # Model để dùng
OLLAMA_HOST = "http://localhost:11434"  # Default Ollama host
```

---

## 🔧 Cấu Trúc Class

```python
class TranslatorWithVerification:
    """3-Pass Ollama Translator with granular translation & verification"""
    
    def __init__(self, max_passes: int = 3)
    def translate(self, srt_path: Path, output_path: Path) -> Path
    
    # Internal methods:
    - _pass_1_rough_translation()    # Pass 1: Dịch thô
    - _pass_2_verification()          # Pass 2: Xác minh tiếng Trung
    - _pass_3_refactor()              # Pass 3: Tinh chỉnh xưng hô
    - _translate_single_sentence()    # Dịch một câu
    - _call_ollama()                  # Gọi Ollama API
    - _subtitles_to_srt_text()        # Convert subtitle → SRT text
    - _parse_srt_from_text()          # Parse SRT từ text
```

---

## 📊 3-Pass System Chi Tiết

### PASS 1: Dịch Thô (Rough Translation)

**Mục tiêu:** Dịch toàn bộ tiếng Trung sang tiếng Việt

- Load toàn bộ file SRT
- Duyệt từng subtitle
- Dùng ChineseDetector kiểm tra: có tiếng Trung không?
- Nếu có, gọi Ollama dịch **từng câu một**
- **Atomic write**: Ghi file ngay sau mỗi câu dịch
- Log chi tiết: `[Dịch #001] → [✓ #001]`

**Prompt được dùng:**
```
"Bạn là một chuyên gia lồng tiếng phim. 
Hãy dịch câu sau từ tiếng Trung sang tiếng Việt sao cho 
ngắn gọn, khớp khẩu hình và xưng hô tự nhiên. 
Chỉ trả về bản dịch, không thêm ghi chú hay giải thích."
```

**Log mẫu:**
```
[Dịch #001] Gốc: 你好，我是李明
[✓ #001] Dịch: Xin chào, tôi là Lý Minh

[Dịch #002] Gốc: 今天天气很好
[✓ #002] Dịch: Hôm nay thời tiết rất đẹp

✅ Pass 1 XONG: 1000 thành công, 5 lỗi (tổng 1005)
```

---

### PASS 2: Xác Minh & Dịch Lại (Verification)

**Mục tiêu:** Tìm tiếng Trung còn sót, dịch lại

- Load file từ Pass 1
- Quét toàn bộ file dùng **ChineseDetector**
- Tìm subtitle nào còn ký tự Trung
- Với mỗi subtitle còn Trung:
  - Gọi Ollama dịch lại
  - **Atomic write**: Ghi file ngay
  - Log: `[Dịch lại #042] (3 ký tự Trung)`

**Pass 2 có thể chạy nhiều vòng?**
- Không, Pass 2 chỉ chạy 1 vòng duy nhất
- Nếu sau dịch lại còn Trung, sẽ giữ nguyên và log warning

**Log mẫu:**
```
⚠️  Phát hiện 25 subtitle còn tiếng Trung
   Dịch lại các subtitle: [42, 138, 201, 245, ...]

[Dịch lại #042] Gốc: Bây giờ là时刻 (2 ký tự Trung)
[✓ #042] Dịch lại: Bây giờ là lúc rồi

✅ Pass 2 XONG: 23 subtitle dịch lại, 2 lỗi
```

---

### PASS 3: Tinh Chỉnh Xưng Hô & Ngữ Điệu (Refactor)

**Mục tiêu:** Tinh chỉnh toàn bộ file để tự nhiên & phù hợp phim

- Load file từ Pass 2
- **Gửi toàn bộ nội dung SRT** tới Ollama một lần
- Ollama sẽ:
  - Tinh chỉnh xưng hô (anh/em, tôi/ông...)
  - Tự nhiên hóa ngữ điệu
  - Giữ nguyên định dạng SRT
- Parse lại SRT từ kết quả Ollama
- Ghi file (nếu parse thành công)

**Prompt được dùng:**
```
"Bạn là một chuyên gia lồng tiếng phim tiếng Việt. 
Hãy tinh chỉnh lại toàn bộ file phụ đề sau sao cho: 
1. Xưng hô tự nhiên (anh/em, tôi/ông...) phù hợp với bối cảnh phim. 
2. Ngữ điệu sôi động và chân thực. 
3. Giữ nguyên định dạng SRT (chỉ chỉnh sửa nội dung text). 
Trả về file SRT đầy đủ."
```

**Đặc điểm:**
- Nếu Ollama refactor lỗi → log warning, giữ nguyên file cũ
- Nếu parse lỗi → log warning, giữ nguyên file cũ
- Pass 3 không bắt buộc, có lỗi không làm crash pipeline

**Log mẫu:**
```
✅ Load 1005 subtitle cho Pass 3
📤 Gửi SRT (125,450 ký tự) tới Ollama để refactor...
📥 Nhận kết quả từ Ollama
✅ Parse lại SRT: 1005 subtitle
✅ Pass 3 XONG: File đã refactor
```

---

## 🔍 Logging Chi Tiết

### Log Levels

```
DEBUG:   Chi tiết thấp (skipped, không dịch)
INFO:    Sự kiện chính (dịch, ghi file)
WARNING: Lỗi không nghiêm trọng (dịch lỗi, parse lỗi)
ERROR:   Lỗi nghiêm trọng (Pass fail)
```

### Log Format

```
[HH:MM:SS] | [LEVEL] | [Message]
```

### Ví Dụ Log Đầy Đủ

```
2026-04-14 10:30:15 | INFO | 🌐 Dịch: subtitles.srt (Ollama)...

======================================================================
📍 PASS 1/3: Dịch thô (từ Trung sang Việt)
======================================================================
✅ Load 1005 subtitle từ subtitles.srt
   [Dịch #001] Gốc: 你好呀
   [✓ #001] Dịch: Xin chào nè

   [Dịch #002] Gốc: 今天天气很好
   [✓ #002] Dịch: Hôm nay thời tiết đẹp lắm

   ...

✅ Pass 1 XONG: 1000 thành công, 5 lỗi (tổng 1005)

======================================================================
📍 PASS 2/3: Xác minh & dịch lại (ChineseDetector)
======================================================================
✅ Load 1005 subtitle cho Pass 2
⚠️  Phát hiện 8 subtitle còn tiếng Trung
   Dịch lại các subtitle: [42, 138, 201, ...]

   [Dịch lại #042] Gốc: Bây giờ là时刻 (2 ký tự Trung)
   [✓ #042] Dịch lại: Bây giờ là lúc rồi

   ...

✅ Pass 2 XONG: 7 subtitle dịch lại, 1 lỗi

======================================================================
📍 PASS 3/3: Tinh chỉnh xưng hô & ngữ điệu
======================================================================
✅ Load 1005 subtitle cho Pass 3
📤 Gửi SRT (125,450 ký tự) tới Ollama để refactor...
📥 Nhận kết quả từ Ollama
✅ Parse lại SRT: 1005 subtitle
✅ Pass 3 XONG: File đã refactor

✅ Dịch HOÀN TẤT: subtitles.srt
```

---

## ⚙️ Exception Handling

### Chiến lược Xử Lý Lỗi

1. **Pass 1 (Dịch thô):**
   - Nếu 1 câu dịch lỗi → log error, giữ nguyên nội dung gốc, **tiếp tục dịch câu tiếp theo**
   - Nếu lỗi critical (file not found) → raise exception, dừng

2. **Pass 2 (Xác minh):**
   - Nếu 1 câu dịch lỗi → log error, giữ nguyên nội dung cũ, **tiếp tục**
   - Nếu lỗi critical → hót warning, nhưng không raise (Pass 2 là secondary)

3. **Pass 3 (Refactor):**
   - Nếu Ollama refactor lỗi → log warning, giữ nguyên file cũ
   - Nếu parse lỗi → log warning, giữ nguyên file cũ
   - **Không bao giờ raise** (Pass 3 là optional)

### Ví Dụ Exception Handling

```python
try:
    translated_text = self._translate_single_sentence(subtitle.content)
    subtitle.content = translated_text
    translated_count += 1
    logger.info(f"   [✓ #{idx:03d}] Dịch: {translated_text[:60]}...")
    save_srt(subtitles, output_path)

except Exception as e:
    failed_count += 1
    logger.error(f"   [✗ #{idx:03d}] ❌ Lỗi dịch: {str(e)[:80]}")
    # Giữ nguyên nội dung gốc
    save_srt(subtitles, output_path)
    # Tiếp tục dịch câu tiếp theo
```

---

## 💡 Custom System Prompts

Bạn có thể tùy chỉnh system prompts bằng cách sửa các hằng số trong class:

```python
# Prompt cho dịch từng câu
SYSTEM_PROMPT = (
    "Bạn là một chuyên gia lồng tiếng phim. "
    "Hãy dịch câu sau từ tiếng Trung sang tiếng Việt sao cho "
    "ngắn gọn, khớp khẩu hình và xưng hô tự nhiên. "
    "Chỉ trả về bản dịch, không thêm ghi chú hay giải thích."
)

# Prompt cho refactor
REFACTOR_PROMPT = (
    "Bạn là một chuyên gia lồng tiếng phim tiếng Việt. "
    "Hãy tinh chỉnh lại toàn bộ file phụ đề sau sao cho: "
    "1. Xưng hô tự nhiên (anh/em, tôi/ông...) phù hợp với bối cảnh phim. "
    "2. Ngữ điệu sôi động và chân thực. "
    "3. Giữ nguyên định dạng SRT (chỉ chỉnh sửa nội dung text). "
    "Trả về file SRT đầy đủ."
)
```

---

## 🎯 Sử Dụng

### Trong Pipeline

```python
from pipeline import TranslatorWithVerification
from pathlib import Path

translator = TranslatorWithVerification(max_passes=3)
result = translator.translate(
    srt_path=Path("input.srt"),
    output_path=Path("output.srt")
)
```

### Standalone

```bash
python pipeline.py
# Hoặc thêm vào script:
from pipeline import TranslatorWithVerification
translator = TranslatorWithVerification()
translator.translate(Path("input.srt"), Path("output.srt"))
```

---

## 📈 Tối Ưu Hóa Performance

### Để tăng tốc độ:

```python
# 1. Giảm max_passes
translator = TranslatorWithVerification(max_passes=2)  # Bỏ Pass 3

# 2. Dùng model nhỏ hơn
config.OLLAMA_MODEL = "neural-chat"  # Nhanh hơn qwen2.5

3. Tăng temperature (kém chính xác nhưng nhanh hơn)
"temperature": 0.5  # Từ 0.3

# 4. Giảm max_tokens nếu câu ngắn
```

### Để tăng chất lượng:

```python
# 1. Dùng model lớn hơn
config.OLLAMA_MODEL = "qwen2.5:14b"  # Chậm hơn nhưng tốt hơn

# 2. Giảm temperature
"temperature": 0.1  # Từ 0.3 - chính xác hơn nhưng dull

# 3. Keep Pass 3 (refactor)
translator = TranslatorWithVerification(max_passes=3)
```

---

## 🐛 Troubleshooting

### Lỗi: "Connection refused" khi gọi Ollama

```
❌ Ollama server not running
```

**Giải pháp:**
```bash
# Check xem Ollama service có chạy không
ollama serve

# Hoặc kiểm tra port
netstat -an | grep 11434
```

### Lỗi: "Model not found"

```
❌ qwen2.5:7b not found
```

**Giải pháp:**
```bash
ollama pull qwen2.5:7b
```

### Lỗi: "Timeout"

```
⏱️  Ollama timeout (30s)
```

**Giải pháp:**
- Tăng timeout trong `_call_ollama()`
- Hoặc dùng model nhỏ hơn, nhanh hơn

### File output không ghi được

```
❌ Permission denied: output.srt
```

**Giải pháp:**
- Check quyền folder
- Chắc chắn output path tồn tại
- Run as admin (Windows)

---

## 📝 Ví Dụ Chi Tiết

### Input SRT (subtitles.srt)
```
1
00:00:05,000 --> 00:00:08,000
你好，我是李明

2
00:00:08,500 --> 00:00:11,000
今天天气很好

3
00:00:11,500 --> 00:00:15,000
你想去哪里玩呢?
```

### Output SRT (sau Pass 1)
```
1
00:00:05,000 --> 00:00:08,000
Xin chào, tôi là Lý Minh

2
00:00:08,500 --> 00:00:11,000
Hôm nay thời tiết rất đẹp

3
00:00:11,500 --> 00:00:15,000
Cậu muốn đi chơi đâu vậy?
```

### Output SRT (sau Pass 3)
```
1
00:00:05,000 --> 00:00:08,000
Xin chào, em là Lý Minh

2
00:00:08,500 --> 00:00:11,000
Hôm nay thời tiết đẹp lắm

3
00:00:11,500 --> 00:00:15,000
Em muốn đi chơi đâu không?
```

---

## ✅ Checklist Cài Đặt

- [ ] Ollama installed
- [ ] Ollama server running (`ollama serve`)
- [ ] Model pulled (`ollama pull qwen2.5:7b`)
- [ ] Python packages installed (`pip install ollama`)
- [ ] config.py configured (OLLAMA_MODEL, OLLAMA_HOST)
- [ ] srt_parser_optimized.py available
- [ ] ChineseDetector in pipeline.py
- [ ] TranslatorWithVerification imported

---

## 📞 Support

Nếu gặp vấn đề:

1. Check log chi tiết (ERROR, WARNING messages)
2. Verify ollama running: `curl http://localhost:11434/api/tags`
3. Check model available: `ollama list`
4. Try simpler model: `ollama pull neural-chat`

---

**Tác giả:** GitHub Copilot  
**Ngày:** April 2026  
**Phiên bản:** TranslatorWithVerification v2.0 (Ollama-based)
