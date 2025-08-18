import logging
from typing import Callable, Any

from api.common import run_chain, get_prompt_template, format_docs
from ..retrieval import get_vector_store

logger = logging.getLogger("pipelines.common")


_PROMPT_KEY_CACHE: dict[str, str] | None = None


def get_prompt_key_for_pipeline(pipeline_id: str, default: str = "general") -> str:
    global _PROMPT_KEY_CACHE
    if _PROMPT_KEY_CACHE is None:
        try:
            import os, json
            # backend/routers -> backend/api/pipelines.json
            routers_dir = os.path.dirname(os.path.dirname(__file__))
            pipelines_path = os.path.normpath(os.path.join(routers_dir, "..", "api", "pipelines.json"))
            with open(pipelines_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            _PROMPT_KEY_CACHE = {str(item.get("id")): str(item.get("prompt_key")) for item in data if item.get("id")}
        except Exception:
            _PROMPT_KEY_CACHE = {}
    return _PROMPT_KEY_CACHE.get(pipeline_id, default)


def summarize_external_data(external_data: dict[str, Any] | None) -> str:
    if not external_data:
        return "No external data available."

    parts: list[str] = []

    # Weather summary
    if "today_weather" in external_data:
        w = external_data["today_weather"] or {}
        parts.append(
            f"Current Weather → Temp: {w.get('main', {}).get('temp')}K, "
            f"Humidity: {w.get('main', {}).get('humidity')}%, "
            f"Clouds: {w.get('clouds', {}).get('all')}%, "
            f"Wind: {w.get('wind', {}).get('speed')} m/s."
        )

    # Forecast summary (optional shape: list of entries with 'dt','main','rain')
    if isinstance(external_data.get("forecast"), list):
        try:
            from datetime import datetime

            forecast_days: dict[str, dict] = {}
            for entry in external_data["forecast"]:
                ts = entry.get("dt")
                if not ts:
                    continue
                day = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
                main = entry.get("main", {})
                rain = (entry.get("rain", {}) or {}).get("3h", 0)
                forecast_days.setdefault(day, {"temps": [], "rain_total": 0})
                forecast_days[day]["temps"].append(main.get("temp"))
                forecast_days[day]["rain_total"] += rain

            compact: list[str] = []
            for day, vals in list(forecast_days.items())[:5]:
                temps = [t for t in vals["temps"] if t is not None]
                tmin = min(temps) if temps else None
                tmax = max(temps) if temps else None
                compact.append(f"{day}: Tmin={tmin}K, Tmax={tmax}K, Rain={vals['rain_total']}mm")
            if compact:
                parts.append("Forecast (next days): " + "; ".join(compact))
        except Exception:
            pass

    # Soil summary (Agro soil fields)
    if any(k in external_data for k in ("t0", "moisture")):
        parts.append(
            f"Soil → Moisture: {external_data.get('moisture')}, "
            f"Temp(0cm): {external_data.get('t0')}, "
            f"Temp(10cm): {external_data.get('t10')}."
        )

    # Mandi price summary (data.gov.in commodity prices)
    mandi_records = external_data.get("mandi_records") if isinstance(external_data, dict) else None
    if isinstance(mandi_records, list) and mandi_records:
        max_items = 5
        lines: list[str] = []
        for rec in mandi_records[:max_items]:
            market = rec.get("market") or rec.get("Market")
            district = rec.get("district") or rec.get("District")
            state = rec.get("state") or rec.get("State")
            commodity = rec.get("commodity") or rec.get("Commodity")
            variety = rec.get("variety") or rec.get("Variety")
            grade = rec.get("grade") or rec.get("Grade")
            modal = rec.get("modal_price") or rec.get("modal_price (Rs/quintal)") or rec.get("modal")
            min_p = rec.get("min_price") or rec.get("min")
            max_p = rec.get("max_price") or rec.get("max")
            date = rec.get("arrival_date") or rec.get("date")
            # Build a compact line
            loc = ", ".join([p for p in [market, district, state] if p])
            prod = " / ".join([p for p in [commodity, variety, grade] if p])
            price = f"Modal {modal} (min {min_p}, max {max_p})" if modal or min_p or max_p else "Price N/A"
            when = f" on {date}" if date else ""
            lines.append(f"{loc} — {prod}: {price}{when}")
        total = external_data.get("total") or len(mandi_records)
        parts.append("Mandi Prices (sample):\n" + "\n".join(lines) + f"\nTotal records: {total}; showing {min(len(mandi_records), max_items)}")

    return "\n".join(parts) if parts else "No external data available."


async def run_pipeline(
    question: str,
    *,
    prompt_key: str,
    external_fetcher: Callable[..., Any] | None = None,
    fetcher_args: dict[str, Any] | None = None,
) -> dict:
    # Step 1: external API data
    external_data = None
    if external_fetcher:
        try:
            external_data = await external_fetcher(**(fetcher_args or {}))
        except Exception as e:
            logger.error(f"External fetch failed: {e}")
            external_data = None

    # Step 2: retrieve docs
    vector_store = get_vector_store()
    retriever = vector_store.as_retriever(search_kwargs={"k": 4, "score_threshold": 0.6})
    docs = retriever.get_relevant_documents(question)
    docs_context = format_docs(docs)

    # Step 3: build context (use summarized external data)
    external_text = summarize_external_data(external_data)
    full_context = f"External Data:\n{external_text}\n\nRelevant Docs:\n{docs_context}"

    # Step 4: LLM
    prompt = get_prompt_template(prompt_key)
    answer = run_chain(prompt, {"context": full_context, "question": question})

    return {
        "output": answer,
        "external_data": external_data,
        "prompt_key": prompt_key,
    }
