import json
import time
from datetime import datetime
from google.adk.plugins import base_plugin
from google.genai import types

class AuditLogPlugin(base_plugin.BasePlugin):
    """
    AuditLogPlugin: Ghi nhật ký chi tiết cho mọi tương tác.
    
    Tại sao cần: Để tuân thủ (Compliance), hậu kiểm (Forensics) và debug. 
    Chúng ta cần biết cuộc tấn công nào đã bị chặn bởi lớp bảo vệ nào.
    """
    def __init__(self):
        super().__init__(name="audit_log")
        self.logs = []
        # Monitoring metrics
        self.total_requests = 0
        self.total_blocked = 0
        self.alert_threshold = 0.3 # Cảnh báo nếu >30% bị block

    def _extract_text(self, content) -> str:
        text = ""
        # Handle both types.Content and llm_response objects
        actual_content = content.content if hasattr(content, 'content') else content
        if actual_content and actual_content.parts:
            for part in actual_content.parts:
                if hasattr(part, 'text') and part.text:
                    text += part.text
        return text

    async def on_user_message_callback(self, *, invocation_context, user_message):
        # Tạo bản ghi mới cho request này
        request_id = f"req_{int(time.time() * 1000)}"
        setattr(invocation_context, "request_id", request_id)
        setattr(invocation_context, "start_time", time.time())
        
        self.total_requests += 1
        
        log_entry = {
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
            "input": self._extract_text(user_message),
            "output": None,
            "latency_ms": None,
            "blocked": False,
            "block_layer": None
        }
        self.logs.append(log_entry)
        
        # Plugin này không bao giờ chặn, chỉ ghi log
        return None

    async def after_model_callback(self, *, callback_context, llm_response):
        request_id = getattr(callback_context, "request_id", None)
        start_time = getattr(callback_context, "start_time", None)
        
        output_text = self._extract_text(llm_response)
        
        # Tìm lại bản ghi để cập nhật output và latency
        for entry in self.logs:
            if entry["request_id"] == request_id:
                entry["output"] = output_text
                if start_time:
                    entry["latency_ms"] = int((time.time() - start_time) * 1000)
                
                # Kiểm tra xem có phải nội dung là thông báo bị block không
                if any(msg in output_text for msg in ["blocked", "apologize", "cannot", "[REDACTED]"]):
                    entry["blocked"] = True
                    self.total_blocked += 1
                break
        
        # Kiểm tra ngưỡng cảnh báo (Monitoring & Alert)
        self._check_alerts()
        
        return llm_response

    def _check_alerts(self):
        if self.total_requests > 5: # Chỉ check sau khi có đủ dữ liệu mẫu
            block_rate = self.total_blocked / self.total_requests
            if block_rate > self.alert_threshold:
                print(f"\n[ALERT] High Block Rate detected: {block_rate:.1%}")
                print(f"[ALERT] Possible attack in progress or guardrails are too strict!")

    def export_json(self, filepath="security_audit.json"):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({
                "summary": {
                    "total_requests": self.total_requests,
                    "total_blocked": self.total_blocked,
                    "block_rate": self.total_blocked / self.total_requests if self.total_requests > 0 else 0
                },
                "details": self.logs
            }, f, indent=2, ensure_ascii=False)
        print(f"\nAudit logs exported to {filepath}")

if __name__ == "__main__":
    # Test nhanh plugin
    pass
