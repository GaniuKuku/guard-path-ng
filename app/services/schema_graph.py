from collections import defaultdict


class SchemaGraph:

    def __init__(self, schema: dict):
        self.schema = schema
        self.graph = defaultdict(list)
        self.reverse_graph = defaultdict(list)

        self._build_graph()

    def _build_graph(self):

        for table_name, table_data in self.schema["tables"].items():

            foreign_keys = table_data.get("foreign_keys", [])

            for fk in foreign_keys:

                from_col = fk["from_column"]
                to_table = fk["to_table"]
                to_col = fk["to_column"]

                # directed relationship
                self.graph[table_name].append(to_table)

                # reverse relationship
                self.reverse_graph[to_table].append(table_name)

    def get_join_path(self, tables: list):

        """
        Given required tables, return valid join order.
        """

        if len(tables) <= 1:
            return tables

        visited = set()
        path = []

        def dfs(table):
            visited.add(table)
            path.append(table)

            for neighbor in self.graph.get(table, []):
                if neighbor in tables and neighbor not in visited:
                    dfs(neighbor)

        dfs(tables[0])

        # ensure all requested tables included
        for t in tables:
            if t not in path:
                path.append(t)

        return path

    def get_connections(self):
        return dict(self.graph)
