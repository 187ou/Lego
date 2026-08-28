"""知识图谱增强版测试

测试内容：
1. Schema 增强（物理/几何属性）
2. 多维度替代算法
3. 层次结构（SubAssembly）
4. 图算法推理（约束传播）
"""

import pytest
from src.kg.schema import (
    NodeType, RelationType,
    PartGeometry, PartPhysics, PartCommercial,
    GraphNode, GraphRelation,
    get_part_knowledge, calc_part_compatibility,
    PART_KNOWLEDGE_BASE,
)
from src.kg.graph_store import MockGraphStore
from src.kg.graph_builder import GraphBuilder


# ===== 1. Schema 增强测试 =====

class TestSchemaEnhancement:
    """测试 Schema 增强"""

    def test_part_knowledge_base_exists(self):
        """零件知识库应存在"""
        assert len(PART_KNOWLEDGE_BASE) > 0

    def test_part_has_geometry(self):
        """零件应有几何属性"""
        knowledge = get_part_knowledge("3001")
        assert knowledge is not None
        assert knowledge["geometry"].width == 2
        assert knowledge["geometry"].length == 4
        assert knowledge["geometry"].studs == 8

    def test_part_has_physics(self):
        """零件应有物理属性"""
        knowledge = get_part_knowledge("3001")
        assert knowledge is not None
        assert knowledge["physics"].weight > 0
        assert knowledge["physics"].strength > 0

    def test_part_has_commercial(self):
        """零件应有商业属性"""
        knowledge = get_part_knowledge("3001")
        assert knowledge is not None
        assert knowledge["commercial"].rarity == "common"
        assert knowledge["commercial"].price > 0

    def test_unknown_part_returns_none(self):
        """未知零件应返回 None"""
        knowledge = get_part_knowledge("9999")
        assert knowledge is None

    def test_sub_assembly_node_type_exists(self):
        """SubAssembly 节点类型应存在"""
        assert NodeType.SUB_ASSEMBLY.value == "SubAssembly"

    def test_incompatible_relation_exists(self):
        """INCOMPATIBLE_WITH 关系应存在"""
        assert RelationType.INCOMPATIBLE_WITH.value == "INCOMPATIBLE_WITH"

    def test_depends_on_relation_exists(self):
        """DEPENDS_ON 关系应存在"""
        assert RelationType.DEPENDS_ON.value == "DEPENDS_ON"

    def test_has_part_relation_exists(self):
        """HAS_PART 关系应存在"""
        assert RelationType.HAS_PART.value == "HAS_PART"


# ===== 2. 多维度替代算法测试 =====

class TestCompatibilityAlgorithm:
    """测试多维度兼容性算法"""

    def test_same_part_perfect_score(self):
        """相同零件兼容性应为 1.0"""
        score = calc_part_compatibility("3001", "3001")
        assert score == 1.0

    def test_similar_parts_high_score(self):
        """相似零件兼容性应较高"""
        # 3001 (Brick 2x4) vs 3002 (Brick 2x3) - 同类型，尺寸接近
        score = calc_part_compatibility("3001", "3002")
        assert score > 0.5

    def test_different_type_lower_than_same_type(self):
        """不同类型零件兼容性应低于同类型"""
        # 3001 (Brick 2x4) vs 3002 (Brick 2x3) - 同类型
        same_type_score = calc_part_compatibility("3001", "3002")
        # 3001 (Brick) vs 3020 (Plate) - 不同类型
        diff_type_score = calc_part_compatibility("3001", "3020")

        # 同类型应高于不同类型
        assert same_type_score > diff_type_score

    def test_unknown_part_zero_score(self):
        """未知零件兼容性应为 0"""
        score = calc_part_compatibility("3001", "9999")
        assert score == 0.0

    def test_symmetry(self):
        """兼容性应是对称的"""
        score_ab = calc_part_compatibility("3001", "3002")
        score_ba = calc_part_compatibility("3002", "3001")
        assert score_ab == score_ba

    def test_score_range(self):
        """兼容性得分应在 0-1 之间"""
        for part_a in ["3001", "3002", "3003", "3020", "3069"]:
            for part_b in ["3001", "3002", "3003", "3020", "3069"]:
                score = calc_part_compatibility(part_a, part_b)
                assert 0.0 <= score <= 1.0


# ===== 3. 层次结构测试 =====

