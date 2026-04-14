#!/usr/bin/env python3
"""Test VietnameseRefiner"""

import sys
import io
from pathlib import Path

# Fix encoding for Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent))

from pipeline import VietnameseRefiner

refiner = VietnameseRefiner()

test_cases = [
    "Tôi rất vui vì bạn đã đến",
    "Cô ấy là rất xinh đẹp",
    "Nhân vật này đã được yêu thích bởi người dân trên toàn thế giới",
    "Tuy nhiên, tôi vẫn không hiểu tại sao bạn lại làm như vậy",
    "Đó là một câu chuyện dài dòng và phức tạp mà tôi không thể giải thích hết trong một vài từ ngắn.",
]

print("=== VIETNAMESE REFINER TEST ===\n")
for original in test_cases:
    refined = refiner._refine_text(original)
    is_shortened = len(refined) < len(original)
    print(f"Original ({len(original)} chars):")
    print(f"  {original}\n")
    print(f"Refined ({len(refined)} chars{'  [SHORTENED]' if is_shortened else ''}):")
    print(f"  {refined}\n")
    print("-" * 60)
