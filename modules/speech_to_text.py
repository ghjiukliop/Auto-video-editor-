import os
import sys
import logging
import time
import json
import requests
import re
from pathlib import Path
from typing import Literal, List, Optional
from tqdm import tqdm
from utils.audio_utils import segments_to_srt
from dotenv import load_dotenv
import srt

# ÉP HỆ THỐNG DÙNG UTF-8
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "UTF-8"

logger = logging.getLogger("video_pipeline")

# Import config
import config as app_config

# Import Gemini for translation
try:
    import google.generativeai as genai
    from google.api_core.exceptions import ResourceExhausted
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("⚠️ google-generativeai not installed, translations will use Ollama only")


# Từ điển chuẩn hóa tên nhân vật & khái niệm (Hán -> Việt)
# Các tên nhân vật phổ biến trong phim Trung Quốc
GLOSSARY = {
    # Tên nhân vật phổ biến
    "悠雨": "Du Vũ",
    "林": "Lâm",
    "王": "Vương",
    "李": "Lý",
    "张": "Trương",
    "刘": "Lưu",
    "陈": "Trần",
    "杨": "Dương",
    "黄": "Hoàng",
    "周": "Chu",
    "吴": "Ngô",
    "徐": "Từ",
    "孙": "Tôn",
    "何": "Hà",
    "郭": "Quách",
    "马": "Mã",
    "高": "Cao",
    "林": "Lâm",
    "郑": "Trịnh",
    "罗": "La",
    # Các từ khái niệm phổ biến
    "仙侠": "Tiên Hiệp",
    "修仙": "tu tiên",
    "灵力": "sức mạnh linh khí",
    "剑阵": "trận t剑",
    "魔法": "phép thuật",
    "主人": "chủ nhân",
    "宗主": "tông chủ",
}


def contains_cjk(text: str) -> bool:
    """Kiểm tra xem văn bản có chứa chữ Hán/Nhật/Hàn hay không."""
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def apply_glossary(text: str) -> str:
    """Thay thế tên nhân vật dựa trên GLOSSARY."""
    for zh, vi in GLOSSARY.items():
        text = text.replace(zh, vi)
    return text


def translate_with_gemini(texts: List[str], max_retries: int = 3) -> List[str]:
    """
    Dịch text bằng Gemini 2.0 Flash API với batching.
    
    Args:
        texts: Danh sách text cần dịch
        max_retries: Số lần retry
    
    Returns:
        Danh sách text đã dịch
    """
    if not GEMINI_AVAILABLE:
        logger.warning("❌ Gemini not available, skipping Gemini translation")
        return texts
    
    if not texts:
        return texts
    
    try:
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("⚠️ GEMINI_API_KEY not found, using Ollama instead")
            return None  # Signal to use Ollama
        
        genai.configure(api_key=api_key)
        
    except Exception as e:
        logger.warning(f"⚠️ Gemini setup failed: {e}, using Ollama instead")
        return None
    
    batch_size = 50
    batches = [texts[i:i+batch_size] for i in range(0, len(texts), batch_size)]
    all_results = []
    
    logger.info(f"🌐 Dịch {len(texts)} dòng bằng Gemini ({len(batches)} batch)...")
    
    model = genai.GenerativeModel(
        model_name='gemini-2.0-flash',
        system_instruction=(
            "Bạn là chuyên gia dịch thuật phim. Dịch danh sách sau sang tiếng Việt, "
            "giữ nguyên định dạng số thứ tự#nội dung, không dịch các mã số. "
            "Chỉ trả về danh sách dịch, không giải thích gì khác."
        )
    )
    
    for batch_num, batch_texts in enumerate(batches, 1):
        batch_format = "\n".join([f"{i}#{t}" for i, t in enumerate(batch_texts)])
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🌐 Gemini batch {batch_num}/{len(batches)} (lần {attempt+1}/{max_retries})...")
                
                response = model.generate_content(f"Dịch danh sách sau:\n\n{batch_format}")
                
                # Parse response
                translated = {}
                for line in response.text.strip().split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    
                    match = re.match(r'^(\d+)#(.+)$', line)
                    if match:
                        try:
                            idx = int(match.group(1))
                            if idx < len(batch_texts):
                                translated[idx] = match.group(2).strip()
                        except ValueError:
                            continue
                
                # Check if successful
                if len(translated) >= len(batch_texts) * 0.9:
                    batch_results = [translated.get(i, batch_texts[i]) for i in range(len(batch_texts))]
                    all_results.extend(batch_results)
                    logger.info(f"✅ Batch {batch_num} dịch thành công")
                    break
                else:
                    logger.warning(f"⚠️ Batch {batch_num} format mismatch, retry...")
                    time.sleep(5)
                    
            except ResourceExhausted:
                wait = min(2 ** attempt * 60, 300)
                logger.warning(f"⏸️ Rate limit, chờ {wait}s...")
                time.sleep(wait)
                
            except Exception as e:
                logger.warning(f"❌ Batch error: {str(e)[:100]}, retry...")
                time.sleep(5)
        else:
            # Retry failed, use original
            all_results.extend(batch_texts)
        
        time.sleep(2)  # Delay between batches
    
    return all_results if len(all_results) == len(texts) else None


