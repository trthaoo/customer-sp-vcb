import hmac
import hashlib
import uuid
from typing import Dict, Any, Optional
import httpx
from src.config import ZERNIO_API_KEY, ZERNIO_BASE_URL, ZERNIO_WEBHOOK_SECRET, AUTO_SEND

class ZernioClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        auto_send: Optional[bool] = None
    ):
        self.api_key = api_key if api_key is not None else ZERNIO_API_KEY
        self.base_url = (base_url if base_url is not None else ZERNIO_BASE_URL).rstrip("/")
        self.webhook_secret = webhook_secret if webhook_secret is not None else ZERNIO_WEBHOOK_SECRET
        self.auto_send = auto_send if auto_send is not None else AUTO_SEND

    def _headers(self, idempotency_key: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def verify_webhook_signature(self, raw_body: bytes, signature_header: Optional[str]) -> bool:
        """
        Verifies HMAC-SHA256 signature using ZERNIO_WEBHOOK_SECRET.
        Headers: X-Zernio-Signature or X-Webhook-Signature.
        If the secret is not set, every request is rejected.
        """
        if not self.webhook_secret:
            return False
        if not signature_header:
            return False

        expected = hmac.new(
            self.webhook_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256
        ).hexdigest()

        # Handle signatures with or without 'sha256=' prefix
        clean_sig = signature_header.strip()
        if clean_sig.startswith("sha256="):
            clean_sig = clean_sig.split("=", 1)[1]

        return hmac.compare_digest(expected.lower(), clean_sig.lower())

    def reply_comment(
        self,
        post_id: str,
        comment_id: str,
        message: str,
        account_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        POST /v1/inbox/comments/{postId}
        Docs: https://docs.zernio.com/comments/reply-to-inbox-post
        """
        if not self.auto_send or not self.api_key:
            # Live send disabled or no API key -> Dry run simulation
            return {
                "dry_run": True,
                "success": True,
                "action": "reply_comment",
                "postId": post_id,
                "commentId": comment_id,
                "message": message,
                "note": "Live send disabled (AUTO_SEND=false or empty API key)"
            }

        endpoint = f"{self.base_url}/inbox/comments/{post_id}"
        body: Dict[str, Any] = {
            "commentId": comment_id,
            "message": message
        }
        if account_id:
            body["accountId"] = account_id

        idem_key = str(uuid.uuid4())
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(endpoint, json=body, headers=self._headers(idem_key))
            resp.raise_for_status()
            return resp.json()

    def send_dm(
        self,
        conversation_id: str,
        message: str,
        account_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        POST /v1/inbox/conversations/{conversationId}/messages
        Docs: https://docs.zernio.com/messages/send-inbox-message
        """
        if not self.auto_send or not self.api_key:
            # Live send disabled or no API key -> Dry run simulation
            return {
                "dry_run": True,
                "success": True,
                "action": "send_dm",
                "conversationId": conversation_id,
                "message": message,
                "note": "Live send disabled (AUTO_SEND=false or empty API key)"
            }

        endpoint = f"{self.base_url}/inbox/conversations/{conversation_id}/messages"
        body: Dict[str, Any] = {
            "message": message
        }
        if account_id:
            body["accountId"] = account_id

        idem_key = str(uuid.uuid4())
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(endpoint, json=body, headers=self._headers(idem_key))
            resp.raise_for_status()
            return resp.json()

    def list_comments(self, post_id: str) -> Dict[str, Any]:
        """
        GET /v1/inbox/comments/{postId}
        Docs: https://docs.zernio.com/comments/list-inbox-comments
        """
        if not self.api_key:
            return {"comments": [], "note": "No API key"}
        endpoint = f"{self.base_url}/inbox/comments/{post_id}"
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(endpoint, headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    def list_conversations(self) -> Dict[str, Any]:
        """
        GET /v1/inbox/conversations
        Docs: https://docs.zernio.com/messages/list-inbox-conversations
        """
        if not self.api_key:
            return {"conversations": [], "note": "No API key"}
        endpoint = f"{self.base_url}/inbox/conversations"
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(endpoint, headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    def list_messages(self, conversation_id: str) -> Dict[str, Any]:
        """
        GET /v1/inbox/conversations/{conversationId}/messages
        Docs: https://docs.zernio.com/messages/list-inbox-messages
        """
        if not self.api_key:
            return {"messages": [], "note": "No API key"}
        endpoint = f"{self.base_url}/inbox/conversations/{conversation_id}/messages"
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(endpoint, headers=self._headers())
            resp.raise_for_status()
            return resp.json()
