import os
import sys
import logging
import time
import json
import requests
import re
import shutil
from pathlib import Path
from typing import Literal, List, Optional, Dict
from tqdm import tqdm
from utils.audio_utils import segments_to_srt, parse_srt, SRTSegment
from dotenv import load_dotenv
import srt

# ÉP HỆ THỐNG DÙNG UTF-8
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "UTF-8"

logger = logging.getLogger("video_pipeline")

# Import pydub cho tách audio
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False

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


def translate_with_gemini(texts: List[str], max_retries: int = 3) -> Optional[List[str]]:
    """
    Dịch text bằng Gemini 2.0 Flash API với batching.
    
    Args:
        texts: Danh sách text cần dịch
        max_retries: Số lần retry
    
    Returns:
        Danh sách text đã dịch, hoặc None nếu fail
    """
    if not GEMINI_AVAILABLE:
        logger.warning("❌ Gemini library not available")
        return None
    
    if not texts:
        return texts
    
    try:
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("⚠️ GEMINI_API_KEY not found")
            return None
        
        genai.configure(api_key=api_key)
        
    except Exception as e:
        logger.warning(f"⚠️ Gemini setup failed: {e}")
        return None
    
    batch_size = 50
    batches = [texts[i:i+batch_size] for i in range(0, len(texts), batch_size)]
    all_results = []
    
    logger.info(f"🌐 Dịch {len(texts)} dòng bằng Gemini ({len(batches)} batch)...")
    
    model = genai.GenerativeModel(model_name=app_config.GEMINI_MODEL)
    
    system_instruction = (
        "Bạn là chuyên gia dịch thuật phim. Dịch danh sách sau sang tiếng Việt, "
        "giữ nguyên định dạng số thứ tự#nội dung, không dịch các mã số. "
        "Chỉ trả về danh sách dịch, không giải thích gì khác."
    )
    
    for batch_num, batch_texts in enumerate(batches, 1):
        batch_format = "\n".join([f"{i}#{t}" for i, t in enumerate(batch_texts)])
        
        batch_success = False
        for attempt in range(max_retries):
            try:
                logger.info(f"🌐 Gemini batch {batch_num}/{len(batches)} (lần {attempt+1}/{max_retries})...")
                
                response = model.generate_content(
                    f"{system_instruction}\n\nDịch danh sách sau:\n\n{batch_format}"
                )
                
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
                    logger.info(f"✅ Batch {batch_num} dịch thành công ({len(batch_results)} dòng)")
                    batch_success = True
                    break
                else:
                    logger.warning(f"⚠️ Batch {batch_num} chỉ dịch được {len(translated)}/{len(batch_texts)}, retry...")
                    time.sleep(5)
                    
            except ResourceExhausted:
                wait = min(2 ** attempt * 60, 300)
                logger.warning(f"⏸️ Rate limit, chờ {wait}s...")
                time.sleep(wait)
                
            except Exception as e:
                logger.warning(f"❌ Batch {batch_num} error: {str(e)[:100]}, retry...")
                time.sleep(5)
        
        if not batch_success:
            # Batch failed after retries, fallback to original
            logger.warning(f"⚠️ Batch {batch_num} thất bại sau {max_retries} lần, giữ nguyên")
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
    
    logger.error(
        f"❌ Batch {batch_num} thất bại sau {max_retries} lần thử. Giữ nguyên bản gốc."
    )
    return batch_texts


