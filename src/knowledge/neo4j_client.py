"""Neo4j 图数据库客户端——零件替代关系查询"""

from typing import Any
from neo4j import GraphDatabase, Driver
from src.common.config import get_settings


class Neo4jClient:
    """Neo4j 客户端封装"""

    def __init__(self):
        settings = get_settings()
        self._driver: Driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    def close(self):
        self._driver.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ===== 查询方法 =====

    def find_alternatives(self, part_name: str, color: str) -> list[dict]:
        """
        查询零件的替代方案

        Args:
            part_name: 零件名称（如 "3001" 或 "Brick 2x4"）
            color: 颜色

        Returns:
            替代方案列表，按匹配度排序
        """
        query = """
        MATCH (p:Part)-[r:CAN_REPLACE]->(alt:Part)
        WHERE p.name CONTAINS $part_name
          AND (p.color = $color OR alt.color = $color)
        RETURN alt.name AS name, alt.color AS color,
               alt.part_id AS part_id, r.confidence AS confidence
        ORDER BY r.confidence DESC
        LIMIT 5
        """
        with self._driver.session() as session:
            result = session.run(query, part_name=part_name, color=color)
            return [record.data() for record in result]

    def find_by_color_and_size(self, color: str, width: int, length: int) -> list[dict]:
        """按颜色和尺寸模糊查找零件"""
        query = """
        MATCH (p:Part)
        WHERE p.color = $color AND p.width = $width AND p.length = $length
        RETURN p.name AS name, p.color AS color, p.part_id AS part_id
        LIMIT 10
        """
        with self._driver.session() as session:
            result = session.run(query, color=color, width=width, length=length)
            return [record.data() for record in result]

    def get_part_info(self, part_id: str) -> dict | None:
        """获取零件详细信息"""
        query = """
        MATCH (p:Part {part_id: $part_id})
        RETURN p.name AS name, p.color AS color, p.category AS category
        """
        with self._driver.session() as session:
            result = session.run(query, part_id=part_id)
            record = result.single()
            return record.data() if record else None

    # ===== 数据导入 =====

    def init_schema(self):
        """初始化约束和索引"""
        with self._driver.session() as session:
            session.run("CREATE CONSTRAINT part_id IF NOT EXISTS FOR (p:Part) REQUIRE p.part_id IS UNIQUE")
            session.run("CREATE INDEX part_name IF NOT EXISTS FOR (p:Part) ON (p.name)")
            session.run("CREATE INDEX part_color IF NOT EXISTS FOR (p:Part) ON (p.color)")

    def import_parts_from_csv(self, csv_path: str):
        """
        从 CSV 导入零件数据

        CSV 格式：part_id, name, color, category, width, length
        """
        query = """
        LOAD CSV WITH HEADERS FROM $csv_path AS row
        MERGE (p:Part {part_id: row.part_id})
        SET p.name = row.name,
            p.color = row.color,
            p.category = row.category,
            p.width = toInteger(row.width),
            p.length = toInteger(row.length)
        """
        with self._driver.session() as session:
            session.run(query, csv_path=f"file:///{csv_path}")

    def import_alternatives_from_csv(self, csv_path: str):
        """
        从 CSV 导入替代关系

        CSV 格式：part_id_a, part_id_b, confidence, source
        """
        query = """
        LOAD CSV WITH HEADERS FROM $csv_path AS row
        MATCH (a:Part {part_id: row.part_id_a})
        MATCH (b:Part {part_id: row.part_id_b})
        MERGE (a)-[r:CAN_REPLACE]->(b)
        SET r.confidence = toFloat(row.confidence),
            r.source = row.source
        """
        with self._driver.session() as session:
            session.run(query, csv_path=f"file:///{csv_path}")

    def import_part(self, part_id: str, name: str, color: str, **props):
        """导入单个零件"""
        query = """
        MERGE (p:Part {part_id: $part_id})
        SET p.name = $name, p.color = $color
        """
        with self._driver.session() as session:
            session.run(query, part_id=part_id, name=name, color=color, **props)

    def import_alternative(self, part_id_a: str, part_id_b: str, confidence: float, source: str = "manual"):
        """导入单条替代关系"""
        query = """
        MATCH (a:Part {part_id: $part_id_a})
        MATCH (b:Part {part_id: $part_id_b})
        MERGE (a)-[r:CAN_REPLACE]->(b)
        SET r.confidence = $confidence, r.source = $source
        """
        with self._driver.session() as session:
            session.run(query, part_id_a=part_id_a, part_id_b=part_id_b,
                       confidence=confidence, source=source)
