"""Apify Actor: BCV tasas (regex sobre HTML) + JustHTML opcional + SSL fallback (opción 3)"""

from __future__ import annotations

import re
from apify import Actor
from httpx import AsyncClient
import certifi

ID_TO_CODE = {
    "dolar": "USD",
    "euro": "EUR",
    "yuan": "CNY",
    "lira": "TRY",
    "rublo": "RUB",
}


def clean_text(s: str) -> str:
    return " ".join((s or "").split()).strip()


async def fetch_html(url: str, headers: dict) -> tuple[str, str]:
    """Return (html, ssl_mode). Tries verified first, then verify=False (opción 3)."""
    try:
        async with AsyncClient(timeout=30, verify=certifi.where(), headers=headers) as client:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
            return resp.text, "verified"
    except Exception as e:
        Actor.log.warning(f"SSL verify falló, aplicando opción 3 (verify=False). Error: {repr(e)}")

    async with AsyncClient(timeout=30, verify=False, headers=headers) as client:
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()
        return resp.text, "insecure_fallback"


def extract_fecha(html_text: str) -> tuple[str | None, str | None]:
    iso = None
    m_iso = re.search(r'class="date-display-single"[^>]*\scontent="([^"]+)"', html_text)
    if m_iso:
        iso = m_iso.group(1)

    txt = None
    m_txt = re.search(r'<span[^>]*class="date-display-single"[^>]*>(.*?)</span>', html_text, re.S)
    if m_txt:
        raw = re.sub(r"<[^>]+>", " ", m_txt.group(1))
        txt = clean_text(raw)

    return (txt or None), (iso or None)


def extract_rates_from_html(html_text: str) -> dict[str, str]:
    """
    Extrae <strong>VALOR</strong> dentro de cada bloque con id conocido.
    No depende de justhtml.
    """
    rates: dict[str, str] = {}

    for block_id, code in ID_TO_CODE.items():
        # Busca el primer <strong>...</strong> que aparezca después del div con ese id.
        # No intentamos "cerrar" el div (por HTML anidado); basta con "después del id".
        pattern = rf'id="{block_id}"[\s\S]*?<strong>\s*([^<]+?)\s*</strong>'
        m = re.search(pattern, html_text, re.IGNORECASE)
        if m:
            rates[code] = clean_text(m.group(1))

    return rates


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        url = actor_input.get(
            "url",
            "https://www.bcv.org.ve/estadisticas/tipo-cambio-de-referencia-smc",
        )

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            ),
            "Accept-Language": "es-VE,es;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        Actor.log.info(f"Solicitando: {url}")
        html_text, ssl_mode = await fetch_html(url, headers=headers)

        fecha_valor_text, fecha_valor_iso = extract_fecha(html_text)
        rates = extract_rates_from_html(html_text)

        output = {
            "source_url": url,
            "ssl_mode": ssl_mode,
            "fecha_valor_text": fecha_valor_text,
            "fecha_valor_iso": fecha_valor_iso,
            "rates": rates,
        }

        Actor.log.info(f"Output: {output}")
        await Actor.push_data(output)