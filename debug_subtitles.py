from modules.srt_parser_optimized import load_srt
from pathlib import Path

# Check file gốc
original = load_srt(Path("test_subtitles_chinese.srt"))
print(f"Original file: {len(original)} subtitles")
print("=" * 70)
for sub in original[:3]:
    print(f"#{sub.index}\n{sub.start_time} --> {sub.end_time}\n{sub.content}\n")

# Check file dịch
translated = load_srt(Path("output/work/subtitles_translated.srt"))
print(f"\nTranslated file: {len(translated)} subtitles")
print("=" * 70)

# Show around #116
if len(translated) > 116:
    for i in range(110, min(120, len(translated))):
        sub = translated[i]
        print(f"#{sub.index} ({i+1})")
        print(f"{sub.start_time} --> {sub.end_time}")
        print(f"{sub.content[:80]}...")
        print()
