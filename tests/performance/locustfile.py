"""
LEGO-Mate 性能压测脚本

使用方法:
    locust -f tests/performance/locustfile.py \
        --host=http://localhost:8000 \
        --users 100 \
        --spawn-rate 10 \
        --run-time 5m \
        --headless \
        --html=report.html

压测场景:
    - 问候消息 (权重: 30%)
    - 零件替代查询 (权重: 25%)
    - 说明书检索 (权重: 20%)
    - 复杂推理 (权重: 15%)
    - 闲聊 (权重: 10%)
"""

import random
import time
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner


# ===== 压测数据 =====

GREETING_MESSAGES = [
    "你好", "hello", "hi", "嗨", "在吗", "早上好", "下午好", "晚上好",
    "谢谢", "感谢", "拜拜", "再见", "你是谁", "你能做什么",
]

ALTERNATIVE_QUERIES = [
    "红色2x4砖有替代吗",
    "缺了3001怎么办",
    "3002有什么替代",
    "Brick 2x4 有什么替代品",
    "没有红色砖用什么代替",
    "3622能用什么代替",
    "Plate 2x4 有什么替代方案",
    "Slope 45度有什么替代",
]

MANUAL_QUERIES = [
    "第35步怎么拼",
    "第100步是什么",
    "第1步怎么拼",
    "第50步是什么",
    "step 35",
    "怎么拼第20步",
    "第75步怎么拼",
]

COMPLEX_QUERIES = [
    "帮我设计一个乐高城堡",
    "红色2x4砖和蓝色2x3砖有什么区别",
    "这个零件够稳固吗",
    "第35步和第36步之间可以跳过吗",
    "帮我分析一下这个结构",
]

CHAT_MESSAGES = [
    "今天天气怎么样",
    "乐高有多少年历史了",
    "最大的乐高套装是什么",
    "乐高积木是怎么生产的",
    "推荐一个好的乐高套装",
]


# ===== 压测用户 =====

class LegoMateUser(HttpUser):
    """模拟 LEGO-Mate 用户"""

    # 用户思考时间（1-5 秒）
    wait_time = between(1, 5)

    def on_start(self):
        """用户启动时执行"""
        self.conversation_id = None
        # 创建对话
        try:
            response = self.client.post(
                "/api/conversations",
                json={"title": f"LoadTest_{int(time.time())}"},
            )
            if response.status_code == 200:
                data = response.json()
                self.conversation_id = data.get("conversation", {}).get("id")
        except Exception:
            pass

    @task(30)
    def send_greeting(self):
        """发送问候消息（权重 30%）"""
        message = random.choice(GREETING_MESSAGES)
        self._send_chat(message)

    @task(25)
    def query_alternative(self):
        """查询零件替代（权重 25%）"""
        message = random.choice(ALTERNATIVE_QUERIES)
        self._send_chat(message)

    @task(20)
    def query_manual(self):
        """查询说明书（权重 20%）"""
        message = random.choice(MANUAL_QUERIES)
        self._send_chat(message)

    @task(15)
    def send_complex_query(self):
        """复杂推理查询（权重 15%）"""
        message = random.choice(COMPLEX_QUERIES)
        self._send_chat(message)

    @task(10)
    def send_chat(self):
        """闲聊消息（权重 10%）"""
        message = random.choice(CHAT_MESSAGES)
        self._send_chat(message)

    def _send_chat(self, message: str):
        """发送聊天消息"""
        payload = {
            "message": message,
            "set_id": "10295",
        }
        if self.conversation_id:
            payload["conversation_id"] = self.conversation_id

        with self.client.post(
            "/api/chat",
            json=payload,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("response"):
                    response.success()
                else:
                    response.failure("Empty response")
            else:
                response.failure(f"Status {response.status_code}")

    @task(1)
    def health_check(self):
        """健康检查（权重 1%）"""
        self.client.get("/api/health")

    @task(1)
    def get_metrics(self):
        """获取指标（权重 1%）"""
        self.client.get("/metrics")


class StreamingUser(HttpUser):
    """模拟流式聊天用户"""

    wait_time = between(2, 8)

    @task
    def stream_chat(self):
        """测试流式聊天"""
        message = random.choice(GREETING_MESSAGES + ALTERNATIVE_QUERIES)

        with self.client.post(
            "/api/chat/stream",
            json={"message": message, "set_id": "10295"},
            catch_response=True,
            stream=True,
        ) as response:
            if response.status_code == 200:
                # 读取流式响应
                chunks = 0
                for chunk in response.iter_lines():
                    if chunk:
                        chunks += 1
                if chunks > 0:
                    response.success()
                else:
                    response.failure("No stream data")
            else:
                response.failure(f"Status {response.status_code}")


# ===== 压测事件钩子 =====

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """压测开始"""
    print("=" * 60)
    print("LEGO-Mate 性能压测开始")
    print("=" * 60)
    print(f"目标主机: {environment.host}")
    print(f"并发用户: {environment.options.users}")
    print(f"爬升速率: {environment.options.spawn_rate}/s")
    print("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """压测结束"""
    print("=" * 60)
    print("LEGO-Mate 性能压测结束")
    print("=" * 60)

    stats = environment.stats

    print(f"\n总请求数: {stats.total.num_requests}")
    print(f"失败数: {stats.total.num_failures}")
    print(f"平均响应时间: {stats.total.avg_response_time:.0f}ms")
    print(f"P50 响应时间: {stats.total.get_response_time_percentile(0.5):.0f}ms")
    print(f"P95 响应时间: {stats.total.get_response_time_percentile(0.95):.0f}ms")
    print(f"P99 响应时间: {stats.total.get_response_time_percentile(0.99):.0f}ms")
    print(f"最大响应时间: {stats.total.max_response_time:.0f}ms")
    print(f"请求速率: {stats.total.total_rps:.1f} req/s")

    # 性能判定
    p95 = stats.total.get_response_time_percentile(0.95)
    error_rate = stats.total.num_failures / max(1, stats.total.num_requests)

    print("\n" + "=" * 60)
    if p95 < 2000 and error_rate < 0.01:
        print("性能判定: PASS")
    elif p95 < 5000 and error_rate < 0.05:
        print("性能判定: WARNING")
    else:
        print("性能判定: FAIL")
    print("=" * 60)


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, **kwargs):
    """记录每个请求"""
    # 慢请求警告（超过 5 秒）
    if response_time > 5000:
        print(f"[SLOW] {name}: {response_time:.0f}ms")
