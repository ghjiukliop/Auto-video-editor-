"""
🎬 SRT Translator Optimized - Dịch SRT Trung→Việt với Checkpoint & TTS Queue Management
Tính năng:
- Checkpoint/Resume: Tiếp tục từ dòng cuối cùng đã xử lý nếu bị dừng
- Dịch JSON-based: AI trả về JSON để tránh lệch dòng
- TTS Queue: Giới hạn task đồng thời (Semaphore) 
- Logging chuyên nghiệp: Ghi nhật ký vào process.log
- Text Cleaning: Xóa ký tự rác, dấu AI thừa
"""

import asyncio
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pysubs2
import google.generativeai as genai
import edge_tts

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    "api_key": os.getenv("GOOGLE_API_KEY", "YOUR_API_KEY_HERE"),
    "model": "gemini-1.5-flash",  # Nhanh hơn gemini-3-flash cho batch processing
    "voice": "vi-VN-HoaiMyNeural",
    "input_srt": "input.srt",
    "output_srt": "translated_final.srt",
    "audio_folder": "output_audio",
    "batch_size": 35,
    "tts_concurrent": 6,  # Giới hạn task TTS chạy đồng thời
    "checkpoint_file": "progress.json",
    "log_file": "process.log",
}

# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging():
    """Cấu hình logging chuyên nghiệp: vừa file vừa console"""
    log_format = "%(asctime)s | %(levelname)-8s | %(funcName)-20s | %(message)s"
    
    logger = logging.getLogger("SRTTranslator")
    logger.setLevel(logging.DEBUG)
    
    # File handler
    fh = logging.FileHandler(CONFIG["log_file"], encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(log_format))
    
    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(log_format))
    
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger

logger = setup_logging()

# ============================================================================
# TEXT CLEANING
# ============================================================================

def clean_for_tts(text: str) -> str:
    """
    Làm sạch văn bản trước khi đẩy sang TTS.
    Xóa:
    - Dấu sao/asterisk (**, *, ***)
    - Dấu ngoặc vuông & nội dung bên trong
    - Dấu ngoặc nhọn & nội dung bên trong
    - Dấu gạch dưới thừa
    - Khoảng trắng thừa
    - Ký tự điều khiển UTF-8 lạ
    """
    # Xóa markdown bold/italic
    text = re.sub(r'\*+([^*]*)\*+', r'\1', text)
    text = re.sub(r'\_+([^_]*)\_+', r'\1', text)
    
    # Xóa ngoặc vuông & nội dung
    text = re.sub(r'\[.*?\]', '', text)
    
    # Xóa ngoặc nhọn & nội dung
    text = re.sub(r'\{.*?\}', '', text)
    
    # Xóa dấu câu Trung Quốc thay bằng tiếng Việt
    replacements = {
        '，': ',',
        '。': '.',
        '！': '!',
        '？': '?',
        '；': ';',
        '：': ':',
        '「': '"',
        '」': '"',
        '『': '"',
        '』': '"',
        '（': '(',
        '）': ')',
    }
    for zh, vi in replacements.items():
        text = text.replace(zh, vi)
    
    # Xóa khoảng trắng thừa
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Xóa ký tự điều khiển lạ
    text = ''.join(ch for ch in text if ord(ch) >= 32 or ch in '\n\t')
    
    return text.strip()


