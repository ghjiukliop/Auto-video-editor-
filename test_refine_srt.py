#!/usr/bin/env python3
"""Test VietnameseRefiner với file SRT"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from pipeline import VietnameseRefiner

# Create a small test SRT file
test_srt = """1
00:00:00,000 --> 00:00:03,000
Tôi là người rất vui vì bạn đã đến

2
00:00:03,000 --> 00:00:06,000
Cô ấy là rất xinh đẹp và tốt bụng

3
00:00:06,000 --> 00:00:10,000
Nhân vật này đã được yêu thích bởi rất nhiều người trên toàn thế giới từ lâu

4
00:00:10,000 --> 00:00:13,000
Tuy nhiên, tôi vẫn không hiểu tại sao bạn không muốn nói chuyện với tôi
"""

# Write test SRT
input_srt = Path("test_refine_input.srt")
output_srt = Path("test_refine_output.srt")

with open(input_srt, 'w', encoding='utf-8') as f:
    f.write(test_srt)

# Run refiner
refiner = VietnameseRefiner()
refiner.refine(input_srt, output_srt)

# Show results
print("\n=== BEFORE ===")
with open(input_srt, 'r', encoding='utf-8') as f:
    print(f.read())

print("\n=== AFTER ===")
with open(output_srt, 'r', encoding='utf-8') as f:
    print(f.read())

# Cleanup
input_srt.unlink()
output_srt.unlink()
