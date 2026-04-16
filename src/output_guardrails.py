import re
from google.adk.plugins import base_plugin
from google.genai import types

class OutputGuardrailPlugin(base_plugin.BasePlugin):
    """
    OutputGuardrailPlugin: Quét và làm sạch dữ liệu đầu ra của model.
    
    Tại sao cần: Ngăn chặn việc vô tình rò rỉ dữ liệu khách hàng (PII) hoặc 
    các bí mật hệ thống (API Key, Password) mà model có thể trích xuất được từ training data hoặc prompt.
    """
    def __init__(self):
        super().__init__(name="output_guardrail")
        self.redacted_count = 0
        
        # Các mẫu dữ liệu nhạy cảm
        self.PII_PATTERNS = {
            "Phone": r"\b(?:0|84|\+84)?\d{9,10}\b",
            "Email": r"[\w.-]+@[\w.-]+\.[a-zA-Z]{2,}",
            "National ID": r"\b\d{9}\b|\b\d{12}\b",
            "API Key": r"sk-[a-zA-Z0-9-]{10,}",
            "Password": r"password\s*[:=]\s*\S+"
        }

    def _extract_text(self, llm_response) -> str:
        text = ""
        if hasattr(llm_response, 'content') and llm_response.content:
            for part in llm_response.content.parts:
                if hasattr(part, 'text') and part.text:
                    text += part.text
        return text

    async def after_model_callback(self, *, callback_context, llm_response):
        original_text = self._extract_text(llm_response)
        if not original_text:
            return llm_response

        cleaned_text = original_text
        found_sensitive = False

        # Quét và thay thế bằng [REDACTED]
        for name, pattern in self.PII_PATTERNS.items():
            matches = re.findall(pattern, cleaned_text, re.IGNORECASE)
            if matches:
                found_sensitive = True
                for match in matches:
                    cleaned_text = cleaned_text.replace(match, f"[REDACTED_{name.upper()}]")

        if found_sensitive:
            self.redacted_count += 1
            # Cập nhật lại nội dung đã làm sạch vào response
            llm_response.content = types.Content(
                role="model",
                parts=[types.Part.from_text(text=cleaned_text)]
            )

        return llm_response

if __name__ == "__main__":
    # Test nhanh
    import asyncio
    
    class MockResponse:
        def __init__(self, text):
            self.content = types.Content(parts=[types.Part.from_text(text=text)])

    async def test_output_guards():
        plugin = OutputGuardrailPlugin()
        resp = MockResponse("Khách hàng Nguyễn Văn A có số điện thoại 0901234567 và email a@gmail.com. Password là: 123456.")
        
        result = await plugin.after_model_callback(callback_context=None, llm_response=resp)
        print("Original:", "Khách hàng Nguyễn Văn A có số điện thoại 0901234567 và email a@gmail.com. Password là: 123456.")
        print("Cleaned:", result.content.parts[0].text)

    asyncio.run(test_output_guards())
