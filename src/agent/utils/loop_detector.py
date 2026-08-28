"""循环检测器 - 防止 Agent 间无限循环"""


class LoopDetector:
    """循环检测器 - 防止 Agent 间无限循环

    用法:
        detector = LoopDetector(max_iterations=5, max_tool_calls=10)
        if detector.check_loop("vision", "parse_lego_image"):
            # 检测到循环，执行降级
            pass
    """

    def __init__(self, max_iterations: int = 5, max_tool_calls: int = 10):
        self.max_iterations = max_iterations
        self.max_tool_calls = max_tool_calls
        self.iteration_count = 0
        self.tool_call_count = 0
        self._call_history: list[str] = []

    def check_loop(self, agent_name: str, tool_name: str = None) -> bool:
        """检测是否进入循环

        Returns:
            True = 检测到循环
            False = 正常
        """
        self.iteration_count += 1

        if tool_name:
            self.tool_call_count += 1
            call_key = f"{agent_name}:{tool_name}"
            self._call_history.append(call_key)

            # 检测重复调用（同一 Agent 同一工具连续调用 3 次）
            if len(self._call_history) >= 3:
                last_3 = self._call_history[-3:]
                if len(set(last_3)) == 1:
                    return True  # 检测到循环

        # 超过最大迭代次数
        if self.iteration_count >= self.max_iterations:
            return True

        # 超过最大工具调用次数
        if self.tool_call_count >= self.max_tool_calls:
            return True

        return False

    def reset(self):
        """重置检测器"""
        self.iteration_count = 0
        self.tool_call_count = 0
        self._call_history.clear()
