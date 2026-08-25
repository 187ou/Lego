"""图谱存储层

基于 Neo4j 的多模态知识图谱存储。
支持节点的创建、关系的建立、多跳查询等。

如果 Neo4j 不可用，自动降级到内存存储（MockGraphStore）。
"""

import json
from typing import Optional
from src.kg.schema import (
    NodeType,
    RelationType,
    GraphNode,
    GraphRelation,
    RELATION_CONSTRAINTS,
    CYPHER_TEMPLATES,
)


class GraphStore:
    """图谱存储基类"""

    def create_node(self, node: GraphNode) -> bool:
        raise NotImplementedError

    def create_relation(self, relation: GraphRelation) -> bool:
        raise NotImplementedError

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        raise NotImplementedError

    def get_neighbors(self, node_id: str, limit: int = 10) -> list[dict]:
        raise NotImplementedError

    def find_alternatives(self, part_id: str, limit: int = 5) -> list[dict]:
        raise NotImplementedError

    def get_stats(self) -> dict:
        raise NotImplementedError

    def clear_all(self):
        raise NotImplementedError


class Neo4jGraphStore(GraphStore):
    """Neo4j 图谱存储"""

    def __init__(self):
        self._client = None
        self._available = False
        self._connect()

    def _connect(self):
        """连接 Neo4j"""
        try:
            from src.knowledge.neo4j_client import Neo4jClient
            self._client = Neo4jClient()
            self._available = True
            print("[OK] Neo4j 连接成功")
        except Exception as e:
            print(f"[WARN] Neo4j 连接失败: {e}，将使用内存存储")
            self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    def create_node(self, node: GraphNode) -> bool:
        """创建节点"""
        if not self._available:
            return False

        try:
            with self._client as client:
                # 构建属性
                props = {
                    "node_id": node.node_id,
                    "name": node.name,
                    "node_type": node.node_type.value,
                    **node.properties,
                }
                if node.text_description:
                    props["text_description"] = node.text_description
                if node.image_url:
                    props["image_url"] = node.image_url

                # 创建节点
                query = f"""
                MERGE (n:{node.node_type.value} {{node_id: $node_id}})
                SET n += $props
                """
                client._driver.session().run(query, node_id=node.node_id, props=props)
                return True
        except Exception as e:
            print(f"[ERROR] 创建节点失败: {e}")
            return False

    def create_relation(self, relation: GraphRelation) -> bool:
        """创建关系"""
        if not self._available:
            return False

        try:
            with self._client as client:
                query = f"""
                MATCH (a {{node_id: $source_id}}), (b {{node_id: $target_id}})
                MERGE (a)-[r:{relation.relation_type.value}]->(b)
                SET r.confidence = $confidence
                """
                client._driver.session().run(
                    query,
                    source_id=relation.source_id,
                    target_id=relation.target_id,
                    confidence=relation.confidence,
                )
                return True
        except Exception as e:
            print(f"[ERROR] 创建关系失败: {e}")
            return False

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """获取节点"""
        if not self._available:
            return None

        try:
            with self._client as client:
                query = "MATCH (n {node_id: $node_id}) RETURN n"
                result = client._driver.session().run(query, node_id=node_id)
                record = result.single()
                if record:
                    node_data = dict(record["n"])
                    return GraphNode(
                        node_type=NodeType(node_data.get("node_type", "PART")),
                        node_id=node_data["node_id"],
                        name=node_data.get("name", ""),
                        properties=node_data,
                    )
                return None
        except Exception as e:
            print(f"[ERROR] 获取节点失败: {e}")
            return None

    def get_neighbors(self, node_id: str, limit: int = 10) -> list[dict]:
        """获取邻居节点"""
        if not self._available:
            return []

        try:
            with self._client as client:
                query = """
                MATCH (n {node_id: $node_id})-[r]-(m)
                RETURN type(r) as relation, m.node_id as node_id,
                       m.name as name, m.node_type as node_type
                LIMIT $limit
                """
                result = client._driver.session().run(query, node_id=node_id, limit=limit)
                return [dict(record.data()) for record in result]
        except Exception as e:
            print(f"[ERROR] 获取邻居失败: {e}")
            return []

    def find_alternatives(self, part_id: str, limit: int = 5) -> list[dict]:
        """查找替代零件"""
        if not self._available:
            return []

        try:
            with self._client as client:
                query = """
                MATCH (p {node_id: $part_id})-[r:CAN_REPLACE*1..3]-(alt)
                WHERE alt.node_id <> $part_id
                RETURN DISTINCT alt.node_id as part_id, alt.name as name,
                       length(shortestPath((p)-[:CAN_REPLACE*]-(alt))) as distance
                ORDER BY distance
                LIMIT $limit
                """
                result = client._driver.session().run(query, part_id=part_id, limit=limit)
                return [dict(record.data()) for record in result]
        except Exception as e:
            print(f"[ERROR] 查找替代失败: {e}")
            return []

    def get_stats(self) -> dict:
        """获取统计信息"""
        if not self._available:
            return {"available": False}

        try:
            with self._client as client:
                # 节点统计
                node_query = "MATCH (n) RETURN labels(n)[0] as label, count(n) as count"
                node_result = client._driver.session().run(node_query)
                nodes = {record["label"]: record["count"] for record in node_result}

                # 关系统计
                rel_query = "MATCH ()-[r]->() RETURN type(r) as type, count(r) as count"
                rel_result = client._driver.session().run(rel_query)
                rels = {record["type"]: record["count"] for record in rel_result}

                return {
                    "available": True,
                    "nodes": nodes,
                    "relationships": rels,
                    "total_nodes": sum(nodes.values()),
                    "total_relationships": sum(rels.values()),
                }
        except Exception as e:
            return {"available": False, "error": str(e)}

    def clear_all(self):
        """清除所有数据"""
        if not self._available:
            return

        try:
            with self._client as client:
                client._driver.session().run("MATCH (n) DETACH DELETE n")
        except Exception as e:
            print(f"[ERROR] 清除失败: {e}")


