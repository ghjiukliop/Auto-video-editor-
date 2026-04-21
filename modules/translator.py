#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TRANSLATOR MODULE - GEMINI API VERSION WITH INCREMENTAL OUTPUT & RESUME
Phiên bản dùng Gemini API + ghi file SRT incremental + hỗ trợ tiếp tục dịch khi ngắt

PASS 1: gemini-2.0-flash - Phân tích Glossary
PASS 2: gemini-2.0-flash - Dịch công nghiệp (với progress tracking)
"""
import google.generativeai as genai
import re
import json
import time
import os
from pathlib import Path
from typing import List, Dict, Optional
from dotenv import load_dotenv

# ==========================================
# 1. CẤU HÌNH GEMINI API
# ==========================================
load_dotenv(os.path.join(Path(__file__).parent.parent, "Key", "allkey.env"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY không được tìm thấy trong .env!")

# Initialize Gemini client
genai.configure(api_key=GEMINI_API_KEY)

# Model Config
MODEL_GLOSSARY = "models/gemini-3.1-pro-preview"
MODEL_TRANSLATOR = "models/gemini-2.5-pro"

# Translation Config
BATCH_SIZE = 10
SLEEP_TIME = 1.0

# Temp file paths
MAPPING_JSON = "mapping_translator.json"
GLOSSARY_JSON = "glossary_translator.json"
EXTRACTED_TXT = "extracted_translator.txt"
PROGRESS_STATE_JSON = "progress_translator.json"

print(f"✅ Gemini API initialized! Using {MODEL_TRANSLATOR}")

# ==========================================
# PROGRESS STATE TRACKING
# ==========================================
def load_progress() -> Dict:
    if os.path.exists(PROGRESS_STATE_JSON):
        with open(PROGRESS_STATE_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"last_translated_idx": -1, "total_lines": 0}

def save_progress(last_idx: int, total: int):
    with open(PROGRESS_STATE_JSON, 'w', encoding='utf-8') as f:
        json.dump({"last_translated_idx": last_idx, "total_lines": total}, f)

def append_to_srt(output_srt_path: str, idx: str, timestamp: str, text: str):
    try:
        entry = f"{idx}\n{timestamp}\n{text.strip()}\n\n"
        with open(output_srt_path, 'a', encoding='utf-8') as f:
            f.write(entry)
    except Exception as e:
        print(f"❌ Lỗi ghi SRT: {e}")

# ==========================================
# GEMINI API WRAPPER
# ==========================================
def call_gemini(model: str, prompt: str) -> Optional[str]:
    max_retries = 3
    retry_count = 0
    wait_time = 2
    
    while retry_count < max_retries:
        try:
            print(f"   🔄 Gọi {model}...")
            response = genai.GenerativeModel(model).generate_content(prompt)
            result = response.text.strip() if response.text else None
            
            if not result:
                print(f"   ⚠️ {model} trả về kết quả trống")
                return None
            return result
            
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "quota" in error_msg.lower() or "rate" in error_msg.lower():
                retry_count += 1
                print(f"   ⚠️ Rate Limit! Chờ {wait_time}s rồi thử lại... ({retry_count}/{max_retries})")
                time.sleep(wait_time)
                wait_time *= 2
                continue
            print(f"   ❌ Lỗi gọi {model}: {error_msg[:150]}")
            return None
    
    print(f"   ❌ Đã thử {max_retries} lần, vẫn bị rate limit")
    return None

# ==========================================
# GIAI ĐOẠN 1: PRE-PROCESSING
# ==========================================
def preprocess_srt(file_path: str) -> List[str]:
    print("🧹 Đang bóc tách file SRT...")
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        content = f.read().replace('\r\n', '\n')

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

    with open(MAPPING_JSON, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False)
    with open(EXTRACTED_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"✅ Bóc tách xong: {len(lines)} câu thoại")
    return lines

# ==========================================
# GIAI ĐOẠN 2: PASS 1 - GLOSSARY
# ==========================================
def get_glossary(lines: List[str]) -> Dict:
    if os.path.exists(GLOSSARY_JSON):
        print("📁 Tìm thấy glossary.json cũ, dùng luôn.")
        with open(GLOSSARY_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)

    print(f"🧠 PASS 1: Phân tích Glossary...")
    sample = "\n".join(lines[:200])
    
    prompt = f"""Bạn là chuyên gia dịch thuật Dark Fantasy. Phân tích kịch bản sau để tạo Glossary chi tiết.

NHIỆM VỤ:
1. XÁC ĐỊNH NGÔI KỂ (POV)
2. LẬP GLOSSARY NHÂN VẬT (tên Hán Việt)
3. QUY ĐỊNH XƯUNG HÔ
4. STYLE GUIDE
5. KEYWORDS HẮC HÓA

ĐỊNH DẠNG (CHỈ JSON):
{{
    "pov": "mô tả ngôi kể",
    "glossary": {{"Tên gốc": "Tên Hán Việt"}},
    "honorifics": {{"Nhân vật A - Nhân vật B": "Cách xưung hô"}},
    "style_guide": "mô tả văn phong",
    "keywords": ["từ 1", "từ 2"]
}}

