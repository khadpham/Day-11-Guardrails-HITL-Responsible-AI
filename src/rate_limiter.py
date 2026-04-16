import time
from collections import defaultdict, deque
from google.adk.plugins import base_plugin
from google.genai import types

class RateLimitPlugin(base_plugin.BasePlugin):
    """
    RateLimitPlugin: Chặn người dùng gửi quá nhiều yêu cầu trong một khoảng thời gian.
    
    Tại sao cần: Ngăn chặn tấn công Brute-force, từ chối dịch vụ (DoS) và tiết kiệm chi phí API.
    Nó bắt được các cuộc tấn công spam mà các lớp bảo vệ nội dung khác không quan tâm.
    """
    def __init__(self, max_requests=10, window_seconds=60):
        super().__init__(name="rate_limiter")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # Lưu trữ timestamp của các request theo user_id
        self.user_windows = defaultdict(deque)
        self.blocked_count = 0

    async def on_user_message_callback(self, *, invocation_context, user_message):
        # Lấy user_id từ context, mặc định là "anonymous" nếu không có
        user_id = getattr(invocation_context, "user_id", "anonymous")
        now = time.time()
        window = self.user_windows[user_id]

        # Xóa các timestamp đã hết hạn (nằm ngoài cửa sổ thời gian)
        while window and window[0] < now - self.window_seconds:
            window.popleft()

        # Kiểm tra nếu vượt quá giới hạn
        if len(window) >= self.max_requests:
            self.blocked_count += 1
            wait_time = int(self.window_seconds - (now - window[0]))
            return types.Content(
                role="model",
                parts=[types.Part.from_text(
                    text=f"Rate limit exceeded. Please wait {wait_time} seconds before trying again."
                )]
            )

        # Thêm timestamp hiện tại và cho phép request đi tiếp
        window.append(now)
        return None

if __name__ == "__main__":
    # Test nhanh plugin
    import asyncio
    
    async def test_rate_limiter():
        plugin = RateLimitPlugin(max_requests=2, window_seconds=5)
        ctx = type('obj', (object,), {'user_id': 'user1'})
        msg = types.Content(parts=[types.Part.from_text(text="hello")])
        
        print("Request 1:", await plugin.on_user_message_callback(invocation_context=ctx, user_message=msg)) # None
        print("Request 2:", await plugin.on_user_message_callback(invocation_context=ctx, user_message=msg)) # None
        print("Request 3 (Should block):", await plugin.on_user_message_callback(invocation_context=ctx, user_message=msg)) # Blocked
        
    asyncio.run(test_rate_limiter())