def translate_full_text(texts: List[str], max_retries: int = 3) -> List[str]:
    """
    Dịch text bằng Gemini.
    
    ✨ SIMPLIFIED: Chỉ dùng Gemini, không fallback.
    
    Args:
        texts: Danh sách text cần dịch
        max_retries: Số lần retry nếu lỗi
    
    Returns:
        Danh sách text đã dịch
    """
    if not texts:
        logger.warning("Không có text để dịch")
        return texts
    
    if not GEMINI_AVAILABLE:
        logger.error("❌ Gemini library không khả dụng")
        raise ImportError("google.generativeai not installed")
    
    if not app_config.GEMINI_API_KEY:
        logger.error("❌ GEMINI_API_KEY không được cấu hình")
        raise ValueError("GEMINI_API_KEY not found in config")
    
    logger.info(f"🌐 Dịch {len(texts)} dòng bằng Gemini ({app_config.GEMINI_MODEL})...")
    
    try:
        load_dotenv()
        genai.configure(api_key=app_config.GEMINI_API_KEY)
    except Exception as e:
        logger.error(f"❌ Gemini setup fail: {e}")
        raise
    
    batch_size = 50
    batches = [texts[i:i+batch_size] for i in range(0, len(texts), batch_size)]
    all_results = []
    
    logger.info(f"📦 Chia thành {len(batches)} batch (mỗi batch {batch_size} dòng)...")
    
    model = genai.GenerativeModel(model_name=app_config.GEMINI_MODEL)
    
    system_instruction = (
        "Bạn là chuyên gia dịch thuật phim. Dịch danh sách sau sang tiếng Việt, "
        "giữ nguyên định dạng số thứ tự#nội dung, không dịch các mã số. "
        "Chỉ trả về danh sách dịch, không giải thích gì khác."
    )
    
    for batch_num, batch_texts in enumerate(batches, 1):
        batch_format = "\n".join([f"{i}#{t}" for i, t in enumerate(batch_texts)])
        
        batch_success = False
        for attempt in range(max_retries):
            try:
                logger.info(f"🌐 Gemini batch {batch_num}/{len(batches)} (lần {attempt+1}/{max_retries})...")
                
                response = model.generate_content(
                    f"{system_instruction}\n\nDịch danh sách sau:\n\n{batch_format}"
                )
                
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
                
                # Check if successful (>=90% dịch được)
                if len(translated) >= len(batch_texts) * 0.9:
                    batch_results = [translated.get(i, batch_texts[i]) for i in range(len(batch_texts))]
                    all_results.extend(batch_results)
                    logger.info(f"✅ Batch {batch_num} dịch thành công ({len(batch_results)} dòng)")
                    batch_success = True
                    break
                else:
                    logger.warning(f"⚠️ Batch {batch_num} chỉ dịch được {len(translated)}/{len(batch_texts)}, retry...")
                    time.sleep(5)
                    
            except ResourceExhausted:
                wait = min(2 ** attempt * 60, 300)
                logger.warning(f"⏸️ Rate limit, chờ {wait}s...")
                time.sleep(wait)
                
            except Exception as e:
                logger.warning(f"❌ Batch {batch_num} error: {str(e)[:100]}, retry...")
                time.sleep(5)
        
        if not batch_success:
            logger.error(f"❌ Batch {batch_num} thất bại sau {max_retries} lần")
            raise RuntimeError(f"Translation batch {batch_num} failed")
    
    logger.info(f"✅ Gemini dịch xong toàn bộ {len(all_results)} dòng")
    return all_results


def extract_audio_segments(
    audio_path: Path,
    srt_path: Path,
    output_dir: Path
) -> Dict[int, Path]:
    """
    Tách audio thành các segments dựa trên timing từ SRT input.
    
    Args:
        audio_path: Đường dẫn tới file audio gốc
        srt_path: Đường dẫn tới file SRT chứa timing
        output_dir: Thư mục lưu các audio segments
    
    Returns:
        Dict[segment_index] = path_to_segment_audio
    """
    if not PYDUB_AVAILABLE:
        raise ImportError("pydub không được cài đặt. Cài đặt: pip install pydub")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Đọc SRT để lấy timing
    srt_text = srt_path.read_text(encoding='utf-8-sig')
    segments = parse_srt(srt_text)
    
    if not segments:
        logger.warning("⚠️ SRT không có segments, bỏ qua tách audio")
        return {0: audio_path}
    
    # Load audio
    try:
        file_ext = audio_path.suffix.lower()
        if file_ext == '.mp3':
            audio = AudioSegment.from_mp3(str(audio_path))
        elif file_ext == '.wav':
            audio = AudioSegment.from_wav(str(audio_path))
        elif file_ext == '.m4a':
            audio = AudioSegment.from_file(str(audio_path), format="m4a")
        else:
            audio = AudioSegment.from_file(str(audio_path))
    except Exception as e:
        logger.error(f"❌ Lỗi load audio: {e}")
        raise
    
    # Tách audio thành segments
    segment_paths = {}
    logger.info(f"🎵 Tách audio thành {len(segments)} segments...")
    
    for seg in tqdm(segments, desc="📂 Tách audio", unit="segment"):
        segment_audio = audio[seg.start_ms:seg.end_ms]
        segment_path = output_dir / f"segment_{seg.index:03d}.wav"
        
        try:
            segment_audio.export(str(segment_path), format="wav")
            segment_paths[seg.index] = segment_path
        except Exception as e:
            logger.error(f"❌ Lỗi export segment {seg.index}: {e}")
            continue
    
    logger.info(f"✅ Tách {len(segment_paths)} segments thành công")
    return segment_paths


