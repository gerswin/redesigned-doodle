"""Apify Actor: Extrae tasas del BCV usando JustHTML (justhtml)"""

from __future__ import annotations

from apify import Actor
from httpx import AsyncClient
from justhtml import JustHTML


def clean_number(text: str) -> str:
    return " ".join(text.split()).strip()


def extract_rate(doc: JustHTML, block_id: str) -> tuple[str | None, str | None]:
    # Busca el div por id (equivalente a soup.find(id=...))
    blocks = doc.query(f"#{block_id}")
    if not blocks:
        return None, None

    block = blocks[0]

    code_nodes = block.query("span")
    value_nodes = block.query("strong")

    code = code_nodes[0].text.strip() if code_nodes else None
    value = clean_number(value_nodes[0].text) if value_nodes else None

    return code, value


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        url = actor_input.get(
            "url",
            "https://www.bcv.org.ve/estadisticas/tipo-cambio-de-referencia-smc",
        )

        async with AsyncClient(timeout=30) as client:
            Actor.log.info(f"Solicitando: {url}")
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()

        doc = JustHTML(response.text)  # ✅ Parseo

        # Fecha Valor
        date_nodes = doc.query("span.date-display-single")
        if date_nodes:
            fecha_valor_text = date_nodes[0].text.strip()
            fecha_valor_iso = date_nodes[0].attrs.get("content")
        else:
            fecha_valor_text = None
            fecha_valor_iso = None

        # Tasas
        rates = {}
        for block_id in ["dolar", "euro", "yuan", "lira", "rublo"]:
            code, value = extract_rate(doc, block_id)
            if code:
                rates[code] = value

        output = {
            "source_url": url,
            "fecha_valor_text": fecha_valor_text,
            "fecha_valor_iso": fecha_valor_iso,
            "rates": rates,
        }

        await Actor.push_data(output)