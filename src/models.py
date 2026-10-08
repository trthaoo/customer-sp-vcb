from typing import List, Optional, Literal, Dict, Any, Union
from pydantic import BaseModel, Field

PlatformType = Literal["ig", "fb", "tiktok"]
ChannelType = Literal["meta", "tiktok", "shared"]
SurfaceType = Literal["comment", "dm", "any"]
SourceType = Literal["live", "test", "dry_run", "brand_test"]
DecisionType = Literal["auto_reply", "fallback", "escalate"]
FlagType = Literal["auto_reply", "handover"]
HandoverStateType = Literal["open", "claimed", "waiting_on_us", "resolved"]
StatusBadgeType = Literal["handled", "partial", "fallback", "handover"]

class Product(BaseModel):
    id: str
    name: str
    aliases: List[str] = Field(default_factory=list)
    price: Optional[float] = None
    currency: Optional[str] = None
    material: Optional[str] = None
    description: Optional[str] = None
    variants: Optional[List[Any]] = None
    in_stock: Optional[bool] = None
    ship_note: Optional[str] = None
    size_guide: Optional[str] = None
    url: Optional[str] = None
    image_url: Optional[str] = None
    image_path: Optional[str] = None
    notes: Optional[str] = None

class RuleWhen(BaseModel):
    intent: str
    contains_any: List[str] = Field(default_factory=list)
    product_required: bool = False

class Rule(BaseModel):
    id: str
    channel: ChannelType
    surface: SurfaceType
    when: RuleWhen
    use_knowledge: List[str] = Field(default_factory=list)
    if_missing: Literal["escalate", "fallback", "ignore"] = "escalate"
    reply_guide: str

class EdgeCase(BaseModel):
    id: str
    channel: ChannelType
    trigger: str
    contains_any: List[str] = Field(default_factory=list)
    do: str
    do_not: str
    escalate: bool = False
    example_user_message: Optional[str] = None
    example_good_reply: Optional[str] = None

class MediaFrame(BaseModel):
    timestamp: float = 0.0
    label: str = "t=0.0s"
    base64_data: str = ""
    mime_type: str = "image/jpeg"
    file_path: Optional[str] = None

class InboundMessage(BaseModel):
    id: str
    event_id: Optional[str] = None
    platform: PlatformType
    channel: Literal["meta", "tiktok"]
    surface: Literal["comment", "dm"]
    text: str
    post_context: Optional[str] = None
    post_id: Optional[str] = None
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    carousel_urls: List[str] = Field(default_factory=list)
    frames: List[MediaFrame] = Field(default_factory=list)
    context_missing: bool = False
    thread_id: Optional[str] = None
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    env: str = "prod"
    source: SourceType = "live"
    history: List[Dict[str, str]] = Field(default_factory=list)

class PipelineResult(BaseModel):
    inbound: InboundMessage
    matched_product: Optional[Product] = None
    ambiguous_products: List[Product] = Field(default_factory=list)
    matched_rule: Optional[str] = None
    matched_edge_case: Optional[str] = None
    intent: str = "other"
    knowledge_files: List[str] = Field(default_factory=list)
    knowledge_facts: Dict[str, Any] = Field(default_factory=dict)
    retrieved_chunks: List[Dict[str, Any]] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    status_badge: StatusBadgeType = "handled"
    draft_reply: str = ""
    final_reply: str = ""
    decision: DecisionType = "fallback"
    flag: FlagType = "handover"
    needs_human: bool = False
    escalate_reason: Optional[str] = None
    example_good_reply: Optional[str] = None
    model_called: bool = False
    model_used: Optional[str] = None
    caption: Optional[str] = None
    frames: List[MediaFrame] = Field(default_factory=list)
    frame_count: int = 0
    frame_timestamps: List[str] = Field(default_factory=list)
    visual_product_guess: Optional[str] = None
    catalogue_id_matched: Optional[str] = None
    frame_used: Optional[str] = None
    context_missing: bool = False
    vision_unsupported: bool = False
    short_reason: Optional[str] = None
    reply_sent: bool = False
    attached_image_url: Optional[str] = None

class EventRecord(BaseModel):
    id: str
    ts: str
    env: str
    source: SourceType
    channel: Literal["meta", "tiktok"]
    platform: PlatformType
    surface: Literal["comment", "dm"]
    intent: str
    product_id: Optional[str] = None
    matched_rule: Optional[str] = None
    knowledge_files: List[str] = Field(default_factory=list)
    decision: DecisionType
    flag: FlagType
    handover_state: Optional[HandoverStateType] = None
    reply_sent: bool = False
    user_message: str = ""
    reply_text: str = ""
    escalate_reason: Optional[str] = None
    thread_id: Optional[str] = None
    user_id: Optional[str] = None