class MockGraphStore(GraphStore):
    """内存图谱存储（Neo4j 不可用时的降级方案）"""

    def __init__(self):
        self._nodes: dict[str, GraphNode] = {}
        self._relations: list[GraphRelation] = []
        print("[INFO] 使用内存图谱存储（Mock）")

    def create_node(self, node: GraphNode) -> bool:
        self._nodes[node.node_id] = node
        return True

    def create_relation(self, relation: GraphRelation) -> bool:
        self._relations.append(relation)
        return True

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        return self._nodes.get(node_id)

    def get_neighbors(self, node_id: str, limit: int = 10) -> list[dict]:
        results = []
        for rel in self._relations:
            if rel.source_id == node_id:
                target = self._nodes.get(rel.target_id)
                if target:
                    results.append({
                        "relation": rel.relation_type.value,
                        "node_id": target.node_id,
                        "name": target.name,
                        "node_type": target.node_type.value,
                    })
            elif rel.target_id == node_id:
                source = self._nodes.get(rel.source_id)
                if source:
                    results.append({
                        "relation": rel.relation_type.value,
                        "node_id": source.node_id,
                        "name": source.name,
                        "node_type": source.node_type.value,
                    })
        return results[:limit]

    def find_alternatives(self, part_id: str, limit: int = 5, max_depth: int = 3) -> list[dict]:
        """
        查找替代零件（BFS，带深度限制）。

        Args:
            part_id: 零件编号
            limit: 返回数量
            max_depth: 最大搜索深度（跳数）
        """
        node_id = f"part_{part_id}"
        visited = {node_id}
        queue = [(node_id, 0)]
        results = []

        while queue and len(results) < limit:
            current_id, distance = queue.pop(0)

            # 深度限制
            if distance >= max_depth:
                continue

            for rel in self._relations:
                if rel.relation_type == RelationType.CAN_REPLACE:
                    next_id = None
                    if rel.source_id == current_id and rel.target_id not in visited:
                        next_id = rel.target_id
                    elif rel.target_id == current_id and rel.source_id not in visited:
                        next_id = rel.source_id

                    if next_id:
                        visited.add(next_id)
                        node = self._nodes.get(next_id)
                        if node:
                            results.append({
                                "part_id": node.node_id.replace("part_", ""),
                                "name": node.name,
                                "distance": distance + 1,
                            })
                        queue.append((next_id, distance + 1))

        return results[:limit]

    def get_stats(self) -> dict:
        node_types = {}
        for node in self._nodes.values():
            t = node.node_type.value
            node_types[t] = node_types.get(t, 0) + 1

        rel_types = {}
        for rel in self._relations:
            t = rel.relation_type.value
            rel_types[t] = rel_types.get(t, 0) + 1

        return {
            "available": True,
            "mode": "memory",
            "nodes": node_types,
            "relationships": rel_types,
            "total_nodes": len(self._nodes),
            "total_relationships": len(self._relations),
        }

    def clear_all(self):
        self._nodes.clear()
        self._relations.clear()


# 全局单例
_store: Optional[GraphStore] = None


def get_graph_store() -> GraphStore:
    """获取图谱存储单例"""
    global _store
    if _store is None:
        # 尝试 Neo4j，失败则使用内存存储
        neo4j_store = Neo4jGraphStore()
        if neo4j_store.is_available:
            _store = neo4j_store
        else:
            _store = MockGraphStore()
    return _store
