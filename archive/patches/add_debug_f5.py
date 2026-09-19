# -*- coding: utf-8 -*-
"""Add F5 print marker to predict_match.py for debugging."""
path = 'predict_match.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = '        elif market_clean in {"f5", "first5", "first_5"}:'
new = '        elif market_clean in {"f5", "first5", "first_5"}:\n            import sys; sys.stderr.write("[F5] Running F5 handler\\n"); sys.stderr.flush()'

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('OK: debug print added')
else:
    print('FAIL: Pattern not found')
    # Find the F5 line
    idx = content.find('first_5')
    if idx >= 0:
        print('Found at', idx)
        print(repr(content[idx:idx+80]))
    idx2 = content.find('"f5"')
    if idx2 >= 0:
        print('Found "f5" at', idx2)
        print(repr(content[idx2:idx2+80]))