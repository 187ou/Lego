"""物理稳定性自动修正器

当验证不通过时，自动修正积木模型。
"""

from typing import Any

from src.builder3d.physics import PhysicsValidator


class AutoFixer:
    def fix(self, bricks: list[dict], issues: list[str], base_plate: dict) -> list[dict]:
        """
        修正积木模型。

        Args:
            bricks: 原始零件列表
            issues: 验证发现的问题
            base_plate: 底板尺寸

        Returns:
            修正后的零件列表
        """
        bricks = [dict(b) for b in bricks]
        validator = PhysicsValidator()

        for issue in issues:
            if "超出底板" in issue:
                bricks = self._fix_out_of_bounds(bricks, base_plate)
            elif "悬空" in issue or "完全悬空" in issue:
                bricks = self._fix_floating(bricks)
            elif "不连通" in issue:
                bricks = self._fix_connectivity(bricks)

        return bricks

    def _fix_out_of_bounds(self, bricks: list[dict], base_plate: dict) -> list[dict]:
        """将越界积木平移到底板内"""
        bw = base_plate.get("width", 16)
        bl = base_plate.get("length", 16)
        for b in bricks:
            pos = b["position"]
            size = b["size"]
            if pos["x"] + size["x"] > bw:
                pos["x"] = max(0, bw - size["x"])
            if pos["z"] + size["z"] > bl:
                pos["z"] = max(0, bl - size["z"])
            if pos["x"] < 0:
                pos["x"] = 0
            if pos["z"] < 0:
                pos["z"] = 0
        return bricks

    def _fix_floating(self, bricks: list[dict]) -> list[dict]:
        """为悬空积木添加支撑"""
        grid = PhysicsValidator()._build_grid(bricks)

        for i, b in enumerate(bricks):
            pos = b["position"]
            size = b["size"]
            if pos["y"] > 0:
                support = PhysicsValidator()._compute_support(grid, pos["x"], pos["y"], pos["z"], size)
                total = size["x"] * size["z"]
                if total > 0 and support / total < 0.5:
                    # 添加支撑积木
                    for dx in range(size["x"]):
                        for dz in range(size["z"]):
                            support_pos = (pos["x"] + dx, pos["y"] - 1, pos["z"] + dz)
                            if support_pos not in grid:
                                bricks.append({
                                    "position": {"x": support_pos[0], "y": support_pos[1], "z": support_pos[2]},
                                    "size": {"x": 1, "y": 1, "z": 1},
                                    "part_id": "3005",
                                    "color": "Gray",
                                })
                                grid[support_pos] = len(bricks) - 1
        return bricks

    def _fix_connectivity(self, bricks: list[dict]) -> list[dict]:
        """添加连接积木使整体连通"""
        grid = PhysicsValidator()._build_grid(bricks)
        bottom = [i for i, b in enumerate(bricks) if b["position"]["y"] == 0]
        if not bottom:
            return bricks

        visited = set(bottom)
        queue = list(bottom)
        while queue:
            idx = queue.pop(0)
            b = bricks[idx]
            neighbors = PhysicsValidator()._find_neighbors(grid, bricks, b["position"], b["size"])
            for n in neighbors:
                if n not in visited:
                    visited.add(n)
                    queue.append(n)

        # 为不连通的积木添加连接
        for i in range(len(bricks)):
            if i not in visited:
                # 找到最近的底层积木
                target = bottom[0]
                target_pos = bricks[target]["position"]
                pos = bricks[i]["position"]
                # 在中间添加连接
                mid_y = max(0, min(pos["y"], target_pos["y"]))
                bricks.append({
                    "position": {"x": pos["x"], "y": mid_y, "z": pos["z"]},
                    "size": {"x": 1, "y": 1, "z": 1},
                    "part_id": "3005",
                    "color": "Gray",
                })
                visited.add(i)

        return bricks
