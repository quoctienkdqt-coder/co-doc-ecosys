import sys

sys.stdout.reconfigure(encoding='utf-8')

def check_js_syntax(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        code = f.read()

    stack = []
    lines = code.split("\n")
    in_single_line_comment = False
    in_multi_line_comment = False
    in_string = False
    string_char = ""
    escaped = False

    for line_num, line in enumerate(lines, 1):
        i = 0
        while i < len(line):
            ch = line[i]

            if in_multi_line_comment:
                if ch == "*" and i + 1 < len(line) and line[i+1] == "/":
                    in_multi_line_comment = False
                    i += 1
                i += 1
                continue

            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == string_char:
                    in_string = False
                i += 1
                continue

            # Check start of comments
            if ch == "/" and i + 1 < len(line):
                if line[i+1] == "/":
                    break # Single line comment, ignore rest of line
                elif line[i+1] == "*":
                    in_multi_line_comment = True
                    i += 2
                    continue

            # Check start of strings
            if ch in ['"', "'", "`"]:
                in_string = True
                string_char = ch
                i += 1
                continue

            # Check brackets
            if ch in ["(", "{", "["]:
                stack.append((ch, line_num, i))
            elif ch in [")", "}", "]"]:
                if not stack:
                    return f"Unmatched closing '{ch}' at line {line_num}:{i}"
                last_ch, last_line, last_col = stack.pop()
                expected = {"(": ")", "{": "}", "[": "]"}[last_ch]
                if ch != expected:
                    return f"Mismatched bracket: expected '{expected}' (opened at line {last_line}:{last_col}) but found '{ch}' at line {line_num}:{i}"

            i += 1

    if stack:
        last_ch, last_line, last_col = stack.pop()
        return f"Unclosed bracket: '{last_ch}' opened at line {last_line}:{last_col}"

    return "OK"

for f in ["extension/injected_proxy.js", "extension/background.js", "extension/content.js"]:
    res = check_js_syntax(f)
    print(f"{f}: {res}")
