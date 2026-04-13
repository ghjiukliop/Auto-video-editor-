import os
import sys
import logging
import time
import json
import requests
import re
from pathlib import Path
from typing import Literal, List
from tqdm import tqdm
from utils.audio_utils import segments_to_srt
from dotenv import load_dotenv

# ÉP HỆ THỐNG DÙNG UTF-8
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "UTF-8"

logger = logging.getLogger("video_pipeline")

# Nạp Key từ file env cụ thể
env_path = Path(__file__).parent.parent / "Key" / "allkey.env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Model Gemini
MODEL_NAME = "gemini-1.5-flash"

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


def translate_full_text(texts: List[str], max_retries: int = 3) -> List[str]:
    """
    Dịch TOÀN BỘ nội dung cùng một lần bằng Gemini.
    Cách này cho LLM đủ context để dịch tự nhiên, không cứng nhắc.
    
    ƯỪI ĐIỂ:
    - LLM có context từ đầu đến cuối → dịch tự nhiên hơn
    - Tôn chỉ nhân vật được giữ nhất quán
    - Ngôn ngữ phù hợp hơn
    """
    import google.generativeai as genai
    
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY không tìm thấy. Bỏ qua bước dịch thuật.")
        return texts

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(MODEL_NAME)

    # Tạo glossary context
    glossary_str = "\n".join([f"  {k} → {v}" for k, v in GLOSSARY.items()])

    # Tạo full text (toàn bộ nội dung)
    full_text_with_ids = "\n".join([f"{i}|{t}" for i, t in enumerate(texts)])

    prompt_content = (
        "Bạn là dịch giả chuyên nghiệp dịch phim Trung Quốc sang tiếng Việt.\n"
        "Nhiệm vụ: Dịch toàn bộ đoạn hội thoại sau (gồm tất cả dòng) sang tiếng Việt tự nhiên.\n\n"
        "NGUYÊN TẮC DỊCH (BẮT BUỘC):\n"
        "1. Tự nhiên, dễ nghe, như lời người Việt nói trong phim\n"
        "2. Giữ lại tôn chỉ, cảm xúc, tính cách nhân vật gốc\n"
        "3. Thay đổi cấu trúc câu nếu cần → nghe tự nhiên hơn\n"
        "4. Dùng từ phổ thông, tránh từ Hán học hoặc cứng nhắc\n"
        "5. Tính nhất quán nhân vật: nếu gọi tên là 'Du Vũ' ở dòng 1, dùng 'Du Vũ' ở mọi chỗ khác\n"
        "6. TUYỆT ĐỐI KHÔNG để lại chữ Hán trong kết quả\n\n"
        "DANH SÁCH TÊN NHÂN VẬT & KHÁI NIỆM (PHẢI DÙNG):\n"
        f"{glossary_str}\n\n"
        "ĐỊNH DẠNG ĐẦU RA:\n"
        "  Trả về từng dòng: ID|Văn bản_dịch\n"
        "  Ví dụ:\n"
        "    0|Xin chào, tôi tên là Du Vũ\n"
        "    1|Tôi tham gia sự kiện này vì...\n"
        "  Không thêm giải thích, nhận xét, hoặc dòng trống nào.\n\n"
        "VÍ DỤ CẢI THIỆN DỊCH:\n"
        "  ❌ 'Tôi đã đi đến một sự kiện có liên quan đến nữ thần phép thuật'\n"
        "  ✅ 'Tôi tham gia một sự kiện liên quan đến phép thuật'\n"
        "  \n"
        "  ❌ 'Bởi vì tôi đã trả lời trên diễn đàn Đông Hoa Luận Đàm'\n"
        "  ✅ 'Vì tôi đã trả lời một câu hỏi trên diễn đàn'\n"
        "  \n"
        "  ❌ 'Chết trong tầm tay của họ / Và để họ ôm lấy cơ thể tôi'\n"
        "  ✅ 'Họ bế tôi vào lòng / và ôm chặt tôi'\n\n"
        "NỘI DUNG CẦN DỊCH (toàn bộ):\n"
        f"{full_text_with_ids}"
    )

    for attempt in range(max_retries):
        try:
            logger.info("🌐 Dịch toàn bộ %d dòng cùng lúc (Gemini - lần %d/%d)...", len(texts), attempt + 1, max_retries)
            response = model.generate_content(
                prompt_content,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=8000,
                )
            )
            
            raw_text = response.text

            results = {}
            cjk_found = False
            
            for line in raw_text.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                
                match = re.search(r"(\d+)\s*\|\s*(.*)", line)
                if match:
                    idx_str = match.group(1).strip()
                    try:
                        idx = int(idx_str)
                        if idx < len(texts):
                            translated = match.group(2).strip()
                            translated = apply_glossary(translated)
                            
                            if contains_cjk(translated):
                                logger.warning(
                                    "⚠️ Phát hiện chữ Hán sót tại dòng %d: %s", idx, translated
                                )
                                cjk_found = True
                                # Thay thế bằng bản gốc
                                results[idx] = texts[idx]
                            else:
                                results[idx] = translated
                    except ValueError:
                        continue

            if cjk_found:
                raise ValueError("CJK characters detected in translation — retry")

            # Tạo kết quả cuối, dùng bản gốc nếu không có dịch
            final_results = [results.get(i, texts[i]) for i in range(len(texts))]

            logger.info("✅ Dịch toàn bộ thành công: %d dòng", len(final_results))
            return final_results

        except Exception as exc:
            logger.warning(
                "Lỗi dịch toàn bộ (lần %d/%d): %s",
                attempt + 1, max_retries, str(exc)[:150]
            )
            time.sleep(5)

    logger.error("❌ Dịch thuật thất bại sau %d lần thử. Giữ nguyên văn bản gốc.", max_retries)
    return texts

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
    Bước 1: Whisper nhận diện giọng nói → Bước 2: Gemini dịch sang tiếng Việt.
    
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

    if segments:
        logger.info(
            "🌐 Bắt đầu dịch TOÀN BỘ %d câu sang tiếng Việt (Model: %s)...", 
            len(segments), MODEL_NAME
        )
        
        # LẤY TẤT CẢ TEXTS VÀ DỊCH TOÀN BỘ CÙNG LẦN
        original_texts = [seg["text"] for seg in segments]
        translated_texts = translate_full_text(original_texts)
        
        # CẬP NHẬT TẤT CẢ SEGMENTS VỚI BẢN DỊCH
        for i, translated_text in enumerate(translated_texts):
            if i < len(segments):
                segments[i]["text"] = translated_text

    srt_text = segments_to_srt(segments)
    output_srt_path.parent.mkdir(parents=True, exist_ok=True)
    output_srt_path.write_text(srt_text, encoding="utf-8-sig")
    logger.info("✅ Đã lưu phụ đề: %s", output_srt_path)
    return output_srt_path