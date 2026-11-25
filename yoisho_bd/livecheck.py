"""Phase 1 step 1a: prove the three live services work on this server.

1. One web search through TinyFish.
2. One website read through Sellbird's checked HTTP client.
3. One Claude answer through Sellbird's Brain (no tools, plan quota).

Prints a pass or fail line for each, with counts only. Sends nothing, saves
nothing except the usage record Sellbird keeps for every Claude call.
"""

from __future__ import annotations

import asyncio
import re

DEFAULT_QUERY = "Japanese manufacturing company India subsidiary"


async def _search(query: str) -> tuple[bool, str, list]:
    import httpx

    from sellbird.collectors.discover import DiscoveryQuery, TinyFish
    from sellbird.config import load_env

    env = load_env().model_dump()
    if not str(env.get("tinyfish_api_key", "")).strip():
        return False, "TINYFISH_API_KEY is empty in .env", []
    async with httpx.AsyncClient(timeout=20) as client:
        results = await TinyFish().fetch(client, env, DiscoveryQuery(term=query, depth=10))
    with_site = [b for b in results if b.website or b.domain]
    if not with_site:
        return False, f"search answered with {len(results)} results, none with a website", []
    return True, f"{len(results)} results, {len(with_site)} with a website", with_site


async def _read(candidates: list) -> tuple[bool, str, str]:
    from sellbird.collectors.profile import _text
    from sellbird.public_http import public_http_client

    async with public_http_client(timeout=15) as client:
        for business in candidates[:5]:
            url = business.website or f"https://{business.domain}"
            try:
                resp = await client.get(url)
            except Exception:
                continue
            if resp.status_code != 200 or "html" not in resp.headers.get("content-type", ""):
                continue
            text = re.sub(r"\s+", " ", _text(resp.text)).strip()
            if len(text) >= 200:
                return True, f"read 1 page, {len(text)} characters of text", text
    return False, "none of the first 5 results gave a readable page", ""


async def _think(page_text: str) -> tuple[bool, str]:
    from sellbird.brain import Brain
    from sellbird.config import load_config
    from sellbird.state import StateManager

    state = StateManager()
    await state.init_db()
    brain = Brain(state, load_config().brain)
    prompt = (
        "Below is text from one company website. In one sentence, say what the "
        "company does. Use only the text. If the text does not say, answer UNKNOWN.\n\n"
        "<page>\n" + page_text[:4000] + "\n</page>"
    )
    answer = (await brain.think(prompt, agent="yoisho", task="livecheck")).strip()
    if not answer:
        reason = brain.paused_reason() or "Claude gave an empty answer"
        return False, reason
    return True, f"Claude answered ({len(answer.split())} words)"


async def run(query: str = DEFAULT_QUERY) -> int:
    """Run the three checks. Returns the number of failed checks."""
    failures = 0
    ok, note, candidates = await _search(query)
    print(f"[{'PASS' if ok else 'FAIL'}] 1. Web search (TinyFish): {note}")
    failures += not ok

    text = ""
    if ok:
        ok, note, text = await _read(candidates)
    else:
        note = "skipped, the search failed"
    print(f"[{'PASS' if ok else 'FAIL'}] 2. Website read: {note}")
    failures += not ok

    if text:
        ok, note = await _think(text)
    else:
        ok, note = False, "skipped, no page text to read"
    print(f"[{'PASS' if ok else 'FAIL'}] 3. Claude answer: {note}")
    failures += not ok

    print("All 3 live checks passed." if not failures else f"{failures} of 3 checks failed.")
    return failures


def configure(parser):
    parser.add_argument("--query", default=DEFAULT_QUERY, help="Search phrase for check 1")

    def _main(args):
        raise SystemExit(1 if asyncio.run(run(args.query)) else 0)

    return _main