def translate_batch(batch_texts: List[str], batch_num: int, total_batches: int, max_retries: int = 3) -> List[str]:
    """
    Dịch một batch text bằng Ollama local LLM.
    
    Args:
        batch_texts: Danh sách text cần dịch
        batch_num: Số batch hiện tại
        total_batches: Tổng số batches
        max_retries: Số lần retry nếu lỗi
    
    Returns:
        Danh sách text đã dịch
    """
    import ollama
    
    # Tạo batch text với ID
    batch_text_with_ids = "\n".join([f"{i}|{t}" for i, t in enumerate(batch_texts)])
    
    prompt_content = (
        "Dịch từng câu sau sang TIẾNG VIỆT (không phải tiếng Anh, không phải tiếng Trung):\n\n"
        "Format input: số|câu tiếng Trung\n"
        "Format output: số|bản dịch TIẾNG VIỆT\n\n"
        "RULES:\n"
        "• Dịch TOÀN BỘ câu sang tiếng Việt - KHÔNG để chữ Hán\n"
        "• Dịch tự nhiên, dễ hiểu\n"
        "• Chỉ OUTPUT: số|bản dịch\n"
        "• KHÔNG thêm giải thích, KHÔNG thêm dòng khác\n\n"
        "VÍ DỤ:\n"
        "Input: 0|我叫悠雨\n"
        "Output: 0|Tôi tên là Du Vũ\n\n"
        "Input: 1|我穿越到了一个有着魔法少女的世界\n"
        "Output: 1|Tôi đã chuyển sang một thế giới có cô gái phép thuật\n\n"
        "BẮT ĐẦU - DỊCH CÁC CÂUTỪ ĐÂY:\n"
        f"{batch_text_with_ids}"
    )
    
    for attempt in range(max_retries):
        try:
            logger.info(
                "🌐 Dịch batch %d/%d (%d dòng - lần %d/%d)...",
                batch_num, total_batches, len(batch_texts), attempt + 1, max_retries
            )
            time.sleep(1)  # Cho model có thời gian xử lý
            
            # Gọi Ollama via API
            response = ollama.chat(
                model=app_config.OLLAMA_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "Bạn là dịch giả chuyên nghiệp phim Trung-Việt. Dịch CHÍNH XÁC từ tiếng Trung sang tiếng Việt. Không để chữ Hán.",
                    },
                    {"role": "user", "content": prompt_content},
                ],
                stream=False,
            )
            
            raw_text = response["message"]["content"]
            logger.info(f"📥 Raw response (first 500 chars): {raw_text[:500]}")
            
            results = {}
            cjk_count = 0
            parsed_count = 0
            
            for line in raw_text.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                
                # Tìm dòng có format "số|text"
                # Nếu có "→", lấy phần sau "→" (vì model có thể return input → output)
                if "→" in line:
                    # Format: số|input → output, lấy output
                    parts = line.split("→")
                    if len(parts) >= 2:
                        line = parts[-1].strip()
                        # Thêm lại số vào đầu
                        match_num = re.search(r"(\d+)\s*\|", parts[0])
                        if match_num:
                            idx_str = match_num.group(1)
                            translated = line
                        else:
                            continue
                    else:
                        continue
                else:
                    # Format thông thường: số|text
                    match = re.search(r"(\d+)\s*\|\s*(.*)", line)
                    if not match:
                        continue
                    idx_str = match.group(1).strip()
                    translated = match.group(2).strip()
                
                try:
                    idx = int(idx_str)
                    if idx < len(batch_texts):
                        translated = apply_glossary(translated)
                        parsed_count += 1
                        
                        if contains_cjk(translated):
                            cjk_count += 1
                            logger.debug(f"⚠️ Dòng {idx} có chữ Hán: {translated}")
                        
                        # Accept dù có chữ Hán
                        results[idx] = translated
                except ValueError:
                    continue
            
            # Kiểm tra xem có dịch được bao nhiêu dòng
            if parsed_count < len(batch_texts) * 0.5:
                logger.warning(
                    f"⚠️ Parse info: chỉ parse được {parsed_count}/{len(batch_texts)}"
                )
                raise ValueError(f"Chỉ dịch được {parsed_count}/{len(batch_texts)} dòng (need ≥{int(len(batch_texts)*0.5)})")
            
            # Nếu có quá nhiều chữ Hán (>70%), retry
            if cjk_count > len(batch_texts) * 0.7:
                raise ValueError(f"Quá nhiều chữ Hán ({cjk_count}/{parsed_count}), retry")
            
            # Tạo kết quả cuối, dùng bản gốc nếu không có dịch
            final_results = [results.get(i, batch_texts[i]) for i in range(len(batch_texts))]
            
            logger.info(
                "✅ Batch %d/%d hoàn tất: %d dòng parsed, %d có chữ Hán",
                batch_num, total_batches, parsed_count, cjk_count
            )
            return final_results
            
            
        except Exception as exc:
            logger.warning(
                "Lỗi batch %d (lần %d/%d): %s",
                batch_num, attempt + 1, max_retries, str(exc)[:150]
            )
            time.sleep(5)
    
    logger.error(f"❌ Batch {batch_num} thất bại sau {max_retries} lần thử. Giữ nguyên bản gốc.")
    return batch_texts