def transcribe_segments_with_whisper(
    segment_paths: Dict[int, Path],
    model_name: str,
    lang: Literal["vi", "en", "zh", "auto"] = "auto"
) -> List[Dict]:
    """
    Chạy Whisper cho từng audio segment riêng biệt.
    
    Args:
        segment_paths: Dict[segment_index] = path_to_segment
        model_name: Tên mô hình Whisper (base, small, medium, large)
        lang: Ngôn ngữ ("zh", "en", "vi", hoặc "auto")
    
    Returns:
        Danh sách segments với transcription
    """
    import whisper
    import torch
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    whisper_lang = _detect_language(lang)
    
    logger.info(f"Loading Whisper model '{model_name}' on {device}")
    model = whisper.load_model(model_name, device=device)
    
    all_segments = []
    logger.info(f"🎤 Chạy Whisper cho {len(segment_paths)} segments...")
    
    for seg_idx in tqdm(sorted(segment_paths.keys()), desc="🎤 Whisper", unit="segment"):
        audio_path = segment_paths[seg_idx]
        
        transcribe_kwargs = {
            "verbose": False,
            "task": "transcribe",
        }
        if whisper_lang:
            transcribe_kwargs["language"] = whisper_lang
        
        try:
            result = model.transcribe(str(audio_path), **transcribe_kwargs)
            segments = result.get("segments", [])
            
            # Lưu segment index để tracking
            for seg in segments:
                seg["_original_segment_idx"] = seg_idx
            
            all_segments.extend(segments)
        except Exception as e:
            logger.error(f"❌ Lỗi Whisper segment {seg_idx}: {e}")
            continue
    
    logger.info(f"✅ Transcribed {len(all_segments)} segments")
    return all_segments


