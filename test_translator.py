#!/usr/bin/env python3
"""Test translator để debug response từ Ollama"""

import sys
import logging
from pathlib import Path
from typing import List, Tuple, Dict

sys.path.insert(0, str(Path(__file__).parent))

import re
try:
    import ollama
except ImportError:
    print("❌ Cần cài: pip install ollama")
    sys.exit(1)

# Setup logging DEBUG
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger("test")

# Import từ pipeline
from pipeline import ChineseDetector

class TestTranslator:
    def __init__(self, model: str = "qwen2.5:7b"):
        self.model = model
    
    def test_batch(self, texts: List[str]):
        """Test dịch một batch nhỏ"""
        batch = [(i, text) for i, text in enumerate(texts)]
        
        batch_text = "\n".join([f"{idx}#{content}" for idx, content in batch])
        
        prompt = f"""Bạn là translator giỏi từ tiếng Trung sang tiếng Việt.
CHỈ TRẢ LỜI DƯỚI DẠNG: số#dịch
KHÔNG GIẢI THÍCH, không thêm gì cả!

{batch_text}

Trả lời (CHỈ định dạng số#dịch):"""
        
        logger.info(f"📤 SEND PROMPT:\n{prompt}\n")
        
        try:
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                stream=False,
                options={"temperature": 0.1, "top_p": 0.9}
            )
            
            raw_response = response['response']
            logger.info(f"📥 RAW RESPONSE:\n{raw_response}\n")
            
            # Parse
            result = self._parse_response(raw_response, len(batch))
            logger.info(f"✅ PARSED: {result}\n")
            
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    def _parse_response(self, text: str, expected_count: int) -> Dict[int, str]:
        """Parse response định dạng: số#dịch."""
        result = {}
        for line in text.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            match = re.match(r'^(\d+)[#→]\s*(.+)$', line)
            if match:
                try:
                    idx = int(match.group(1))
                    content = match.group(2).strip()
                    if idx < expected_count and len(content) > 2:
                        result[idx] = content
                except (ValueError, IndexError):
                    pass
        return result

if __name__ == "__main__":
    test_texts = [
        "我就要憂鬱,我穿越到了一個有著魔法少女的事件",
        "只因為我在東華論壇上回答了擊敗魔法少女最好的方法是什麼",
        "我笑著打倒,那就是在她一無所知的時候",
    ]
    
    translator = TestTranslator()
    logger.info("🧪 TEST TRANSLATOR - Dịch 3 phụ đề\n")
    translator.test_batch(test_texts)
