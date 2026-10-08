import uuid
from typing import Dict, Any, Optional
from src.models import InboundMessage, PlatformType, ChannelType, SurfaceType, SourceType

def map_platform(raw_platform: str) -> PlatformType:
    p = str(raw_platform).strip().lower()
    if p in ("instagram", "ig"):
        return "ig"
    elif p in ("facebook", "fb", "messenger"):
        return "fb"
    elif p in ("tiktok", "tt"):
        return "tiktok"
    return "ig"  # Default fallback if unknown

def map_channel(platform: PlatformType) -> ChannelType:
    return "meta" if platform in ("ig", "fb") else "tiktok"

class MessageNormalizer:
    @staticmethod
    def normalize_webhook(payload: Dict[str, Any], env: str = "prod", source: SourceType = "live") -> Optional[InboundMessage]:
        event_type = payload.get("event")
        event_id = payload.get("id") or str(uuid.uuid4())

        if event_type == "comment.received":
            comment = payload.get("comment", {})
            raw_plat = comment.get("platform") or payload.get("account", {}).get("platform") or "ig"
            platform = map_platform(raw_plat)
            channel = "meta" if platform in ("ig", "fb") else "tiktok"
            
            author = comment.get("author", {})
            is_own = author.get("isOwner", False)
            if is_own:
                # Ignore self comments to avoid endless loop
                return None

            post_caption = comment.get("postCaption") or comment.get("videoCaption") or payload.get("post", {}).get("caption")
            post_id = comment.get("postId") or comment.get("platformPostId")
            
            # Extract media URL from Zernio event payload. Do not invent an endpoint.
            media_url = (
                comment.get("mediaUrl") or 
                comment.get("videoUrl") or 
                comment.get("imageUrl") or 
                payload.get("post", {}).get("mediaUrl") or 
                payload.get("post", {}).get("videoUrl") or 
                payload.get("post", {}).get("imageUrl")
            )
            carousel_urls = comment.get("carouselMedia") or comment.get("mediaUrls") or payload.get("post", {}).get("carouselMedia") or []
            media_type = comment.get("mediaType") or payload.get("post", {}).get("mediaType")

            frames = []
            context_missing = False
            if media_url or carousel_urls:
                try:
                    from src.pipeline.media import get_media_processor
                    processor = get_media_processor()
                    frames, context_missing = processor.process_media(
                        post_id=post_id,
                        media_url=media_url,
                        media_type=media_type,
                        carousel_urls=carousel_urls
                    )
                except Exception as e:
                    print(f"Warning: Media frame extraction failed: {e}")
                    context_missing = True
            else:
                # No URL = mark context_missing
                context_missing = True

            return InboundMessage(
                id=comment.get("id") or str(uuid.uuid4()),
                event_id=event_id,
                platform=platform,
                channel=channel,
                surface="comment",
                text=(comment.get("text") or "").strip(),
                post_context=post_caption,
                post_id=post_id,
                media_url=media_url,
                media_type=media_type,
                carousel_urls=carousel_urls,
                frames=frames,
                context_missing=context_missing,
                thread_id=comment.get("parentCommentId") or comment.get("id"),
                user_id=author.get("id"),
                user_name=author.get("name") or author.get("username"),
                env=env,
                source=source
            )

        elif event_type == "message.received":
            message = payload.get("message", {})
            direction = message.get("direction", "incoming")
            if direction != "incoming":
                # Ignore outgoing messages
                return None

            raw_plat = message.get("platform") or payload.get("account", {}).get("platform") or "ig"
            platform = map_platform(raw_plat)
            channel = "meta" if platform in ("ig", "fb") else "tiktok"
            sender = message.get("sender", {})
            conversation = payload.get("conversation", {})
            conv_id = message.get("conversationId") or conversation.get("id")

            return InboundMessage(
                id=message.get("id") or str(uuid.uuid4()),
                event_id=event_id,
                platform=platform,
                channel=channel,
                surface="dm",
                text=(message.get("text") or "").strip(),
                post_context=None,
                post_id=None,
                thread_id=conv_id,
                user_id=sender.get("id"),
                user_name=sender.get("name") or sender.get("username"),
                env=env,
                source=source
            )

        return None

    @staticmethod
    def normalize_manual(
        text: str,
        platform: str = "ig",
        surface: str = "comment",
        post_context: Optional[str] = None,
        thread_id: Optional[str] = None,
        user_id: Optional[str] = None,
        env: str = "prod",
        source: SourceType = "dry_run",
        msg_id: Optional[str] = None
    ) -> InboundMessage:
        plat = map_platform(platform)
        channel = "meta" if plat in ("ig", "fb") else "tiktok"
        surf: SurfaceType = "comment" if surface.lower() in ("comment", "cmt") else "dm"
        return InboundMessage(
            id=msg_id or (f"dry_{uuid.uuid4().hex[:12]}" if source == "dry_run" else str(uuid.uuid4())),
            event_id=None,
            platform=plat,
            channel=channel,
            surface=surf,
            text=text.strip(),
            post_context=post_context,
            post_id=None,
            thread_id=thread_id or f"thread_{uuid.uuid4().hex[:8]}",
            user_id=user_id or "user_demo",
            user_name="Khách hàng",
            env=env,
            source=source
        )
