import os
import sys
import logging
import time
import json
import requests
import re
from pathlib import Path
from typing import Literal
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

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ĐỔI SANG MODEL 8B ĐỂ TRÁNH LỖI 429 (Dẫn đến việc bị trả về tiếng Trung)
MODEL_NAME = "llama-3.1-8b-instant"

def translate_with_retry(texts: list[str], max_retries=3) -> list[str]:
    """Dịch ép buộc Hán-Việt và chống sót chữ Hán"""
    if not GROQ_API_KEY:
        return texts

    url = "https://api.groq.com/openai/v1/chat/completions"
    
    # PROMPT ĐÃ ĐƯỢC NÂNG CẤP ĐỂ XỬ LÝ TÊN NHÂN VẬT
    prompt_content = (
        "Bạn là chuyên gia dịch thuật phim Trung-Việt chuyên nghiệp.\n"
        "NHIỆM VỤ: Dịch các câu thoại sau sang tiếng Việt tự nhiên.\n"
        "YÊU CẦU BẮT BUỘC:\n"
        "1. GIỮ NGUYÊN ĐỊNH DẠNG ID|Văn bản. Không thêm lời giải thích.\n"
        "2. TUYỆT ĐỐI KHÔNG để lại chữ Hán trong kết quả. TẤT CẢ tên riêng (như 悠雨) PHẢI được phiên âm sang âm Hán-Việt (ví dụ: 悠雨 -> Du Vũ, 林 -> Lâm).\n"
        "3. Nếu không dịch được, hãy cố gắng phiên âm Hán-Việt cho toàn bộ câu đó.\n"
    )
    prompt_content += "\n".join([f"{i}|{t}" for i, t in enumerate(texts)])
    
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "Bạn là máy dịch phim chuyên nghiệp, chỉ trả về kết quả dưới dạng ID|Văn bản."},
            {"role": "user", "content": prompt_content}
        ],
        "temperature": 0.1
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=45)
            
            if response.status_code == 429:
                wait_time = (attempt + 1) * 20
                logger.warning(f"Chạm giới hạn Groq. Đang nghỉ {wait_time}s...")
                time.sleep(wait_time)
                continue
                
            if response.status_code == 200:
                data = response.json()
                raw_text = data['choices'][0]['message']['content']
                
                results = {}
                lines = raw_text.strip().split("\n")
                for line in lines:
                    match = re.search(r"(\d+)\s*\|\s*(.*)", line)
                    if match:
                        results[int(match.group(1))] = match.group(2).strip()
                
                return [results.get(i, texts[i]) for i in range(len(texts))]
            
            time.sleep(5)
        except Exception as e:
            logger.warning(f"Lỗi kết nối dịch thuật: {str(e)[:50]}")
            time.sleep(5)

    return texts

def transcribe_to_srt(
    audio_path: Path,
    output_srt_path: Path,
    model_name: str,
    lang: Literal["vi", "en", "zh", "auto"] = "auto",
) -> Path:
    import whisper
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    logger.info(f"Loading Whisper model {model_name} on {device}")
    model = whisper.load_model(model_name, device=device)
    
    # Bước 1: Whisper trích xuất tiếng Trung chuẩn
    result = model.transcribe(str(audio_path), language="zh" if lang == "zh" or lang == "auto" else None, verbose=False)
    segments = result.get("segments", [])
    
    if segments:
        logger.info(f"Bắt đầu dịch {len(segments)} câu sang tiếng Việt (Model: {MODEL_NAME})...")
        batch_size = 25
        
        for i in tqdm(range(0, len(segments), batch_size), desc="Đang dịch"):
            batch = segments[i:i + batch_size]
            original_texts = [seg["text"] for seg in batch]
            
            translated_texts = translate_with_retry(original_texts)
            
            for j, translated_text in enumerate(translated_texts):
                if j < len(batch):
                    batch[j]["text"] = translated_text
            
            # Nghỉ ngắn để lách luật API
            time.sleep(1.5)

    srt_text = segments_to_srt(segments)
    output_srt_path.write_text(srt_text, encoding="utf-8-sig")
    return output_srt_path