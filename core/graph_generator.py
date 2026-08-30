import random


def generate_random_connected_graph(n, p, max_weight=100):
    """Random connected undirected graph as a list of (u, v, w) triples.

    A random spanning tree guarantees connectivity; extra edges are added
    independently with probability p.
    """
    edges_dict = {}

    # Ensure connectivity: random spanning tree
    nodes = list(range(n))
    random.shuffle(nodes)
    for i in range(1, n):
        u = nodes[i]
        v = nodes[random.randint(0, i - 1)]
        w = random.randint(1, max_weight)
        edges_dict[(min(u, v), max(u, v))] = w

    # Add random edges
    for i in range(n):
        for j in range(i + 1, n):
            if (i, j) not in edges_dict and random.random() < p:
                edges_dict[(i, j)] = random.randint(1, max_weight)

    return [(u, v, w) for (u, v), w in edges_dict.items()]


def get_locality_perturbation(edges, n=None, max_weight=100):
    """Pick one edge and mutate it in place.

    Mutates and returns the chosen entry of `edges` (list of triples).
    The `n` argument is accepted for backward compatibility and ignored.
      * decrease / increase: weight changes by a random amount,
      * delete: weight becomes inf,
      * an inf ("deleted") edge may be revived with a finite weight.
    """
    op = random.choice(["decrease", "increase", "delete"])
    idx = random.randint(0, len(edges) - 1)
    u, v, w = edges[idx]

    if op == "decrease":
        if w == float('inf'):
            w = max_weight
        new_w = max(1, w - random.randint(1, w // 2 + 1))
    elif op == "increase":
        if w == float('inf'):
            w = max_weight
        new_w = w + random.randint(1, 50)
    else:  # delete
        new_w = float('inf')

    edges[idx] = (u, v, new_w)
    return (u, v, new_w)
