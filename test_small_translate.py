#!/usr/bin/env python3
"""Test dịch một số phụ đề nhỏ"""

from pathlib import Path
import srt
from googletrans import Translator

# Import ChineseDetector từ pipeline
import sys
sys.path.insert(0, str(Path(__file__).parent))
from pipeline import ChineseDetector

# Load subtitles từ file
srt_file = Path("output/work/subtitles_original.srt")
with open(srt_file, 'r', encoding='utf-8-sig') as f:
    subs = list(srt.parse(f))

print(f"Total: {len(subs)} subtitles")

# Find first 5 with Chinese
chinese_subs = [(i, sub) for i, sub in enumerate(subs) if ChineseDetector.has_chinese(sub.content)]
print(f"Chinese: {len(chinese_subs)} subtitles\n")

# Test translate 5 first
translator = Translator()
for idx in range(min(5, len(chinese_subs))):
    i, sub = chinese_subs[idx]
    original = sub.content
    
    # Translate
    result = translator.translate(original, src='zh-CN', dest='vi')
    translated = result.text
    
    print(f"[{i}]")
    print(f"  Original: {original[:60]}")
    print(f"  Translated: {translated[:60]}")
    print()
