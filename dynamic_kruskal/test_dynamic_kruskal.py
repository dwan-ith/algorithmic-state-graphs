import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dynamic_kruskal import DynamicKruskal
from core.graph_generator import generate_random_connected_graph, get_locality_perturbation

def test_kruskal():
    n = 200
    edges = generate_random_connected_graph(n, 0.05)
    
    dyn_k = DynamicKruskal(n)
    for u, v, w in edges:
        dyn_k.add_edge(u, v, w)
        
    dyn_k.compute_initial()
    initial_mst = dyn_k.get_mst_edges()
    
    updates = 100
    for i in range(updates):
        u, v, w_new = get_locality_perturbation(edges, n)
        dyn_k.update_edge(u, v, w_new)
        dyn_mst = dyn_k.get_mst_edges()
        
        # Ground truth static rebuild
        st = DynamicKruskal(n)
        for eu, ev, ew in edges:
            st.add_edge(eu, ev, ew)
        st.compute_initial()
        st_mst = st.get_mst_edges()
        
        dyn_weight = sum(w for u, v, w in dyn_mst)
        st_weight = sum(w for u, v, w in st_mst)
        
        if dyn_weight != st_weight:
            print(f"Error at update {i}: {u}-{v}={w_new} (Weight Dyn: {dyn_weight}, St: {st_weight})")
            assert False, "Weights mismatched!"
            
    print("Kruskal tests passed!")
    print(f"--- METRICS ---")
    print(f"Updates: {updates}")
    print(f"Fast Repairs (No cascade): {dyn_k.fast_repairs}")
    print(f"Rebuilds: {dyn_k.rebuilds}")
    print(f"Bypassed Recomputation: {dyn_k.fast_repairs / updates * 100:.1f}%")

if __name__ == "__main__":
    test_kruskal()
