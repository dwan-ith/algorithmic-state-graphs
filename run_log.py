"""
Run each benchmark independently and write clean output to log.txt
"""
import sys, io, traceback
sys.path.insert(0, '.')

def run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        return {'errors': -1, '_crash': traceback.format_exc()}

lines = []

from benchmark import bench_prim, bench_kruskal, bench_dijkstra, bench_astar, bench_maxflow

CONFIGS = [
    (200, 100, 0.05, 'mixed',    'random sparse n=200'),
    (200, 100, 0.05, 'increase', 'targeted increases n=200'),
    (500,  50, 0.04, 'mixed',    'random sparse n=500'),
]

for algo_name, fn in [
    ('Prim',     bench_prim),
    ('Kruskal',  bench_kruskal),
    ('Dijkstra', bench_dijkstra),
    ('A*',       bench_astar),
    ('MaxFlow',  bench_maxflow),
]:
    lines.append(f'\n### {algo_name}\n')
    for n, upd, ep, mode, label in CONFIGS:
        r = run(fn, n, upd, ep, mode)
        lines.append(f'  [{label}]')
        if r.get('_crash'):
            lines.append(f'    CRASHED: {r["_crash"][:400]}')
        else:
            lines.append(f'    errors       : {r["errors"]}')
            lines.append(f'    fast_rate    : {r.get("fast_rate",0)*100:.1f}%')
            lines.append(f'    speedup      : {r.get("speedup",0):.2f}x')
            lines.append(f'    dyn_ms       : {r.get("t_dyn_ms",0):.2f}')
            lines.append(f'    static_ms    : {r.get("t_static_ms",0):.2f}')
            if 'sensitivity' in r:
                lines.append(f'    sensitivity  : {r["sensitivity"]*100:.2f}%')
            if 'avg_expansions' in r:
                lines.append(f'    avg_expand   : {r["avg_expansions"]:.2f}')
        lines.append('')

with open('log.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print('done')
