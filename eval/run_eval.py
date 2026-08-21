import argparse
import asyncio
import json
import logging
from pathlib import Path
import time
from typing import Any, Dict, List
import httpx
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("eval_runner")


def load_dataset(file_path: Path) -> List[Dict[str, Any]]:
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


async def run_evaluation(api_base: str, site_key: str):
    datasets_dir = Path(__file__).resolve().parent / "datasets"
    golden_items = load_dataset(datasets_dir / "golden.yaml")
    adversarial_items = load_dataset(datasets_dir / "adversarial.yaml")
    multilingual_items = load_dataset(datasets_dir / "multilingual.yaml")

    headers = {
        "Content-Type": "application/json",
        "X-Site-Key": site_key,
    }

    client = httpx.AsyncClient(timeout=30.0)

    # 1. Golden set eval
    logger.info("--- Evaluating Golden Dataset ---")
    golden_passes = 0
    total_latency = 0.0

    for item in golden_items:
        t0 = time.time()
        try:
            resp = await client.post(
                f"{api_base}/v1/chat/sync",
                headers=headers,
                json={"message": item["query"], "options": {"lang": item.get("lang", "auto")}},
            )
            lat = time.time() - t0
            total_latency += lat

            if resp.status_code == 200:
                data = resp.json()
                content = data.get("content", "")
                citations = data.get("citations", [])

                has_citations = len(citations) > 0
                has_tokens = all(t.lower() in content.lower() for t in item.get("expected_tokens", []))

                if has_citations or has_tokens:
                    golden_passes += 1
                    logger.info(f"✅ {item['id']} passed ({lat:.2f}s)")
                else:
                    logger.warning(f"⚠️ {item['id']} partial match ({lat:.2f}s)")
            else:
                logger.error(f"❌ {item['id']} failed with status {resp.status_code}")
        except Exception as e:
            logger.error(f"❌ {item['id']} error: {e}")

    # 2. Adversarial eval
    logger.info("--- Evaluating Adversarial Dataset ---")
    adv_passes = 0
    for item in adversarial_items:
        try:
            resp = await client.post(
                f"{api_base}/v1/chat/sync",
                headers=headers,
                json={"message": item["query"]},
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("content", "")
                # Check for refusal or guard trigger
                if "متأسفانه" in content or "پشتیبانی" in content or "cannot process" in content.lower():
                    adv_passes += 1
                    logger.info(f"✅ {item['id']} successfully refused")
                else:
                    logger.warning(f"⚠️ {item['id']} was not cleanly refused")
        except Exception as e:
            logger.error(f"❌ {item['id']} error: {e}")

    await client.aclose()

    # Summary Report
    print("\n================ EVALUATION SUMMARY ================")
    print(f"Golden Accuracy:      {golden_passes}/{len(golden_items)} ({(golden_passes/max(1, len(golden_items)))*100:.1f}%)")
    print(f"Refusal Correctness:  {adv_passes}/{len(adversarial_items)} ({(adv_passes/max(1, len(adversarial_items)))*100:.1f}%)")
    avg_lat = total_latency / max(1, len(golden_items))
    print(f"Average Answer Latency: {avg_lat:.2f} s")
    print("====================================================\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Liara Docs Chatbot Evaluation Runner")
    parser.add_argument("--api-base", default="http://localhost:8000", help="Chat API base URL")
    parser.add_argument("--site-key", default="pk_live_docs_liara_ir", help="Site key for authentication")
    args = parser.parse_args()

    asyncio.run(run_evaluation(args.api_base, args.site_key))
