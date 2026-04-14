#!/usr/bin/env python3
from deep_translator import GoogleTranslator

t = GoogleTranslator(source_language='zh', target_language='vi')
result = t.translate('我很开心')
print(f"Input: 我很开心")
print(f"Output: {result}")
