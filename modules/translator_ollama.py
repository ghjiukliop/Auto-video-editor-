#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TRANSLATOR MODULE - GROQ API VERSION WITH INCREMENTAL OUTPUT & RESUME
Phiên bản dùng Groq API + ghi file SRT incremental + hỗ trợ tiếp tục dịch khi ngắt

PASS 1: gpt-oss-120b - Phân tích Glossary
PASS 2: llama-3.3-70b-versatile - Dịch công nghiệp (với progress tracking)
"""
from groq import Groq
import re
import json
import time
import os
from pathlib import Path
from typing import List, Dict, Optional
from dotenv import load_dotenv

# ==========================================
# 1. CẤU HÌNH GROQ API
# ==========================================
load_dotenv(os.path.join(Path(__file__).parent.parent, "Key", "allkey.env"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("❌ GROQ_API_KEY không được tìm thấy trong .env!")

# Initialize Groq client
groq_client = Groq(api_key=GROQ_API_KEY)

# Model Config (Dùng Groq)
MODEL_GLOSSARY = "gpt-oss-120b"                 # PASS 1: GPT-OSS 120B (phân tích Glossary)
MODEL_TRANSLATOR = "llama-3.3-70b-versatile"    # PASS 2: Llama 3.3 70B (dịch)

# Translation Config
BATCH_SIZE = 15        # Batch size nhỏ hơn (tránh vượt quá Groq limit)
SLEEP_TIME = 2.0       # 2 giây giữa mỗi batch (tránh rate limit)

# Temp file paths
MAPPING_JSON = "mapping_translator.json"
GLOSSARY_JSON = "glossary_translator.json"
EXTRACTED_TXT = "extracted_translator.txt"
PROGRESS_STATE_JSON = "progress_translator.json"

print(f"✅ Groq API initialized (Unlimited quota - No rate limits!)")
print(f"   📊 PASS 1 (Glossary): {MODEL_GLOSSARY}")
print(f"   📝 PASS 2 (Translation): {MODEL_TRANSLATOR}")

# ==========================================
# PROGRESS STATE TRACKING
# ==========================================
def load_progress() -> Dict:
    """Load translation progress state"""
    if os.path.exists(PROGRESS_STATE_JSON):
        with open(PROGRESS_STATE_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"last_translated_idx": -1, "total_lines": 0}

def save_progress(last_idx: int, total: int):
    """Save translation progress"""
    with open(PROGRESS_STATE_JSON, 'w', encoding='utf-8') as f:
        json.dump({"last_translated_idx": last_idx, "total_lines": total}, f)

def append_to_srt(output_srt_path: str, idx: str, timestamp: str, text: str):
    """Append single translated line to SRT file"""
    try:
        entry = f"{idx}\n{timestamp}\n{text.strip()}\n\n"
        with open(output_srt_path, 'a', encoding='utf-8') as f:
            f.write(entry)
    except Exception as e:
        print(f"❌ Lỗi ghi SRT: {e}")

# ==========================================
# GROQ API WRAPPER
# ==========================================
def call_groq(model: str, prompt: str, timeout: int = 300) -> Optional[str]:
    """
    Gọi Groq API với exponential backoff cho rate limit
    
    Args:
        model: Tên model (llama-3.3-70b-versatile, gpt-oss-120b, etc)
        prompt: Prompt text
        timeout: Timeout (giây)
    
    Returns:
        Response text hoặc None nếu lỗi
    """
    max_retries = 3
    retry_count = 0
    wait_time = 2  # Start with 2 seconds
    
    while retry_count < max_retries:
        try:
            print(f"   🔄 Gọi {model}...")
            message = groq_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2048,  # Giảm từ 4096 để request nhỏ hơn
                top_p=1,
            )
            
            result = message.choices[0].message.content.strip() if message.choices[0].message.content else None
            
            if not result:
                print(f"   ⚠️ {model} trả về kết quả trống")
                return None
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            
            # Lỗi 429: Rate Limit
            if "429" in error_msg or "rate" in error_msg.lower():
                retry_count += 1
                print(f"   ⚠️ Rate Limit! Chờ {wait_time}s rồi thử lại... ({retry_count}/{max_retries})")
                time.sleep(wait_time)
                wait_time *= 2  # Exponential backoff
                continue
            
            # Lỗi khác
            print(f"   ❌ Lỗi gọi {model}: {error_msg[:150]}")
            return None
    
    print(f"   ❌ Đã thử {max_retries} lần, vẫn bị rate limit")
    return None

# ==========================================
# GIAI ĐOẠN 1: PRE-PROCESSING (BÓC TÁCH SRT)
# ==========================================
def preprocess_srt(file_path: str) -> List[str]:
    """
    Bóc tách file SRT: 
    - Lưu [Index] [Text] vào extracted.txt
    - Lưu Timestamp vào mapping.json
    """
    print("🧹 GIAI ĐOẠN 1: Đang bóc tách file SRT...")
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        content = f.read().replace('\r\n', '\n')

    # Regex: Bắt (Index, Timestamp, Text)
    pattern = re.compile(r'(\d+)\n(\d{2}:\d{2}:\d{2}.*?)\n([\s\S]*?)(?=\n\n|\n\d+\n|$)')
    matches = pattern.findall(content)

    if not matches:
        print("❌ Regex không tìm thấy nội dung. Kiểm tra định dạng SRT!")
        return []

    lines = []
    mapping = {}
    for idx, timestamp, text in matches:
        clean_text = text.replace('\n', ' ').strip()
        if clean_text:
            lines.append(f"{idx} {clean_text}")
            mapping[idx] = timestamp

    # Lưu mapping.json (Index -> Timestamp)
    with open(MAPPING_JSON, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False)

    # Lưu extracted.txt (Index + Text)
    with open(EXTRACTED_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"✅ Bóc tách xong: {len(lines)} câu thoại")
    print(f"   - Lưu mapping tại: {MAPPING_JSON}")
    print(f"   - Lưu text tại: {EXTRACTED_TXT}")
    return lines

# ==========================================
# GIAI ĐOẠN 2: PASS 1 - BRAIN ANALYSIS (GLOSSARY)
# ==========================================
def get_glossary(lines: List[str]) -> Dict:
    """
    PASS 1: Dùng Groq llama-3.3-70b-versatile phân tích 200 dòng đầu.
    
    Nhiệm vụ:
    1. Xác định Ngôi kể (POV)
    2. Lập Glossary Nhân vật với tên Hán Việt
    3. Quy định Xưung hô dựa trên mối quan hệ
    4. Style Guide với từ khóa Hắc hóa
    5. Keywords hắc hóa ("Tử cục", "đoạn trường", etc)
    
    Trả về JSON với cấu trúc:
    {
        "pov": "mô tả ngôi kể",
        "glossary": {"Tên gốc": "Tên Hán Việt"},
        "honorifics": {"Nhân vật A - Nhân vật B": "Cách xưung hô"},
        "style_guide": "mô tả văn phong",
        "keywords": ["từ 1", "từ 2", ...]
    }
    """
    if os.path.exists(GLOSSARY_JSON):
        print("📁 Tìm thấy glossary.json cũ, dùng luôn.")
        with open(GLOSSARY_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)

    print(f"🧠 PASS 1: Phân tích Glossary bằng {MODEL_GLOSSARY}...")
    
    # Sample 200 dòng đầu (không 800)
    sample = "\n".join(lines[:200])
    
    prompt = f"""Bạn là chuyên gia dịch thuật Dark Fantasy và biên kịch. Phân tích kịch bản sau để tạo Glossary chi tiết phục vụ dịch thuật.

