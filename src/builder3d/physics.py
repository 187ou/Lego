"""物理稳定性验证器

检查积木模型是否符合物理规则：
1. 重力支撑：非底层积木下方必须有支撑
2. 悬空检测：无支撑面积 <= 50%
3. 边界检测：不超出底板
4. 连通性：所有积木与底板相连
"""

from typing import Any


class PhysicsValidator:
    def validate(self, bricks: list[dict], base_plate: dict) -> dict:
        """
        Args:
            bricks: [{"position": {x,y,z}, "size": {x,y,z}}, ...]
            base_plate: {"width": N, "length": M}

        Returns:
            {"stable": bool, "issues": [...], "suggestions": [...]}
        """
        issues = []
        suggestions = []

        if not bricks:
            issues.append("没有积木")
            return {"stable": False, "issues": issues, "suggestions": suggestions}

        # 构建占用网格
        grid = self._build_grid(bricks)

        for i, b in enumerate(bricks):
            pos = b["position"]
            size = b["size"]
            x, y, z = pos["x"], pos["y"], pos["z"]

            # 1. 边界检测
            bp_w = base_plate.get("width", 16)
            bp_l = base_plate.get("length", 16)
            if x < 0 or z < 0 or x + size["x"] > bp_w or z + size["z"] > bp_l:
                issues.append(f"brick[{i}]({x},{y},{z}) 超出底板范围")
                suggestions.append(f"将 brick[{i}] 移到底板内")

            # 2. 重力支撑
            if y > 0:
                support = self._compute_support(grid, x, y, z, size)
                total_area = size["x"] * size["z"]
                unsupported = 1.0 - (support / total_area) if total_area > 0 else 1.0

                if unsupported > 0.5:
                    issues.append(f"brick[{i}]({x},{y},{z}) 悬空 {unsupported:.0%}")
                    suggestions.append(f"在 brick[{i}] 下方添加支撑")

            # 3. 悬空检测（下方完全无支撑）
            if y > 0 and self._has_no_support(grid, x, y, z, size):
                issues.append(f"brick[{i}]({x},{y},{z}) 完全悬空")

        # 4. 连通性
        if not self._check_connectivity(grid, bricks):
            issues.append("存在不连通的积木")
            suggestions.append("添加连接积木使整体连通")

        return {
            "stable": len(issues) == 0,
            "issues": issues,
            "suggestions": suggestions,
        }

    def _build_grid(self, bricks: list[dict]) -> dict:
        """构建 (x,y,z) -> brick_index 的占用网格"""
        grid = {}
        for i, b in enumerate(bricks):
            pos = b["position"]
            size = b["size"]
            for dx in range(size["x"]):
                for dy in range(size["y"]):
                    for dz in range(size["z"]):
                        key = (pos["x"] + dx, pos["y"] + dy, pos["z"] + dz)
                        grid[key] = i
        return grid

    def _compute_support(self, grid: dict, x: int, y: int, z: int, size: dict) -> int:
        """计算下方支撑面积"""
        support = 0
        for dx in range(size["x"]):
            for dz in range(size["z"]):
                if (x + dx, y - 1, z + dz) in grid:
                    support += 1
        return support

    def _has_no_support(self, grid: dict, x: int, y: int, z: int, size: dict) -> bool:
        """下方是否完全无支撑"""
        return self._compute_support(grid, x, y, z, size) == 0

    def _check_connectivity(self, grid: dict, bricks: list[dict]) -> bool:
        """BFS 检查所有积木是否与底板连通"""
        if not bricks:
            return True

        # 找到底层积木作为 BFS 起点
        bottom_bricks = [i for i, b in enumerate(bricks) if b["position"]["y"] == 0]
        if not bottom_bricks:
            # 没有底层积木，检查是否所有积木悬空
            return False

        # BFS
        visited = set(bottom_bricks)
        queue = list(bottom_bricks)

        while queue:
            idx = queue.pop(0)
            b = bricks[idx]
            pos = b["position"]
            size = b["size"]

            # 检查六个方向的邻居
            neighbors = self._find_neighbors(grid, bricks, pos, size)
            for n in neighbors:
                if n not in visited:
                    visited.add(n)
                    queue.append(n)

        return len(visited) == len(bricks)

    def _find_neighbors(self, grid: dict, bricks: list[dict], pos: dict, size: dict) -> list[int]:
        """找到相邻的积木索引"""
        neighbors = []
        for i, other in enumerate(bricks):
            if other["position"] == pos:
                continue
            op = other["position"]
            os = other["size"]
            # 检查是否相邻（面接触）
            if self._is_adjacent(pos, size, op, os):
                neighbors.append(i)
        return neighbors

    @staticmethod
    def _is_adjacent(pos1: dict, size1: dict, pos2: dict, size2: dict) -> bool:
        """两个积木是否面相邻"""
        # X 方向
        if (pos1["x"] + size1["x"] == pos2["x"] or pos2["x"] + size2["x"] == pos1["x"]):
            if PhysicsValidator._overlap(pos1["y"], size1["y"], pos2["y"], size2["y"]):
                if PhysicsValidator._overlap(pos1["z"], size1["z"], pos2["z"], size2["z"]):
                    return True
        # Y 方向
        if (pos1["y"] + size1["y"] == pos2["y"] or pos2["y"] + size2["y"] == pos1["y"]):
            if PhysicsValidator._overlap(pos1["x"], size1["x"], pos2["x"], size2["x"]):
                if PhysicsValidator._overlap(pos1["z"], size1["z"], pos2["z"], size2["z"]):
                    return True
        # Z 方向
        if (pos1["z"] + size1["z"] == pos2["z"] or pos2["z"] + size2["z"] == pos1["z"]):
            if PhysicsValidator._overlap(pos1["x"], size1["x"], pos2["x"], size2["x"]):
                if PhysicsValidator._overlap(pos1["y"], size1["y"], pos2["y"], size2["y"]):
                    return True
        return False

    @staticmethod
    def _overlap(a_start: int, a_size: int, b_start: int, b_size: int) -> bool:
        return a_start < b_start + b_size and b_start < a_start + a_size
