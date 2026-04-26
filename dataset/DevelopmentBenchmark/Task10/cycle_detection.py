import pandas as pd
import os

# ---- Cycle detection using DFS ----
def has_cycle(graph):
    visited = set()
    stack = set()

    def dfs(node):
        if node not in visited:
            visited.add(node)
            stack.add(node)
            for neighbor in graph.get(node, []):
                if neighbor not in visited and dfs(neighbor):
                    return True
                elif neighbor in stack:
                    return True
            stack.remove(node)
        return False

    return any(dfs(node) for node in graph)

# ---- Read one graph ----
def read_graph(csv_path):
    df = pd.read_csv(csv_path)
    graph = {}
    for _, row in df.iterrows():
        node_from = str(row["Node From"]).strip()
        node_to_raw = str(row["Node To"])
        # split with ,
        node_to_list = [n.strip() for n in node_to_raw.split(",") if n.strip()]
        graph[node_from] = node_to_list
    return graph

# ---- Main ----
results = []
base_path = ""

for i in range(1, 6):  # graph_1.csv ~ graph_5.csv
    file_path = os.path.join(base_path, f"tc10_input0{i}.csv")
    graph = read_graph(file_path)
    contains_cycle = has_cycle(graph)
    results.append({
        "Graph ID": f"graph_{i}",
        "Contains Cycle (True / False)": contains_cycle
    })

# ---- Save results ----
output_df = pd.DataFrame(results)
output_df.to_excel("output10.xlsx", index=False)

print("✅ Cycle detection results saved to output10.xlsx")
