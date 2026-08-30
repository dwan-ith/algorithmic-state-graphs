with open('diff.log', 'r', encoding='utf-8') as f:
    text = f.read()

import ast
lines = text.split('\n')
print(lines[0])

def print_set(s):
    # s is like "Dyn MST missing: {(a,b,c), ...}"
    prefix, sep, data = s.partition('{')
    if not data:
        print(s)
        return
    data = '{' + data
    try:
        edges = ast.literal_eval(data)
        print(prefix)
        for e in edges:
            print("  ", e)
    except Exception as e:
        print(s)

print_set(lines[1])
print_set(lines[2])
