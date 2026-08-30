import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dynamic_dijkstra import DynamicDijkstra
from core.graph_generator import generate_random_connected_graph, get_locality_perturbation

def test_dijkstra():
    n = 200
    edges = generate_random_connected_graph(n, 0.05)
    
    dyn_dij = DynamicDijkstra(n)
    for u, v, w in edges:
        dyn_dij.add_edge(u, v, w)
        
    dyn_dij.compute_initial()
    initial_dist = dyn_dij.get_distances()
    
    st_dij = DynamicDijkstra(n)
    for u, v, w in edges:
        st_dij.add_edge(u, v, w)
    st_dij.compute_initial()
    assert initial_dist == st_dij.get_distances()
    
    updates = 100
    for i in range(updates):
        u, v, w_new = get_locality_perturbation(edges, n)
        
        dyn_dij.update_edge(u, v, w_new)
        dyn_dist = dyn_dij.get_distances()
        
        st = DynamicDijkstra(n)
        for eu, ev, ew in edges:
            st.add_edge(eu, ev, ew)
        st.compute_initial()
        st_dist = st.get_distances()
        
        if dyn_dist != st_dist:
            print(f"Error at update {i}: {u}-{v}={w_new}")
            assert False, "Distance arrays mismatched!"
            
    print("Dijkstra tests passed!")
    print(f"--- METRICS ---")
    print(f"Updates: {updates}")
    print(f"Fast Repairs (No cascade): {dyn_dij.fast_repairs}")
    print(f"Rebuilds: {dyn_dij.rebuilds_triggered}")
    print(f"Bypassed Recomputation: {dyn_dij.fast_repairs / updates * 100:.1f}%")

if __name__ == "__main__":
    test_dijkstra()
