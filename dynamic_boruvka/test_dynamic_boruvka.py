import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time
from dynamic_boruvka import DynamicBoruvka
from core.graph_generator import generate_random_connected_graph, get_locality_perturbation

def test_boruvka():
    n = 200
    edges = generate_random_connected_graph(n, 0.05)
    
    dyn_bor = DynamicBoruvka(n)
    for u, v, w in edges:
        dyn_bor.add_edge(u, v, w)
        
    dyn_bor.compute_initial()
    initial_mst = dyn_bor.get_mst_edges()
    
    st_bor = DynamicBoruvka(n)
    for u, v, w in edges:
        st_bor.add_edge(u, v, w)
    st_bor.compute_initial()
    assert initial_mst == st_bor.get_mst_edges()
    
    updates = 100
    for i in range(updates):
        u, v, w_new = get_locality_perturbation(edges, n)
        
        dyn_bor.update_edge(u, v, w_new)
        dyn_mst = dyn_bor.get_mst_edges()
        
        # Ground truth static rebuild
        st = DynamicBoruvka(n)
        for eu, ev, ew in edges:
            st.add_edge(eu, ev, ew)
        st.compute_initial()
        st_mst = st.get_mst_edges()
        
        dyn_weight = sum(w for u, v, w in dyn_mst)
        st_weight = sum(w for u, v, w in st_mst)
        
        if dyn_weight != st_weight:
            print(f"Error at update {i}: {u}-{v}={w_new} (Weight Dyn: {dyn_weight}, St: {st_weight})")
            assert False, "Weights mismatched!"
            
    print("Boruvka tests passed!")
    print(f"--- METRICS ---")
    print(f"Updates: {updates}")
    print(f"Fast Repairs (No cascade): {dyn_bor.fast_repairs}")
    print(f"Rebuilds: {dyn_bor.rebuilds_triggered}")
    print(f"Bypassed Recomputation: {dyn_bor.fast_repairs / updates * 100:.1f}%")

if __name__ == "__main__":
    test_boruvka()
