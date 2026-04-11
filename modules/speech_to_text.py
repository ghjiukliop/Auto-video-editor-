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
load_dotenv() # Tự động tìm và đọc file .env

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# CẤU HÌNH GROQ
MODEL_NAME = "llama-3.3-70b-versatile"

def translate_with_retry(texts: list[str], max_retries=3) -> list[str]:
    """Dịch có cơ chế thử lại nếu gặp lỗi Rate Limit hoặc Kết nối"""
    url = "https://api.groq.com/openai/v1/chat/completions"
    prompt_content = (
        "Bạn là chuyên gia dịch thuật phim. Hãy dịch các câu sau sang tiếng Việt.\n"
        "YÊU CẦU: GIỮ NGUYÊN ĐỊNH DẠNG ID|Văn bản. Không thêm lời giải thích.\n"
    )
    prompt_content += "\n".join([f"{i}|{t}" for i, t in enumerate(texts)])
    
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt_content}],
        "temperature": 0.1
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=45)
            
            if response.status_code == 429: # Chạm giới hạn tốc độ
                wait_time = (attempt + 1) * 10
                logger.warning(f"Chạm giới hạn tốc độ. Đang đợi {wait_time}s để thử lại...")
                time.sleep(wait_time)
                continue
                
            if response.status_code == 200:
                data = response.json()
                raw_text = data['choices'][0]['message']['content']
                
                # Parsing thông minh: Tìm tất cả các dòng có dạng 'số|chữ'
                results = {}
                lines = raw_text.strip().split("\n")
                for line in lines:
                    match = re.search(r"(\d+)\s*\|\s*(.*)", line)
                    if match:
                        idx = int(match.group(1))
                        content = match.group(2).strip()
                        results[idx] = content
                
                # Kiểm tra xem có đủ câu không
                final_output = [results.get(i, texts[i]) for i in range(len(texts))]
                return final_output
            
            else:
                logger.error(f"Lỗi API {response.status_code}. Thử lại lần {attempt+1}...")
                time.sleep(5)
                
        except Exception as e:
            logger.warning(f"Lỗi kết nối: {str(e)[:50]}. Thử lại sau 5s...")
            time.sleep(5)

    return texts # Sau 3 lần thất bại, trả về bản gốc để không treo app

def transcribe_to_srt(
    audio_path: Path,
    output_srt_path: Path,
    model_name: str,
    lang: Literal["vi", "en", "zh", "auto"] = "auto",
) -> Path:
    import whisper
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    logger.info(f"Loading Whisper model {model_name}")
    model = whisper.load_model(model_name, device=device)
    result = model.transcribe(str(audio_path), language="zh" if lang == "zh" else None, verbose=False)
    segments = result.get("segments", [])
    
    if segments:
        logger.info(f"Bắt đầu dịch {len(segments)} câu. Đang dùng chế độ Chống Lỗi Chunk...")
        batch_size = 20 # Giảm size batch để AI dịch chính xác hơn
        
        for i in tqdm(range(0, len(segments), batch_size), desc="Đang dịch"):
            batch = segments[i:i + batch_size]
            original_texts = [seg["text"] for seg in batch]
            
            translated_texts = translate_with_retry(original_texts)
            
            for j, translated_text in enumerate(translated_texts):
                if j < len(batch):
                    # Chống lỗi: Nếu AI trả về tiếng Trung, giữ nguyên để bước sau lọc tiếp
                    batch[j]["text"] = translated_text
            
            # Nghỉ 4 giây giữa các batch để giữ cho API 'vui vẻ'
            time.sleep(4)

    srt_text = segments_to_srt(segments)
    with open(output_srt_path, "w", encoding="utf-8-sig") as f:
        f.write(srt_text)
        
    return output_srt_path

import torch # Đảm bảo import torch ở cuối hoặc đầu file