NHIỆM VỤ:
1. XÁC ĐỊNH NGÔI KỂ (POV): Ai là người dẫn chuyện? Ngôn ngữ kể chuyện là gì (Lạnh lùng, thù hận, tuyệt vọng)?

2. LẬP GLOSSARY NHÂN VẬT: Trích xuất tên gốc (Trung/Anh) và chuyển sang âm Hán Việt mang sắc thái trang trọng, cổ điển.

3. QUY ĐỊNH XƯUNG HÔ: Dựa trên mối quan hệ (Kẻ thao túng - Nạn nhân, Chủ nhân - Kẻ hèn mọn, Ta - Ngươi, Tôi - Nàng), lập bảng xưung hô cố định.

4. STYLE GUIDE: Mô tả 2-3 câu về văn phong: Trang trọng hay dân gian? Dùng Hán Việt hay Việt thuần? Cảm xúc chủ đạo?

5. KEYWORDS HẮC HÓA: Đưa ra 7-10 từ khóa Hán Việt 'đắt' để dùng xuyên suốt. 
   VÍ DỤ: "Tử cục" (kết cục tuyệt vọng), "đoạn trường" (chia ly đau đớn), "chết tâm" (tuyệt vọng), "nghiệt duyên" (định mệnh tàn nhẫn), "tử khí" (khí chết chóc).

