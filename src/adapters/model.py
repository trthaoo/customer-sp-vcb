from typing import List, Dict, Any, Optional
import os
import time
import httpx
from src import config

class ModelAdapter:
    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None
    ):
        self._provider = provider
        self._api_key = api_key
        self._base_url = base_url
        self._model_name = model_name

    @property
    def provider(self) -> str:
        raw = self._provider or os.getenv("MODEL_PROVIDER", config.MODEL_PROVIDER or "")
        raw = (raw or "").lower().strip()
        if "openai" in raw:
            return "openai"
        if "gemini" in raw:
            return "gemini"
        return raw

    @property
    def api_key(self) -> str:
        if self._api_key is not None:
            return self._api_key
        return os.getenv("MODEL_API_KEY", config.MODEL_API_KEY or "").strip()

    @property
    def base_url(self) -> str:
        if self._base_url is not None:
            return self._base_url
        return os.getenv("MODEL_BASE_URL", config.MODEL_BASE_URL or "").strip()

    @property
    def model_name(self) -> str:
        if self._model_name is not None:
            return self._model_name
        return os.getenv("MODEL_NAME", config.MODEL_NAME or "gemini-3.1-flash-lite").strip()

    def is_available(self) -> bool:
        """Returns True only if an API key is configured."""
        return bool(self.api_key)

    def is_vision_capable(self) -> bool:
        """
        Returns True if the configured model supports visual inputs (images/frames).
        """
        m = self.model_name.lower()
        # Explicit non-vision models
        non_vision = ["gpt-3.5", "davinci", "babbage", "curie", "text-", "llama-2", "deepseek-chat"]
        for nv in non_vision:
            if nv in m and "vision" not in m and "vl" not in m:
                return False
        # Default Gemini and modern OpenAI/Claude models are vision-capable
        return True

    def get_info(self) -> Dict[str, Any]:
        key = self.api_key
        provider = self.provider
        if not provider:
            if "gemini" in self.model_name.lower() or key.startswith("AIza") or key.startswith("AQ."):
                provider = "gemini"
            else:
                provider = "openai"
        return {
            "is_available": self.is_available(),
            "is_vision_capable": self.is_vision_capable(),
            "provider": provider,
            "model_name": self.model_name,
        }

    def generate_reply(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        frames: Optional[List[Any]] = None
    ) -> str:
        """
        Generates reply text using configured model provider.
        If frames are provided, includes them as visual context in chronological order.
        """
        if not self.is_available():
            return ""

        # If frames provided but model cannot take images
        if frames and not self.is_vision_capable():
            raise ValueError("vision_unsupported: Configured model does not support visual frames")

        try:
            prov = self.provider
            if prov == "gemini" or (not prov and ("gemini" in self.model_name.lower() or self.api_key.startswith("AIza") or self.api_key.startswith("AQ.")) and not self.base_url):
                return self._generate_gemini(system_prompt, messages, frames)
            else:
                return self._generate_openai(system_prompt, messages, frames)
        except Exception as e:
            err_str = str(e).lower()
            if "vision" in err_str or "image" in err_str or "unsupported" in err_str or "modal" in err_str:
                raise ValueError(f"vision_unsupported: {e}")
            print(f"Warning: Model generation failed ({e})")
            return "[Lỗi kết nối Model API]"

    def _generate_gemini(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        frames: Optional[List[Any]] = None
    ) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        contents = []

        total_msgs = len(messages)
        for idx, m in enumerate(messages):
            role = "user" if m.get("role") in ("user", "customer") else "model"
            parts = []
            
            # If last user message, attach video frames in time order
            if idx == total_msgs - 1 and role == "user" and frames:
                for f in frames:
                    # MediaFrame base64_data
                    b64 = getattr(f, "base64_data", "")
                    mime = getattr(f, "mime_type", "image/jpeg")
                    lbl = getattr(f, "label", "")
                    if b64:
                        parts.append({
                            "inline_data": {
                                "mime_type": mime,
                                "data": b64
                            }
                        })
            
            parts.append({"text": m.get("content", "")})
            contents.append({"role": role, "parts": parts})

        body = {
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": contents,
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 400
            }
        }
        for attempt in range(3):
            try:
                with httpx.Client(timeout=30.0) as client:
                    resp = client.post(url, json=body)
                    if resp.status_code == 429 and attempt < 2:
                        time.sleep(2.0 * (attempt + 1))
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "").strip()
                    return ""
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < 2:
                    time.sleep(2.0 * (attempt + 1))
                    continue
                raise
        return ""

    def _generate_openai(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        frames: Optional[List[Any]] = None
    ) -> str:
        base = self.base_url or "https://api.openai.com/v1"
        url = f"{base.rstrip('/')}/chat/completions"
        payload_messages = [{"role": "system", "content": system_prompt}]

        total_msgs = len(messages)
        for idx, m in enumerate(messages):
            role = "user" if m.get("role") in ("user", "customer") else "assistant"
            content_text = m.get("content", "")

            # If last user message and frames present, use multimodal content array
            if idx == total_msgs - 1 and role == "user" and frames:
                content_parts = []
                for f in frames:
                    b64 = getattr(f, "base64_data", "")
                    mime = getattr(f, "mime_type", "image/jpeg")
                    if b64:
                        content_parts.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,{b64}"
                            }
                        })
                content_parts.append({"type": "text", "text": content_text})
                payload_messages.append({"role": role, "content": content_parts})
            else:
                payload_messages.append({"role": role, "content": content_text})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        body = {
            "model": self.model_name or "gpt-4o-mini",
            "messages": payload_messages,
            "temperature": 0.3,
            "max_tokens": 2048
        }
        with httpx.Client(timeout=45.0) as client:
            resp = client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            if choices:
                msg = choices[0].get("message", {})
                content = (msg.get("content") or "").strip()
                if not content and msg.get("reasoning_content"):
                    # Fallback if model exhausted tokens inside thinking
                    content = msg.get("reasoning_content", "").strip()
                return content
        return ""

_model_adapter_instance: Optional[ModelAdapter] = None

def get_model_adapter() -> ModelAdapter:
    global _model_adapter_instance
    if _model_adapter_instance is None:
        _model_adapter_instance = ModelAdapter()
    return _model_adapter_instance