class TestSubAssembly:
    """测试子装配层次结构"""

    def test_create_sub_assembly(self):
        """应能创建子装配"""
        store = MockGraphStore()
        builder = GraphBuilder(store)

        # 创建零件
        for pid in ["3001", "3002", "3003"]:
            node = GraphNode(
                node_type=NodeType.PART,
                node_id=f"part_{pid}",
                name=f"Part {pid}",
            )
            store.create_node(node)

        # 创建子装配
        builder.create_sub_assembly(
            assembly_id="test_assembly",
            name="测试子装配",
            set_id="10295",
            part_ids=["3001", "3002", "3003"],
        )

        # 验证子装配节点存在
        assembly = store.get_node("assembly_test_assembly")
        assert assembly is not None
        assert assembly.name == "测试子装配"

    def test_get_assembly_parts(self):
        """应能获取子装配的零件"""
        store = MockGraphStore()
        builder = GraphBuilder(store)

        # 创建零件
        for pid in ["3001", "3002"]:
            node = GraphNode(
                node_type=NodeType.PART,
                node_id=f"part_{pid}",
                name=f"Part {pid}",
            )
            store.create_node(node)

        # 创建子装配
        builder.create_sub_assembly(
            assembly_id="asm1",
            name="装配1",
            set_id="10295",
            part_ids=["3001", "3002"],
        )

        # 获取零件
        parts = store.get_assembly_parts("assembly_asm1")
        assert len(parts) == 2

    def test_get_sub_assemblies(self):
        """应能获取套装的子装配"""
        store = MockGraphStore()
        builder = GraphBuilder(store)

        # 创建套装
        set_node = GraphNode(
            node_type=NodeType.SET,
            node_id="set_10295",
            name="Set 10295",
        )
        store.create_node(set_node)

        # 创建零件
        for pid in ["3001", "3002"]:
            node = GraphNode(
                node_type=NodeType.PART,
                node_id=f"part_{pid}",
                name=f"Part {pid}",
            )
            store.create_node(node)

        # 创建子装配
        builder.create_sub_assembly(
            assembly_id="asm1",
            name="装配1",
            set_id="10295",
            part_ids=["3001", "3002"],
        )

        # 获取子装配
        assemblies = store.get_sub_assemblies("10295")
        assert len(assemblies) >= 1


# ===== 4. 不兼容和依赖关系测试 =====

class TestIncompatibleAndDependency:
    """测试不兼容和依赖关系"""

    def test_add_incompatible_relation(self):
        """应能添加不兼容关系"""
        store = MockGraphStore()
        builder = GraphBuilder(store)

        # 创建零件
        for pid in ["3001", "3020"]:
            node = GraphNode(
                node_type=NodeType.PART,
                node_id=f"part_{pid}",
                name=f"Part {pid}",
            )
            store.create_node(node)

        # 添加不兼容关系
        builder.add_part_incompatible("3001", "3020")

        # 验证
        incompat = store.find_incompatible_parts("3001")
        assert len(incompat) == 1
        assert incompat[0]["part_id"] == "3020"

    def test_add_dependency_relation(self):
        """应能添加依赖关系"""
        store = MockGraphStore()
        builder = GraphBuilder(store)

        # 创建零件
        for pid in ["3001", "3002"]:
            node = GraphNode(
                node_type=NodeType.PART,
                node_id=f"part_{pid}",
                name=f"Part {pid}",
            )
            store.create_node(node)

        # 添加依赖关系
        builder.add_part_dependency("3001", "3002")

        # 验证
        deps = store.find_dependent_parts("3001")
        assert len(deps) == 1
        assert deps[0]["part_id"] == "3002"


# ===== 5. 增强替代查询测试 =====

class TestEnhancedAlternatives:
    """测试增强版替代查询"""

    def test_alternatives_sorted_by_score(self):
        """替代结果应按得分排序"""
        store = MockGraphStore()
        builder = GraphBuilder(store)

        # 创建零件
        for pid in ["3001", "3002", "3003", "3004", "3005"]:
            node = GraphNode(
                node_type=NodeType.PART,
                node_id=f"part_{pid}",
                name=f"Part {pid}",
            )
            store.create_node(node)

        # 自动构建替代关系
        from src.kg.graph_builder import _auto_build_alternatives
        stats = {"nodes": 0, "relations": 0}
        _auto_build_alternatives(builder, stats)

        # 查询替代
        alts = store.find_alternatives("3001", limit=3)

        # 验证按得分排序
        if len(alts) >= 2:
            assert alts[0]["score"] >= alts[1]["score"]

    def test_alternatives_include_compatibility(self):
        """替代结果应包含兼容性得分"""
        store = MockGraphStore()
        builder = GraphBuilder(store)

        # 创建零件
        for pid in ["3001", "3002"]:
            node = GraphNode(
                node_type=NodeType.PART,
                node_id=f"part_{pid}",
                name=f"Part {pid}",
            )
            store.create_node(node)

        # 自动构建替代关系
        from src.kg.graph_builder import _auto_build_alternatives
        stats = {"nodes": 0, "relations": 0}
        _auto_build_alternatives(builder, stats)

        # 查询替代
        alts = store.find_alternatives("3001", limit=3)

        # 验证包含兼容性
        for alt in alts:
            assert "compatibility" in alt
            assert "score" in alt