ĐỊNH DẠNG TRẢ VỀ (CHỈ JSON, KHÔNG THÊM LỜI BÌNH):
{{
    "pov": "mô tả ngôi kể",
    "glossary": {{"Tên gốc": "Tên Hán Việt", ...}},
    "honorifics": {{"Nhân vật A - Nhân vật B": "Cách xưung hô", ...}},
    "style_guide": "mô tả văn phong",
    "keywords": ["từ 1", "từ 2", ...]
}}

KỊCH BẢN (200 dòng đầu):
{sample}

BẮTBUỘC: Trả về đúng format JSON, không thêm lời bình hay ghi chú khác."""
    
    try:
        response = call_groq(MODEL_GLOSSARY, prompt, timeout=120)
        
        if not response:
            raise Exception("PASS 1 thất bại: Groq không phản hồi")
        
        # Bóc tách JSON
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            with open(GLOSSARY_JSON, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            print(f"✅ PASS 1 hoàn thành!")
            print(f"   📍 POV: {data.get('pov', 'N/A')[:60]}...")
            print(f"   👥 Glossary: {len(data.get('glossary', {}))} nhân vật")
            print(f"   💬 Honorifics: {len(data.get('honorifics', {}))} quy tắc xưung hô")
            print(f"   🔑 Keywords: {', '.join(data.get('keywords', [])[:3])}...")
            return data
        else:
            raise Exception("Không parse được JSON từ PASS 1")
    except Exception as e:
        print(f"❌ Lỗi PASS 1: {str(e)[:150]}")
        raise

# ==========================================
# GIAI ĐOẠN 3: PASS 2 - INDUSTRIAL TRANSLATION
# ==========================================
def run_translation_incremental(lines: List[str], glossary_info: Dict, mapping: Dict, output_srt_path: str) -> bool:
    """
    PASS 2: Dịch từng batch và ghi incremental vào file SRT + lưu progress.
    
    Hỗ trợ resume: nếu dịch giữa chừng mà ngắt, lần chạy tiếp theo sẽ:
    1. Load progress state
    2. Skip lines đã dịch
    3. Tiếp tục dịch từ line tiếp theo
    
    Args:
        lines: Danh sách lines [Index Text]
        glossary_info: Glossary dictionary
        mapping: Index -> Timestamp mapping
        output_srt_path: Output SRT file path
    
    Returns:
        True nếu thành công
    """
    print(f"⚡ PASS 2: Dịch công nghiệp bằng {MODEL_TRANSLATOR} (with resume support)...")
    
    # Load progress
    progress = load_progress()
    last_translated_idx = progress.get("last_translated_idx", -1)
    
    # Filter lines cần dịch (skip những đã dịch)
    remaining_lines = lines[last_translated_idx + 1:]
    
    if not remaining_lines:
        print("✅ Tất cả đã dịch xong!")
        return True
    
    print(f"📊 Tiếp tục từ line {last_translated_idx + 1}, còn {len(remaining_lines)} dòng cần dịch")
    
    try:
        pov = glossary_info.get('pov', '')
        glossary = json.dumps(glossary_info.get('glossary', {}), ensure_ascii=False)
        honorifics = json.dumps(glossary_info.get('honorifics', {}), ensure_ascii=False)
        style_guide = glossary_info.get('style_guide', '')
        keywords = ", ".join(glossary_info.get('keywords', []))
    except (KeyError, TypeError) as e:
        print(f"❌ Lỗi Glossary: {e}")
        return False

    total_batches = (len(remaining_lines) + BATCH_SIZE - 1) // BATCH_SIZE
    current_line_idx = last_translated_idx + 1

    for i in range(0, len(remaining_lines), BATCH_SIZE):
        batch = remaining_lines[i:i+BATCH_SIZE]
        batch_text = "\n".join(batch)
        batch_num = i // BATCH_SIZE + 1
        progress_pct = int((i / len(remaining_lines)) * 100)
        
        print(f"📦 Batch {batch_num}/{total_batches} ({progress_pct}%)")

        prompt = f"""Bạn là bậc thầy dịch thuật Dark Fantasy. Dịch từng dòng sau theo định dạng [Index] [Dịch].

