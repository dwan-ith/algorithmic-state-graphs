import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import random
from dynamic_maxflow import DynamicMaxFlow

def generate_random_flow_graph(n, max_cap=20):
    edges = []
    # Directed random graph ensuring path from 0 to n-1
    for i in range(n-1):
        # path ensuring connectivity
        edges.append((i, i+1, random.randint(1, max_cap)))
        
    for _ in range(n * 2):
        u = random.randint(0, n-2)
        v = random.randint(u+1, n-1)
        w = random.randint(1, max_cap)
        edges.append((u, v, w))
    return edges

def test_maxflow():
    n = 50
    edges = generate_random_flow_graph(n)
    
    dyn_mf = DynamicMaxFlow(n, 0, n-1)
    for u, v, w in edges:
        dyn_mf.add_edge(u, v, w)
        
    dyn_mf.compute_initial()
    
    updates = 50
    for i in range(updates):
        idx = random.randint(0, len(edges)-1)
        u, v, w = edges[idx]
        
        op = random.choice(["increase", "decrease"])
        if op == "increase":
            new_w = w + random.randint(1, 10)
        else:
            new_w = max(0, w - random.randint(1, 10))
            
        edges[idx] = (u, v, new_w)
        
        dyn_mf.update_edge(u, v, new_w)
        dyn_flow = dyn_mf.get_max_flow()
        
        # Ground truth static
        st = DynamicMaxFlow(n, 0, n-1)
        for eu, ev, ew in edges:
            st.add_edge(eu, ev, ew)
        st.compute_initial()
        st_flow = st.get_max_flow()
        
        if dyn_flow != st_flow:
            print(f"Error at update {i}: {u}-{v}: {w}->{new_w}. Dyn: {dyn_flow}, St: {st_flow}")
            assert False, "Flow mismatch!"
            
    print("Max Flow tests passed!")
    print(f"--- METRICS ---")
    print(f"Updates: {updates}")
    print(f"Fast Repairs (Feasible old flow): {dyn_mf.fast_repairs}")
    print(f"Total Incremental Augmentations: {dyn_mf.augmentations}")

if __name__ == "__main__":
    test_maxflow()