def merge_segment_transcriptions(
    all_segments: List[Dict],
    segment_timings: Dict[int, tuple]  # {segment_idx: (start_ms, end_ms)}
) -> List[Dict]:
    """
    Gộp các transcription từ từng segment lại, điều chỉnh timing.
    
    Whisper xử lý từng segment riêng lẻ, nên output timing là tương đối (0s từ đầu segment).
    Hàm này thêm offset (thời gian bắt đầu của segment trong audio gốc) để lấy absolute timing.
    
    Args:
        all_segments: Danh sách segments từ Whisper (có _original_segment_idx)
        segment_timings: Dict[segment_idx] = (start_ms, end_ms) từ SRT input
    
    Returns:
        Danh sách segments với timing điều chỉnh (absolute)
    """
    merged_segments = []
    segment_idx = 1
    
    logger.info(f"📊 Gộp {len(all_segments)} transcriptions và điều chỉnh timing...")
    
    for seg in tqdm(all_segments, desc="📊 Gộp", unit="seg"):
        original_idx = seg.get("_original_segment_idx", 0)
        
        # Lấy offset (thời gian bắt đầu của segment trong audio gốc)
        if original_idx in segment_timings:
            start_ms, end_ms = segment_timings[original_idx]
            offset_seconds = start_ms / 1000.0  # Convert milliseconds to seconds
        else:
            offset_seconds = 0
        
        # Điều chỉnh timing: thêm offset vào relative timing của Whisper
        new_seg = {
            "id": segment_idx,
            "start": seg.get("start", 0) + offset_seconds,
            "end": seg.get("end", 0) + offset_seconds,
            "text": seg.get("text", "").strip()
        }
        
        if new_seg["text"]:  # Chỉ lưu nếu có text
            merged_segments.append(new_seg)
            segment_idx += 1
    
    logger.info(f"✅ Gộp thành công {len(merged_segments)} segments")
    return merged_segments



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
    srt_input_path: Optional[Path] = None,
    use_segment_mode: bool = True,
) -> Path:
    """
    Tạo SRT từ audio bằng Whisper.
    
    ✨ NEW: Hỗ trợ 2 chế độ:
    - use_segment_mode=True (mặc định): Tách audio theo SRT input, chạy Whisper từng segment riêng
    - use_segment_mode=False: Chạy Whisper trên toàn bộ audio (cách cũ)
    
    Args:
        audio_path: Đường dẫn tới file audio
        output_srt_path: Đường dẫn output SRT
        model_name: Mô hình Whisper (base, small, medium, large)
        lang: Ngôn ngữ (zh, en, vi, auto)
        srt_input_path: (Optional) Đường dẫn tới SRT input để dùng cho segment mode
        use_segment_mode: Dùng segment-based transcription (mặc định True)
    
    Returns:
        Path tới file SRT output
    """
    import whisper
    import torch
    import shutil

    if not audio_path.exists():
        raise FileNotFoundError(f"File audio không tồn tại: {audio_path}")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    whisper_lang = _detect_language(lang)

    output_srt_path.parent.mkdir(parents=True, exist_ok=True)
    
    # SEGMENT MODE (mới)
    if use_segment_mode and srt_input_path and srt_input_path.exists():
        logger.info("🎯 Sử dụng Segment-Based Transcription Mode")
        logger.info("📊 Tách audio dựa trên SRT input và chạy Whisper từng segment...")
        
        # Tạo thư mục tạm cho segments
        temp_segment_dir = output_srt_path.parent / ".segments_temp"
        
        try:
            # Bước 1: Tách audio thành segments
            segment_paths = extract_audio_segments(audio_path, srt_input_path, temp_segment_dir)
            
            # Bước 2: Chạy Whisper cho từng segment
            all_segments = transcribe_segments_with_whisper(segment_paths, model_name, lang)
            
            # Bước 3: Lấy timing từ SRT input
            srt_text = srt_input_path.read_text(encoding='utf-8-sig')
            srt_segments = parse_srt(srt_text)
            segment_timings = {seg.index: (seg.start_ms, seg.end_ms) for seg in srt_segments}
            
            # Bước 4: Gộp kết quả với timing điều chỉnh
            merged_segments = merge_segment_transcriptions(all_segments, segment_timings)
            
            # Bước 5: Tạo SRT
            srt_text_output = segments_to_srt(merged_segments)
            output_srt_path.write_text(srt_text_output, encoding="utf-8-sig")
            
            logger.info(f"✅ Segment mode hoàn tất: {len(merged_segments)} segments")
            logger.info(f"✅ Đã lưu phụ đề: {output_srt_path}")
            
            # Cleanup thư mục tạm
            if temp_segment_dir.exists():
                try:
                    shutil.rmtree(temp_segment_dir)
                    logger.debug(f"🧹 Cleaned up temp directory: {temp_segment_dir}")
                except Exception as e:
                    logger.warning(f"⚠️ Không thể xóa thư mục tạm: {e}")
            
            return output_srt_path
            
        except Exception as e:
            logger.error(f"❌ Segment mode lỗi: {e}")
            logger.info("⚠️ Fallback sang Full-Audio Mode...")
            
            # Cleanup thư mục tạm nếu có lỗi
            if temp_segment_dir.exists():
                try:
                    shutil.rmtree(temp_segment_dir)
                except:
                    pass
            
            use_segment_mode = False  # Fallback
    
    # FULL-AUDIO MODE (cũ, dùng khi segment mode không khả dụng)
    if not use_segment_mode:
        logger.info("🎙️ Sử dụng Full-Audio Transcription Mode (xử lý toàn bộ audio)")
        
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

        if segments:
            logger.info(
                "📝 Whisper transcription complete. Translation will be handled separately."
            )

        srt_text = segments_to_srt(segments)
        output_srt_path.parent.mkdir(parents=True, exist_ok=True)
        output_srt_path.write_text(srt_text, encoding="utf-8-sig")
        logger.info("✅ Đã lưu phụ đề: %s", output_srt_path)
        
        return output_srt_path
