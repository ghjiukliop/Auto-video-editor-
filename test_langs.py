#!/usr/bin/env python3
from deep_translator import GoogleTranslator

langs = GoogleTranslator().get_supported_languages()
print(f"Total: {len(langs)} langs")
print(f"Type: {type(langs)}")
print(f"\nAll languages: {sorted(langs)}")
print(f"\nVietnamese: {'vietnamese' in langs, 'vi' in langs}")
print(f"Chinese: {'chinese' in langs, 'zh' in langs}")