def translate_full_text(texts: List[str], max_retries: int = 3) -> List[str]:
    """
    Dịch TOÀN BỘ nội dung bằng Ollama local LLM với smart batching.
    
    Vì chạy local, chia nhỏ thành batches để tránh quá tải RAM/VRAM nhưng vẫn 
    đảm bảo hiệu suất cao. Mỗi batch có ~500 dòng (OLLAMA_BATCH_SIZE).
    
    Ưu điểm:
    - Không cần gọi external API (offline)
    - Có đủ context trong mỗi batch để dịch tự nhiên
    - Tiết kiệm tài nguyên memory
    - Tốc độ xử lý 10,000+ dòng khả thi
    """
    if not texts:
        logger.warning("Không có text để dịch")
        return texts
    
    logger.info(f"🌐 Bắt đầu dịch {len(texts)} dòng với Ollama ({app_config.OLLAMA_MODEL})...")
    
    # Kiểm tra kết nối Ollama
    try:
        import ollama
        ollama.list()  # Test connection
    except Exception as exc:
        logger.error(
            f"❌ Không thể kết nối Ollama tại {app_config.OLLAMA_HOST}. "
            f"Vui lòng đảm bảo Ollama đang chạy.\n"
            f"Error: {exc}"
        )
        logger.warning("Giữ nguyên text gốc (không dịch)")
        return texts
    
    # Chia thành batches
    batch_size = app_config.OLLAMA_BATCH_SIZE
    batches = [texts[i:i+batch_size] for i in range(0, len(texts), batch_size)]
    total_batches = len(batches)
    
    logger.info(f"📦 Chia thành {total_batches} batch(es), mỗi batch ~{batch_size} dòng")
    
    # Dịch từng batch
    all_results = []
    for batch_num, batch_texts in enumerate(batches, 1):
        batch_results = translate_batch(batch_texts, batch_num, total_batches, max_retries)
        all_results.extend(batch_results)
    
    logger.info(f"✅ Dịch xong toàn bộ {len(all_results)} dòng")
    return all_results


def _detect_language(lang: str) -> str | None:
    """
    Chuyển tham số lang của pipeline sang mã ngôn ngữ Whisper.
    Trả về None để Whisper tự nhận diện (auto-detect).
    """
    mapping = {"zh": "zh", "vi": "vi", "en": "en"}
    return mapping.get(lang)  # "auto" → None


def transcribe_to_srt(
    audio_path: Path,
    output_srt_path: Path,
    model_name: str,
    lang: Literal["vi", "en", "zh", "auto"] = "auto",
) -> Path:
    """
    Bước 1: Whisper nhận diện giọng nói → Bước 2: Ollama dịch sang tiếng Việt.
    
    FIX:
    - Bỏ tham số `task="translation"` gây KeyError — chỉ dùng task="transcribe".
    - Xóa biến `src_lang` không được khai báo gây NameError.
    - Thêm kiểm tra audio file tồn tại trước khi load Whisper.
    """
    import whisper
    import torch

    if not audio_path.exists():
        raise FileNotFoundError(f"File audio đầu vào không tồn tại: {audio_path}")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    whisper_lang = _detect_language(lang)  # None = auto-detect

    logger.info("Loading Whisper model '%s' on %s", model_name, device)
    model = whisper.load_model(model_name, device=device)

    logger.info(
        "Bắt đầu nhận diện giọng nói (lang=%s)...",
        whisper_lang if whisper_lang else "auto",
    )

    # Chỉ dùng task="transcribe" — không dùng "translation" để tránh KeyError
    transcribe_kwargs = {
        "verbose": False,
        "task": "transcribe",
    }
    if whisper_lang:
        transcribe_kwargs["language"] = whisper_lang

    result = model.transcribe(str(audio_path), **transcribe_kwargs)
    segments = result.get("segments", [])
    logger.info("✅ Whisper nhận diện được %d câu.", len(segments))

    # NOTE: Translation moved to main.py pipeline for better error handling
    # and to use the optimized Ollama + post-processing translator
    if segments:
        logger.info(
            "📝 Whisper transcription complete. Translation will be handled separately."
        )

    srt_text = segments_to_srt(segments)
    output_srt_path.parent.mkdir(parents=True, exist_ok=True)
    output_srt_path.write_text(srt_text, encoding="utf-8-sig")
    logger.info("✅ Đã lưu phụ đề: %s", output_srt_path)
    return output_srt_path