def validate_json_response(response_text: str) -> Optional[Dict[str, str]]:
    """
    Trích xuất JSON từ response của Gemini.
    Nếu response không phải pure JSON, tìm JSON block trong text.
    """
    response_text = response_text.strip()
    
    # Thử parse trực tiếp
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass
    
    # Tìm JSON block trong text (giữa ```json ... ``` hoặc { ... })
    json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Tìm { ... }
    brace_match = re.search(r'\{.*\}', response_text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass
    
    logger.warning(f"Không parse được JSON từ response: {response_text[:100]}...")
    return None

# ============================================================================
# CHECKPOINT MANAGEMENT
# ============================================================================

class ProgressCheckpoint:
    """Quản lý lưu/tải tiến độ xử lý"""
    
    def __init__(self, checkpoint_file: str):
        self.checkpoint_file = Path(checkpoint_file)
        self.data = self._load()
    
    def _load(self) -> Dict:
        """Tải checkpoint từ file"""
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info(f"✅ Đã tải checkpoint từ {self.checkpoint_file}")
                return data
            except Exception as e:
                logger.error(f"Lỗi tải checkpoint: {e}. Tạo mới...")
        
        return {"last_processed_line": -1, "total_lines": 0, "timestamp": None}
    
    def save(self):
        """Lưu checkpoint vào file"""
        self.data["timestamp"] = datetime.now().isoformat()
        try:
            with open(self.checkpoint_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            logger.debug(f"💾 Đã lưu checkpoint: dòng {self.data['last_processed_line']}")
        except Exception as e:
            logger.error(f"Lỗi lưu checkpoint: {e}")
    
    def update(self, line_idx: int):
        """Cập nhật dòng cuối cùng đã xử lý"""
        self.data["last_processed_line"] = line_idx
        self.save()
    
    def get_resume_line(self) -> int:
        """Lấy dòng bắt đầu tiếp tục (dòng sau dòng cuối đã xử lý)"""
        return self.data["last_processed_line"] + 1
    
    def is_resumed(self) -> bool:
        """Kiểm tra có phải đang tiếp tục hay chạy từ đầu"""
        return self.data["last_processed_line"] >= 0

# ============================================================================
# TRANSLATION WITH JSON RESPONSE
# ============================================================================

async def translate_batch_json(batch_data: List[Tuple[int, str]], checkpoint: ProgressCheckpoint) -> Dict[int, str]:
    """
    Dịch một batch dữ liệu sử dụng Gemini 3 Flash.
    Yêu cầu trả về JSON format: {"original_idx": "translated_text", ...}
    
    Args:
        batch_data: List of (original_index, original_text) tuples
        checkpoint: Progress checkpoint object
    
    Returns:
        Dict mapping original_index -> translated_text
    """
    
    # Xây dựng prompt yêu cầu JSON response
    batch_json_input = {str(idx): text for idx, text in batch_data}
    
    prompt = f"""Nhiệm vụ: Dịch phụ đề phim Trung Quốc sang tiếng Việt.

QUYẾT ĐỊNH DỊCH:
1. TÊN RIÊNG/ĐỊA DANH: Dùng âm Hán-Việt hoặc dịch nghĩa tự nhiên
   Ví dụ: 悠雨 → Du Vũ, 长城 → Tường Thành, 北京 → Bắc Kinh
2. VĂN PHONG: Tự nhiên như phim lồng tiếng TVB/VTV, không máy móc
3. GIỮ Ý NGHĨA: Nếu là chú thích, câu thoại hát, giữ lại tính chất

ĐỊNH DẠNG ĐẦU RA (BẮTBUỘC):
- Chỉ trả về JSON object (không text khác, không markdown)
- Key: index string từ input, Value: text dịch
- VÍ DỤ: {{"0": "Xin chào, tôi tên là Du Vũ", "1": "Bạn cảm thấy sao?"}}

KHÔNG ĐƯỢC:
- Bỏ sót bất kỳ index nào
- Thêm comment, chú thích bên ngoài JSON
- Dùng chữ Hán trong đầu ra

Nội dung cần dịch (JSON):
{json.dumps(batch_json_input, ensure_ascii=False, indent=2)}
"""

    try:
        genai.configure(api_key=CONFIG["api_key"])
        model = genai.GenerativeModel(CONFIG["model"])
        
        logger.info(f"📡 Gửi batch {len(batch_data)} dòng đến Gemini...")
        response = await asyncio.to_thread(
            model.generate_content,
            prompt
        )
        
        result_json = validate_json_response(response.text)
        if not result_json:
            logger.error(f"AI trả về response không hợp lệ: {response.text[:200]}")
            return {}
        
        # Chuyển string keys thành int keys
        result = {int(k): v for k, v in result_json.items()}
        
        # Validate: kiểm tra có bỏ sót dòng nào không
        missing = set(idx for idx, _ in batch_data) - set(result.keys())
        if missing:
            logger.warning(f"⚠️ AI bỏ sót {len(missing)} dòng: {missing}")
        
        logger.info(f"✅ Dịch thành công {len(result)} dòng")
        return result
        
    except Exception as e:
        logger.error(f"❌ Lỗi API Gemini: {e}")
        return {}


# ============================================================================
# TTS WITH QUEUE MANAGEMENT (SEMAPHORE)
# ============================================================================

class TTSQueue:
    """Quản lý task TTS với Semaphore để giới hạn concurrent requests"""
    
    def __init__(self, max_concurrent: int):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.total_generated = 0
        self.total_failed = 0
    
    async def speak_line(self, line_idx: int, text: str, output_path: Path) -> bool:
        """
        TTS một dòng với retry logic.
        Sử dụng Semaphore để giới hạn concurrent requests.
        """
        async with self.semaphore:
            text = clean_for_tts(text)
            
            if not text:
                logger.debug(f"🔇 Dòng {line_idx} rỗng sau làm sạch, bỏ qua")
                return True
            
            for attempt in range(3):
                try:
                    logger.debug(f"🎤 TTS dòng {line_idx} (lần {attempt + 1}/3): {text[:50]}...")
                    
                    communicate = edge_tts.Communicate(
                        text=text,
                        voice=CONFIG["voice"],
                        rate="-5%",
                        pitch="-2Hz"
                    )
                    await communicate.save(str(output_path))
                    
                    self.total_generated += 1
                    logger.debug(f"✅ TTS dòng {line_idx} thành công")
                    return True
                    
                except Exception as e:
                    wait_time = 2 ** (attempt + 1)  # Exponential backoff: 2s, 4s, 8s
                    if attempt < 2:
                        logger.warning(f"⚠️ TTS dòng {line_idx} lần {attempt + 1} thất bại: {e}. Chờ {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"❌ TTS dòng {line_idx} thất bại vĩnh viễn: {e}")
                        self.total_failed += 1
                        return False
        
        return False


# ============================================================================
# MAIN WORKFLOW
# ============================================================================

async def main():
    """Workflow chính: Dịch + TTS với checkpoint"""
    
    logger.info("=" * 80)
    logger.info("🚀 BẮT ĐẦU: SRT Translator Optimized")
    logger.info("=" * 80)
    
    # Kiểm tra config
    if CONFIG["api_key"] == "YOUR_API_KEY_HERE":
        logger.error("❌ Chưa cấu hình API_KEY. Đặt biến env GOOGLE_API_KEY hoặc sửa config")
        return
    
    # Tạo thư mục output
    Path(CONFIG["audio_folder"]).mkdir(parents=True, exist_ok=True)
    
    # Tải SRT
    if not Path(CONFIG["input_srt"]).exists():
        logger.error(f"❌ File input {CONFIG['input_srt']} không tồn tại")
        return
    
    subs = pysubs2.load(CONFIG["input_srt"], encoding="utf-8")
    total_lines = len(subs)
    logger.info(f"📖 Đã nạp {total_lines} dòng từ {CONFIG['input_srt']}")
    
    # Load checkpoint
    checkpoint = ProgressCheckpoint(CONFIG["checkpoint_file"])
    start_line = checkpoint.get_resume_line()
    
    if checkpoint.is_resumed():
        logger.info(f"📌 Tiếp tục từ dòng {start_line} (lần trước xử lý đến {start_line - 1})")
    else:
        logger.info(f"🆕 Chạy mới từ dòng 0")
    
    # Khởi tạo TTS queue
    tts_queue = TTSQueue(max_concurrent=CONFIG["tts_concurrent"])
    
    # Xử lý batch
    batch_size = CONFIG["batch_size"]
    processed_count = 0
    skipped_count = start_line
    
    for batch_start in range(start_line, total_lines, batch_size):
        batch_end = min(batch_start + batch_size, total_lines)
        batch_data = [(i, subs[i].text) for i in range(batch_start, batch_end)]
        
        logger.info(f"\n📦 BATCH: dòng {batch_start}-{batch_end-1}/{total_lines-1}")
        logger.info(f"   Đã xử lý: {processed_count}, Bỏ qua: {skipped_count}")
        
        # Dịch batch
        translated = await translate_batch_json(batch_data, checkpoint)
        
        if not translated:
            logger.error(f"❌ Batch {batch_start}-{batch_end-1} dịch thất bại, bỏ qua")
            await asyncio.sleep(5)
            continue
        
        # TTS song song cho batch
        tts_tasks = []
        for original_idx, original_text in batch_data:
            if original_idx in translated:
                new_text = translated[original_idx]
                subs[original_idx].text = new_text
                
                audio_path = Path(CONFIG["audio_folder"]) / f"line_{original_idx:05d}.mp3"
                tts_tasks.append(tts_queue.speak_line(original_idx, new_text, audio_path))
            else:
                logger.warning(f"⚠️ Không có bản dịch cho dòng {original_idx}")
        
        # Chạy TTS song song với Semaphore
        if tts_tasks:
            logger.info(f"🎵 TTS {len(tts_tasks)} dòng (tối đa {CONFIG['tts_concurrent']} cùng lúc)...")
            await asyncio.gather(*tts_tasks)
        
        # Cập nhật checkpoint
        checkpoint.update(batch_end - 1)
        
        # Lưu SRT định kỳ
        if (batch_start - start_line) % (batch_size * 3) == 0:
            subs.save(CONFIG["output_srt"])
            logger.info(f"💾 Lưu SRT: {CONFIG['output_srt']}")
        
        processed_count += len(batch_data)
        
        # Nghỉ giữa batch để avoid rate limit
        if batch_end < total_lines:
            logger.info(f"⏸️  Chờ 3s trước batch tiếp theo...")
            await asyncio.sleep(3)
    
    # Lưu file cuối cùng
    subs.save(CONFIG["output_srt"])
    logger.info(f"✅ Lưu SRT cuối cùng: {CONFIG['output_srt']}")
    
    # Log tổng kết
    logger.info("\n" + "=" * 80)
    logger.info(f"🎉 HOÀN THÀNH!")
    logger.info(f"   Tổng dòng: {total_lines}")
    logger.info(f"   TTS thành công: {tts_queue.total_generated}")
    logger.info(f"   TTS thất bại: {tts_queue.total_failed}")
    logger.info(f"   Output SRT: {CONFIG['output_srt']}")
    logger.info(f"   Output Audio: {CONFIG['audio_folder']}/")
    logger.info(f"   Log: {CONFIG['log_file']}")
    logger.info("=" * 80)


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("\n⚠️ Người dùng dừng chương trình. Đã lưu checkpoint.")
        logger.info("Chạy lại để tiếp tục từ dòng cuối.")
    except Exception as e:
        logger.critical(f"❌ Lỗi không mong muốn: {e}", exc_info=True)
        sys.exit(1)
