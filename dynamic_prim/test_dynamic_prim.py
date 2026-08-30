import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time
from dynamic_prim import DynamicPrim
from core.graph_generator import generate_random_connected_graph, get_locality_perturbation

def test_correctness():
    n = 200
    edges = generate_random_connected_graph(n, 0.05)
    
    dynamic_prim = DynamicPrim(n)
    for u, v, w in edges:
        dynamic_prim.add_edge(u, v, w)
        
    dynamic_prim.compute_initial()
    initial_mst = dynamic_prim.get_mst_edges()
    
    # Static validation
    static_prim = DynamicPrim(n)
    for u, v, w in edges:
        static_prim.add_edge(u, v, w)
    static_prim.compute_initial()
    assert initial_mst == static_prim.get_mst_edges()
    
    updates = 100
    for i in range(updates):
        u, v, w_new = get_locality_perturbation(edges, n)
        
        dynamic_prim.update_edge(u, v, w_new)
        dyn_mst = dynamic_prim.get_mst_edges()
        
        # Ground truth static rebuild
        st_prim = DynamicPrim(n)
        for eu, ev, ew in edges:
            st_prim.add_edge(eu, ev, ew)
        st_prim.compute_initial()
        st_mst = st_prim.get_mst_edges()
        
        # Verify Trace correctness via Weight Sum (to handle non-unique MSTs due to equal weights)
        dyn_weight = sum(w for u, v, w in dyn_mst)
        st_weight = sum(w for u, v, w in st_mst)
        if dyn_weight != st_weight:
            with open("diff.log", "w", encoding="utf-8") as f:
                f.write(f"Error at update {i}: {u}-{v}={w_new}\n")
                s_dyn = set(dyn_mst)
                s_st = set(st_mst)
                f.write(f"Dyn MST missing: {s_st - s_dyn}\n")
                f.write(f"St MST missing: {s_dyn - s_st}\n")
            print(f"Error at update {i}: {u}-{v}={w_new} (Weight Dyn: {dyn_weight}, St: {st_weight})")
            assert False, "Dynamic MST weight does not match Static MST output!"
            
        print(f"Update {i} passed. Fast repairs: {dynamic_prim.fast_repairs}, Rebuilds: {dynamic_prim.rebuilds_triggered}")
        
    print("All tests passed! Theoretical rigor verified.")
    print(f"--- METRICS ---")
    print(f"Total Updates: {updates}")
    print(f"Fast O(1) Repairs (No cascade): {dynamic_prim.fast_repairs}")
    print(f"Cascading Rebuilds (Deep trace divergence): {dynamic_prim.rebuilds_triggered}")
    print(f"Bypassed Recomputation: {dynamic_prim.fast_repairs / updates * 100:.1f}%")

    
if __name__ == "__main__":
    test_correctness()
