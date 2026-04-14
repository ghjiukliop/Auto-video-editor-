# Ollama Translator - Quick Reference

## 🚀 Khởi Động Nhanh (30 giây)

### 1. Cài Ollama
```bash
# Download từ https://ollama.ai/download
# Hoặc: curl https://ollama.ai/install.sh | sh

# Chạy server
ollama serve
```

### 2. Pull Model
```bash
ollama pull qwen2.5:7b
```

### 3. Test
```python
from pipeline import TranslatorWithVerification
from pathlib import Path

translator = TranslatorWithVerification()
translator.translate(Path("input.srt"), Path("output.srt"))
```

---

## 📋 3-Pass System (Tóm Tắt)

| Pass | Mục Tiêu | Input | Output | Atomic Write |
|------|----------|-------|--------|--------------|
| 1 | Dịch thô Trung→Việt | Trung | Việt | Mỗi câu |
| 2 | Xác minh tiếng Trung | Việt | Việt (sạch) | Mỗi câu |
| 3 | Tinh chỉnh xưng hô | Việt | Việt (tự nhiên) | Toàn file |

---

## 🔧 Configuration

**File: config.py**
```python
OLLAMA_MODEL = "qwen2.5:7b"  # Thay model nếu muốn
OLLAMA_HOST = "http://localhost:11434"
```

**Models populaires:**
- `qwen2.5:7b` (mặc định) - Cân bằng chất lượng & tốc độ
- `qwen2.5:14b` - Tốt nhất, nhưng chậm
- `neural-chat` - Nhanh nhất
- `mistral` - Tốt cho tiếng Anh
- `llama2` - Cổ nhất, chậm

---

## 💻 Sử Dụng

### Cơ bản
```python
from pipeline import TranslatorWithVerification
from pathlib import Path

translator = TranslatorWithVerification()
translator.translate(Path("input.srt"), Path("output.srt"))
```

### Tùy chỉnh passes
```python
# Chỉ dịch & xác minh (bỏ refactor)
translator = TranslatorWithVerification(max_passes=2)

# Full 3-pass
translator = TranslatorWithVerification(max_passes=3)
```

### Trong pipeline
```python
# pipeline.py đã tích hợp sẵn
from pipeline import TranslatorWithVerification

translator = TranslatorWithVerification()
result = translator.translate(srt_input, srt_output)
```

---

## 📊 Logging Output

```
[Dịch #001] Gốc: 你好呀
[✓ #001] Dịch: Xin chào nè

[Dịch #002] Gốc: 今天天气很好
[✓ #002] Dịch: Hôm nay thời tiết đẹp

⚠️  Phát hiện 5 subtitle còn tiếng Trung
[Dịch lại #042] Gốc: Bây giờ là时刻 (2 ký tự Trung)
[✓ #042] Dịch lại: Bây giờ là lúc rồi

✅ Pass 1 XONG: 1000 thành công, 5 lỗi
✅ Pass 2 XONG: 4 subtitle dịch lại, 1 lỗi
✅ Pass 3 XONG: File đã refactor
✅ Dịch HOÀN TẤT
```

---

## ⚙️ Troubleshooting

| Lỗi | Giải pháp |
|-----|----------|
| Connection refused | `ollama serve` |
| Model not found | `ollama pull qwen2.5:7b` |
| Timeout | Dùng model nhỏ hơn |
| Permission denied | Check folder rights |
| Memory error | Giảm max_passes |

---

## 🎯 Chiến Lược Tối Ưu

### Tốc độ
```python
# Bỏ Pass 3 (refactor)
translator = TranslatorWithVerification(max_passes=2)

# Dùng model nhỏ
config.OLLAMA_MODEL = "neural-chat"
```

### Chất lượng
```python
# Keep Pass 3
translator = TranslatorWithVerification(max_passes=3)

# Dùng model lớn
config.OLLAMA_MODEL = "qwen2.5:14b"

# Custom prompts (tùy chỉnh trong class)
```

---

## 📝 Key Differences

**Cũ (Google Translate):**
- ❌ Cloud API
- ❌ Không có refactor
- ❌ Atomic write mỗi 10 câu

**Mới (Ollama):**
- ✅ Local (miễn phí)
- ✅ 3-Pass refactor
- ✅ Atomic write mỗi câu
- ✅ Custom prompts
- ✅ Logging chi tiết

---

## 🔗 Links

- Full Guide: `OLLAMA_TRANSLATOR_GUIDE.md`
- Changes Log: `OLLAMA_TRANSLATOR_CHANGES.md`
- Source: `pipeline.py` (class TranslatorWithVerification)
- SRT Parser: `modules/srt_parser_optimized.py`

---

## ✅ Checklist

- [ ] Ollama installed
- [ ] `ollama serve` running
- [ ] Model pulled (`ollama pull qwen2.5:7b`)
- [ ] config.py configured
- [ ] pipeline.py updated
- [ ] Test with sample SRT

---

**Ready to translate!** 🎬