# ===== 6. 图算法推理测试 =====

class TestGraphReasoning:
    """测试图算法推理"""

    def _create_test_store(self):
        """创建测试用图谱"""
        store = MockGraphStore()

        # 创建套装
        set_node = GraphNode(
            node_type=NodeType.SET,
            node_id="set_10295",
            name="Set 10295",
        )
        store.create_node(set_node)

        # 创建零件
        for pid in ["3001", "3002", "3003", "3004", "3005"]:
            node = GraphNode(
                node_type=NodeType.PART,
                node_id=f"part_{pid}",
                name=f"Part {pid}",
            )
            store.create_node(node)

        # 创建步骤
        for step_num in range(1, 6):
            step_node = GraphNode(
                node_type=NodeType.STEP,
                node_id=f"set_10295_step_{step_num}",
                name=f"步骤 {step_num}",
                properties={"step_number": step_num, "set_id": "10295"},
            )
            store.create_node(step_node)

            # 步骤使用零件
            uses_rel = GraphRelation(
                relation_type=RelationType.USES,
                source_id=f"set_10295_step_{step_num}",
                target_id=f"part_3001",
            )
            store.create_relation(uses_rel)

        # 自动构建替代关系
        builder = GraphBuilder(store)
        from src.kg.graph_builder import _auto_build_alternatives
        stats = {"nodes": 0, "relations": 0}
        _auto_build_alternatives(builder, stats)

        return store

    def test_constraint_reasoning_finds_alternatives(self):
        """约束推理应找到替代方案"""
        from src.kg.graph_reasoner import GraphReasoner

        store = self._create_test_store()
        mock_llm = MagicMock()

        reasoner = GraphReasoner(llm=mock_llm, retriever=MagicMock())
        reasoner.retriever.store = store
        reasoner.retriever.find_part_alternatives = store.find_alternatives
        reasoner.retriever.get_part_info = store.get_node

        result = reasoner.reason_constraint(
            query="缺了3001怎么办",
            has_parts=["3002"],
            missing_parts=["3001"],
        )

        assert "conclusion" in result
        assert "recommendations" in result

    def test_constraint_filters_incompatible(self):
        """约束推理应过滤不兼容零件"""
        from src.kg.graph_reasoner import GraphReasoner

        store = self._create_test_store()

        # 添加不兼容关系
        builder = GraphBuilder(store)
        builder.add_part_incompatible("3001", "3005")

        mock_llm = MagicMock()
        reasoner = GraphReasoner(llm=mock_llm, retriever=MagicMock())
        reasoner.retriever.store = store
        reasoner.retriever.find_part_alternatives = store.find_alternatives
        reasoner.retriever.get_part_info = store.get_node

        result = reasoner.reason_constraint(
            query="缺了3001",
            has_parts=["3005"],
            missing_parts=["3001"],
        )

        # 验证不兼容零件被过滤
        for rec in result.get("recommendations", []):
            for alt in rec.get("alternatives", []):
                assert alt["part_id"] != "3005"

    def test_chain_reasoning_analyzes_steps(self):
        """链式推理应分析步骤"""
        from src.kg.graph_reasoner import GraphReasoner

        store = self._create_test_store()
        mock_llm = MagicMock()

        reasoner = GraphReasoner(llm=mock_llm, retriever=MagicMock())
        reasoner.retriever.store = store
        reasoner.retriever.get_step_info = lambda set_id, step_num: {
            "found": True,
            "step": {"step_number": step_num, "description": f"步骤 {step_num}"},
            "parts": [{"part_id": "3001", "name": "Part 3001"}],
        }
        reasoner.retriever.find_path = lambda s, t, max_depth: []

        result = reasoner.reason_chain(
            query="第1步和第2步之间可以跳过吗",
        )

        assert "conclusion" in result
        assert "reasoning_chain" in result

    def test_stability_reasoning_analyzes_part(self):
        """稳定性推理应分析零件"""
        from src.kg.graph_reasoner import GraphReasoner

        store = self._create_test_store()
        mock_llm = MagicMock()

        reasoner = GraphReasoner(llm=mock_llm, retriever=MagicMock())
        reasoner.retriever.store = store
        reasoner.retriever.get_part_info = lambda pid: {
            "found": True,
            "part": {"part_id": pid, "name": f"Part {pid}"},
        }

        result = reasoner.reason_stability(
            query="3001够稳固吗",
        )

        assert "conclusion" in result
        assert "analysis" in result

        # 验证包含稳定性评分
        for a in result["analysis"]:
            if a.get("found"):
                assert "stability_score" in a
                assert "assessment" in a


# ===== MagicMock 导入 =====
from unittest.mock import MagicMock