BỘ QUY TẮC:
📍 POV: {pov}
👥 Glossary: {glossary}
💬 Honorifics: {honorifics}
✍️ Style: {style_guide}
🔑 Keywords: {keywords}

QUY ĐỊNH:
1. Giữ nguyên Index ở đầu
2. Format: [Index] [Lời dịch]
3. Chỉ dịch, không giải thích
4. Mỗi dòng một entry
5. Giữ POV, Glossary, Honorifics

DANH SÁCH CẦN DỊCH:
{batch_text}

OUTPUT (CHỈ DỊCH):
"""
        
        result = call_groq(MODEL_TRANSLATOR, prompt, timeout=120)
        
        if not result:
            print(f"❌ Batch {batch_num} thất bại, bỏ qua.")
        else:
            # Parse result và ghi từng dòng vào SRT
            matches = re.findall(r'^(\d+)\s+(.*)', result, re.MULTILINE)
            
            if matches:
                for idx, text in matches:
                    if idx in mapping:
                        timestamp = mapping[idx]
                        append_to_srt(output_srt_path, idx, timestamp, text)
                
                print(f"✓ Batch {batch_num} OK ({len(matches)} câu) → {output_srt_path}")
                
                # Update progress
                save_progress(current_line_idx + len(matches), len(lines))
            else:
                print(f"⚠️ Batch {batch_num}: Không parse được output")
        
        current_line_idx += len(batch)
        time.sleep(SLEEP_TIME)

    print(f"✅ Hoàn thành dịch! {len(lines)} câu")
    return True

# ==========================================
# GIAI ĐOẠN 4: REASSEMBLE (RÁP LẠI SRT)
# ==========================================
def raw_text_to_srt(raw_text: str, input_srt_path: str, output_srt_path: str) -> bool:
    """
    Khớp lời thoại dịch với Timestamp ban đầu.
    """
    print("🧩 Ráp lại file SRT hoàn chỉnh...")
    
    if not raw_text.strip():
        print("❌ Dữ liệu dịch trống!")
        return False

    # Load mapping từ input SRT
    try:
        with open(input_srt_path, 'r', encoding='utf-8-sig') as f:
            content = f.read().replace('\r\n', '\n')

        # Regex: Bắt (Index, Timestamp, Text)
        pattern = re.compile(r'(\d+)\n(\d{2}:\d{2}:\d{2}.*?)\n([\s\S]*?)(?=\n\n|\n\d+\n|$)')
        matches = pattern.findall(content)
        
        if not matches:
            print("❌ Không parse được input SRT!")
            return False

        mapping = {}
        for idx, timestamp, _ in matches:
            mapping[idx] = timestamp
    except Exception as e:
        print(f"❌ Lỗi đọc {input_srt_path}: {e}")
        return False

    # Parse output: Tìm dạng "Index Text"
    final_srt = []
    matches = re.findall(r'^(\d+)\s+(.*)', raw_text, re.MULTILINE)

    count = 0
    for idx, text in matches:
        if idx in mapping:
            final_srt.append(f"{idx}")
            final_srt.append(mapping[idx])
            final_srt.append(text.strip())
            final_srt.append("")  # Dòng trắng giữa các entry
            count += 1

    if count == 0:
        print(f"❌ Không khớp được Index nào. Sample: {raw_text[:200]}")
        return False

    # Ghi file output
    try:
        Path(output_srt_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_srt_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(final_srt))
        print(f"✅ Ráp xong! {count} câu")
        return True
    except Exception as e:
        print(f"❌ Lỗi ghi {output_srt_path}: {e}")
        return False

# ==========================================
# WRAPPER FUNCTION FOR MAIN.PY INTEGRATION
# ==========================================
def translate_srt_2pass(input_srt_path: str, output_srt_path: str, working_dir: str = ".") -> bool:
    """
    Wrapper function với hỗ trợ resume: ghi incremental vào file SRT + tiếp tục từ điểm dừng
    
    Args:
        input_srt_path: Path tới SRT input
        output_srt_path: Path tới SRT output
        working_dir: Thư mục làm việc (để lưu temp files)
    
    Returns:
        True nếu thành công, False nếu thất bại
    """
    global MAPPING_JSON, GLOSSARY_JSON, EXTRACTED_TXT, PROGRESS_STATE_JSON
    
    # Setup temp file paths trong working directory
    work_path = Path(working_dir)
    MAPPING_JSON = str(work_path / "mapping_translator.json")
    GLOSSARY_JSON = str(work_path / "glossary_translator.json")
    EXTRACTED_TXT = str(work_path / "extracted_translator.txt")
    PROGRESS_STATE_JSON = str(work_path / "progress_translator.json")
    
    try:
        print("\n🧠 PASS 1 - PASS 2 TRANSLATION (2-PASS WORKFLOW - GROQ API + RESUME)")
        print("="*60)
        
        # Load progress
        progress = load_progress()
        last_translated_idx = progress.get("last_translated_idx", -1)
        
        # Giai đoạn 1: Bóc tách SRT
        print("📋 Bước 1: Bóc tách SRT...")
        lines = preprocess_srt(input_srt_path)
        if not lines:
            print("❌ Không bóc tách được dữ liệu")
            return False
        
        # Load mapping (Index -> Timestamp)
        if not os.path.exists(MAPPING_JSON):
            print("❌ Không tìm được mapping file")
            return False
        with open(MAPPING_JSON, 'r', encoding='utf-8') as f:
            mapping = json.load(f)
        
        # PASS 1: Phân tích Glossary (chỉ lần đầu)
        if last_translated_idx == -1:
            print("\n🧠 PASS 1: Phân tích Glossary...")
            glossary = get_glossary(lines)
            if not glossary:
                print("❌ PASS 1 thất bại")
                return False
        else:
            print(f"\n🧠 PASS 1: Skip (đã dịch {last_translated_idx + 1} dòng)")
            if os.path.exists(GLOSSARY_JSON):
                with open(GLOSSARY_JSON, 'r', encoding='utf-8') as f:
                    glossary = json.load(f)
            else:
                print("❌ Không tìm được glossary file")
                return False
        
        # Clear output file nếu lần đầu
        if last_translated_idx == -1:
            with open(output_srt_path, 'w', encoding='utf-8') as f:
                f.write("")
            print(f"📝 Tạo file output: {output_srt_path}")
        else:
            print(f"📝 Tiếp tục ghi vào: {output_srt_path}")
        
        # PASS 2: Dịch công nghiệp (incremental)
        print("\n⚡ PASS 2: Dịch công nghiệp...")
        success = run_translation_incremental(lines, glossary, mapping, output_srt_path)
        
        if not success:
            print("❌ PASS 2 thất bại hoặc bị ngắt")
            return False
        
        print(f"\n✅ Dịch SRT thành công!")
        print(f"   Output: {output_srt_path}")
        print("="*60 + "\n")
        return True
        
    except Exception as e:
        print(f"❌ Lỗi dịch: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup temp files (optional)
        pass