KỊCH BẢN:
{sample}

CHỈ TRẢ VỀ JSON, KHÔNG THÊM LỜI BÌNH."""
    
    try:
        response = call_gemini(MODEL_GLOSSARY, prompt)
        if not response:
            raise Exception("PASS 1 thất bại")
        
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            with open(GLOSSARY_JSON, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            print(f"✅ PASS 1 hoàn thành!")
            return data
        else:
            raise Exception("Không parse được JSON")
    except Exception as e:
        print(f"❌ Lỗi PASS 1: {str(e)[:150]}")
        raise

# ==========================================
# GIAI ĐOẠN 3: PASS 2 - TRANSLATION
# ==========================================
def run_translation_incremental(lines: List[str], glossary_info: Dict, mapping: Dict, output_srt_path: str) -> bool:
    print(f"⚡ PASS 2: Dịch công nghiệp...")
    
    progress = load_progress()
    last_translated_idx = progress.get("last_translated_idx", -1)
    remaining_lines = lines[last_translated_idx + 1:]
    
    if not remaining_lines:
        print("✅ Tất cả đã dịch xong!")
        return True
    
    print(f"📊 Tiếp tục từ line {last_translated_idx + 1}, còn {len(remaining_lines)} dòng")
    
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
        progress_pct = int((i / len(remaining_lines)) * 100) if remaining_lines else 0
        
        print(f"📦 Batch {batch_num}/{total_batches} ({progress_pct}%)")

        prompt = f"""Dịch từng dòng sau theo định dạng [Index] [Dịch]:

BỘ QUY TẮC:
📍 POV: {pov}
👥 Glossary: {glossary}
💬 Honorifics: {honorifics}
✍️ Style: {style_guide}
🔑 Keywords: {keywords}

QUY ĐỊNH:
1. Giữ nguyên Index ở đầu
2. Format: [Index] [Lời dịch]
3. Mỗi dòng một entry

DANH SÁCH:
{batch_text}

OUTPUT (CHỈ DỊCH):"""
        
        result = call_gemini(MODEL_TRANSLATOR, prompt)
        
        if not result:
            print(f"❌ Batch {batch_num} thất bại, bỏ qua.")
        else:
            matches = re.findall(r'^(\d+)\s+(.*)', result, re.MULTILINE)
            if matches:
                for idx, text in matches:
                    if idx in mapping:
                        timestamp = mapping[idx]
                        append_to_srt(output_srt_path, idx, timestamp, text)
                print(f"✓ Batch {batch_num} OK ({len(matches)} câu)")
                save_progress(current_line_idx + len(matches), len(lines))
            else:
                print(f"⚠️ Batch {batch_num}: Không parse được output")
        
        current_line_idx += len(batch)
        time.sleep(SLEEP_TIME)

    print(f"✅ Hoàn thành dịch! {len(lines)} câu")
    return True

# ==========================================
# WRAPPER FUNCTION
# ==========================================
def translate_srt_2pass(input_srt_path: str, output_srt_path: str, working_dir: str = ".") -> bool:
    """
    Dịch SRT bằng Gemini 2-PASS (Glossary + Translation)
    
    Args:
        input_srt_path: Path tới SRT input
        output_srt_path: Path tới SRT output
        working_dir: Thư mục làm việc
    
    Returns:
        True nếu thành công
    """
    global MAPPING_JSON, GLOSSARY_JSON, EXTRACTED_TXT, PROGRESS_STATE_JSON
    
    work_path = Path(working_dir)
    MAPPING_JSON = str(work_path / "mapping_translator.json")
    GLOSSARY_JSON = str(work_path / "glossary_translator.json")
    EXTRACTED_TXT = str(work_path / "extracted_translator.txt")
    PROGRESS_STATE_JSON = str(work_path / "progress_translator.json")
    
    try:
        print("\n🧠 PASS 1 - PASS 2 TRANSLATION (GEMINI API + RESUME)")
        print("="*60)
        
        progress = load_progress()
        last_translated_idx = progress.get("last_translated_idx", -1)
        
        print("📋 Bước 1: Bóc tách SRT...")
        lines = preprocess_srt(input_srt_path)
        if not lines:
            print("❌ Không bóc tách được dữ liệu")
            return False
        
        if not os.path.exists(MAPPING_JSON):
            print("❌ Không tìm được mapping file")
            return False
        with open(MAPPING_JSON, 'r', encoding='utf-8') as f:
            mapping = json.load(f)
        
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
        
        if last_translated_idx == -1:
            with open(output_srt_path, 'w', encoding='utf-8') as f:
                f.write("")
            print(f"📝 Tạo file output: {output_srt_path}")
        else:
            print(f"📝 Tiếp tục ghi vào: {output_srt_path}")
        
        print("\n⚡ PASS 2: Dịch công nghiệp...")
        success = run_translation_incremental(lines, glossary, mapping, output_srt_path)
        
        if not success:
            print("❌ PASS 2 thất bại")
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
