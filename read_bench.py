with open('bench_out.txt', 'rb') as f:
    raw = f.read()
text = raw.decode('utf-8-sig', errors='replace')
for line in text.splitlines():
    if line.strip():
        print(line)
