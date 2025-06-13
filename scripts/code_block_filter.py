# In a separate file: code_block_filter.py
#!/usr/bin/env python3
import json
import sys
from pandocfilters import toJSONFilter, CodeBlock

def code_block_filter(key, value, format, meta):
    if key == 'CodeBlock':
        [[ident, classes, keyvals], code] = value
        # Process code block as needed
        return CodeBlock([ident, classes, keyvals], code)

if __name__ == "__main__":
    toJSONFilter(code_block_filter)