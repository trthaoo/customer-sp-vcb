import argparse
import sys
import json
from src.pipeline.normalizer import MessageNormalizer
from src.pipeline.orchestrator import get_orchestrator

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Customer Service Auto-Reply Dry-Run CLI")
    parser.add_argument("--text", "-t", type=str, required=True, help="Customer message / comment text")
    parser.add_argument("--platform", "-p", type=str, default="ig", choices=["ig", "fb", "tiktok"], help="Platform (ig, fb, tiktok)")
    parser.add_argument("--surface", "-s", type=str, default="comment", choices=["comment", "dm"], help="Surface (comment, dm)")
    parser.add_argument("--context", "-c", type=str, default=None, help="Post / Video caption context")

    args = parser.parse_args()

    # Normalize inbound message as dry_run
    inbound = MessageNormalizer.normalize_manual(
        text=args.text,
        platform=args.platform,
        surface=args.surface,
        post_context=args.context,
        env="prod",
        source="dry_run"
    )

    orchestrator = get_orchestrator()
    result = orchestrator.process(inbound)

    print("\n" + "="*50)
    print("        AUTO-REPLY DRY-RUN RESULTS")
    print("="*50)
    print(f"Platform:        {result.inbound.platform} ({result.inbound.channel})")
    print(f"Surface:         {result.inbound.surface}")
    print(f"Customer Input:  \"{result.inbound.text}\"")
    if result.inbound.post_context:
        print(f"Context:         \"{result.inbound.post_context}\"")
    print("-" * 50)
    print(f"Matched Product: {result.matched_product.name if result.matched_product else 'None'}")
    if result.ambiguous_products:
        names = [p.name for p in result.ambiguous_products]
        print(f"Ambiguous Match: {names} (Do NOT guess!)")
    print(f"Intent:          {result.intent}")
    print(f"Matched EdgeCase:{result.matched_edge_case or 'None'}")
    print(f"Matched Rule:    {result.matched_rule or 'None'}")
    print(f"Knowledge Files: {result.knowledge_files}")
    print(f"Facts Loaded:    {json.dumps(result.knowledge_facts, ensure_ascii=False)}")
    print("-" * 50)
    print(f"Decision:        {result.decision}")
    print(f"Flag:            {result.flag}")
    print(f"Needs Human:     {result.needs_human}")
    if result.escalate_reason:
        print(f"Escalate Reason: {result.escalate_reason}")
    print(f"Reply Sent:      {result.reply_sent} (No live send on dry-run)")
    print("-" * 50)
    print(f"Draft Reply:     \"{result.draft_reply}\"")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
