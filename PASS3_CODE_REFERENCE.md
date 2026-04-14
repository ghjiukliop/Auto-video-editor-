# Pass 3 Chunk-Based Implementation - Code Reference

## Complete _pass_3_refactor() Method

Located in: `pipeline.py` lines ~415-510

### Method Signature
```python
def _pass_3_refactor(self, srt_path: Path) -> None:
```

### Algorithm

```
LOAD subtitles from srt_path

chunk_size = 8
refactored_count = 0

FOR each chunk of 8 subtitles:
    
    LOG "Refactor chunk X-Y/TOTAL"
    
    BUILD chunk SRT text
    
    CREATE comprehensive refactor prompt with instructions:
    - Gender consistency (anh/cô, ông/bà, tôi/ta)
    - Context appropriateness  
    - Natural dialogue tone
    - Professional dubbing quality
    - Preserve SRT format & timing
    
    CALL Ollama with chunk prompt
    
    PARSE returned text to subtitles
    
    IF parse successful AND count matches:
        UPDATE chunk subtitles in list
        LOG changes
        SAVE file (ATOMIC WRITE)
    
    ELSE:
        LOG warning
        KEEP original chunk
        SAVE file
    
    HANDLE errors:
        LOG error
        KEEP original chunk
        SAVE file
        CONTINUE to next chunk

LOG completion: X/N subtitles refactored
```

## Key Components

### 1. Chunk Iteration
```python
chunk_size = 8
for chunk_idx in range(0, len(subtitles), chunk_size):
    chunk = subtitles[chunk_idx:chunk_idx + chunk_size]
    start_idx = chunk_idx + 1
    end_idx = min(chunk_idx + chunk_size, len(subtitles))
```

### 2. SRT Text Building
```python
chunk_srt = self._subtitles_to_srt_text(chunk)
# Converts [Subtitle1, Subtitle2, ...] → SRT format string
```

### 3. Refactor Prompt
```python
refactor_chunk_prompt = (
    f"Bạn là chuyên gia lồng tiếng phim tiếng Việt. "
    f"Hãy tinh chỉnh toàn bộ phụ đề sau sao cho:\n"
    f"1. Giới tính & xưng hô nhất quán\n"
    f"2. Bối cảnh & lời thoại phù hợp nhân vật\n"
    f"3. Ngữ điệu sôi động & chân thực\n"
    f"4. Tự nhiên như lồng tiếng chuyên nghiệp\n"
    f"5. Giữ nguyên định dạng SRT (timing không đổi)\n\n"
    f"Phụ đề:\n{chunk_srt}\n\n"
    f"Trả về phụ đề đã chỉnh sửa theo format SRT gốc."
)
```

### 4. Ollama Call
```python
refactored_chunk_text = self._call_ollama(refactor_chunk_prompt)
```

### 5. Parse Return
```python
refactored_chunk = self._parse_srt_from_text(refactored_chunk_text)
```

### 6. Validation & Update
```python
if refactored_chunk and len(refactored_chunk) == len(chunk):
    # Success: update subtitles
    for i, refactored_sub in enumerate(refactored_chunk):
        chunk[i].content = refactored_sub.content
        refactored_count += 1
else:
    # Parse error: keep original
    LOG warning
```

### 7. Atomic Write
```python
save_srt(subtitles, srt_path)  # Save after EVERY chunk
```

## Error Handling Strategy

### Level 1: Try Block (Per Chunk)
```python
try:
    # Process chunk
    # Parse result
    # Update subtitles
    # Atomic write
except Exception as e:
    # Log error message
    # Keep original chunk unchanged
    # Save file
    # Continue to next chunk
```

### Level 2: Try Block (Overall)
```python
try:
    # Process all chunks
    LOG success
except Exception as e:
    # Log fatal error
    # Don't raise (pipeline continues)
```

### Key Principle
- Never crash the pipeline
- Always save file (even if error)
- Best-effort approach: if chunk fails, keep original
- Continue processing remaining chunks

## Comparison: Old vs New

### Old Pass 3 (Problems)
```
FOR each subtitle:
    context = current_sub + next_sub (only 2)
    refactored = ollama.call(prompt)
    save_srt()

PROBLEM: 
- Insufficient context for gender/pronoun fixes
- File corruption at #116 from accumulated errors
```

### New Pass 3 (Solution)
```
chunk_size = 8
FOR each chunk of 8 subtitles:
    chunk_srt = build_srt_text(chunk)
    refactored = ollama.call(comprehensive_prompt)
    save_srt()

BENEFITS:
- 8-subtitle context window
- Comprehensive refactoring
- Better gender/pronoun handling
- No accumulated corruption
```

## Integration with Other Methods

### Used By
- `translate()` - Calls `_pass_3_refactor()` as final pass

### Uses
- `load_srt()` - Load subtitles from file
- `save_srt()` - Save subtitles to file (ATOMIC)
- `_call_ollama()` - Send prompts to Ollama
- `_subtitles_to_srt_text()` - Convert subtitle list to SRT text
- `_parse_srt_from_text()` - Parse SRT text back to subtitle objects

## Logging Output

### Per Chunk
```
✅ Load N subtitle cho Pass 3
   [Refactor chunk 1-8/100] (8 subtitle)
      [#1] Original text → Refactored text
      [#2] Original text → Refactored text
      ...
      ✓ Chunk 1-8 refactor xong
   [Refactor chunk 9-16/100] (8 subtitle)
      ...
✅ Pass 3 XONG: X/N subtitle refactored
```

### On Error
```
⚠️  Parse lỗi (được 5, expected 8) - giữ nguyên chunk
⚠️  Chunk 17-24 lỗi: Connection timeout - giữ nguyên
```

## Performance Characteristics

- **Time per chunk**: ~3-10 seconds (depends on Ollama model)
- **Memory**: One chunk in memory at a time (8 subs)
- **File I/O**: Save after each chunk (6-12 writes for typical file)
- **Network**: 1 API call per chunk (~12 calls for 100 subtitles)

## Customization Points

| Parameter | Current | Purpose | Changeable |
|-----------|---------|---------|-----------|
| chunk_size | 8 | Subtitles per chunk | ✅ Yes |
| Temperature | 0.3 | (in _call_ollama) | ✅ Yes |
| Model | qwen2.5:7b | (from config) | ✅ Yes |
| Top_p | 0.9 | (in _call_ollama) | ✅ Yes |

### To Change Chunk Size
```python
# In _pass_3_refactor(), line: chunk_size = 8
chunk_size = 10  # Increase for more context
# or
chunk_size = 5   # Decrease for faster processing
```

---

**Last Update:** April 15, 2026  
**Status:** ✅ Production Ready
