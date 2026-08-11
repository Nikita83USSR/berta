"""
BERTA tools: Internet / Web (SAFE by default).
web_search, web_open, web_fetch, web_download.
"""

from __future__ import annotations

import re
import time
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse, urljoin, quote

import requests

from core.event_bus import bus

# --- limits ---
DEFAULT_TIMEOUT = 12
MAX_SEARCH_RESULTS = 8
MAX_BODY_BYTES = 512_000
MAX_TEXT_CHARS = 20_000
ALLOWED_SCHEMES = {"http", "https"}

USER_AGENT = (
    "Mozilla/5.0 (compatible; BERTA/0.3; +https://github.com/Nikita83USSR/berta)"
)


def _ok(data: Any) -> dict:
    return {"ok": True, "data": data, "error": None, "success": True}


def _err(type_: str, message: str) -> dict:
    return {
        "ok": False,
        "data": None,
        "error": {"type": type_, "message": message},
        "success": False,
        "error_message": message,
    }


def _validate_url(url: str) -> tuple[bool, str]:
    url = (url or "").strip()
    if not url:
        return False, "URL пустой"
    try:
        p = urlparse(url)
    except Exception as e:
        return False, f"Некорректный URL: {e}"
    if p.scheme.lower() not in ALLOWED_SCHEMES:
        return False, f"Разрешены только HTTP/HTTPS, получено: {p.scheme or '(пусто)'}"
    if not p.netloc:
        return False, "URL без хоста"
    # basic SSRF: block obvious local/private hosts by default
    host = (p.hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"} or host.endswith(".local"):
        return False, "Доступ к localhost/private host запрещён"
    if re.match(r"^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[0-1])\.)", host):
        return False, "Доступ к private network запрещён"
    return True, url


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip = 0
        self._skip_tags = {"script", "style", "noscript", "svg", "iframe"}

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self._skip_tags:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag.lower() in self._skip_tags and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self._skip:
            return
        t = data.strip()
        if t:
            self._parts.append(t)

    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self._parts)).strip()


def _extract_readable(html: str, max_chars: int = MAX_TEXT_CHARS) -> str:
    try:
        parser = _TextExtractor()
        parser.feed(html)
        text = parser.text()
    except Exception:
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "…"
    return text



def _looks_like_weather(query: str) -> bool:
    q = (query or "").lower()
    keys = (
        "погод", "weather", "температур", "градус", "осадк",
        "forecast", "прогноз погод",
    )
    return any(k in q for k in keys)


def _extract_city_for_weather(query: str) -> str:
    """Грубая эвристика города из запроса о погоде."""
    q = (query or "").strip()
    for w in (
        "какая", "какой", "какую", "сейчас", "сегодня", "завтра",
        "погода", "погоде", "погодой", "погоду", "weather", "в", "во",
        "на", "мне", "скажи", "покажи", "прогноз", "температура",
        "температуру", "?", "!",
    ):
        q = re.sub(rf"\b{re.escape(w)}\b", " ", q, flags=re.I)
    q = re.sub(r"\s+", " ", q).strip(" ,.")
    # русские падежные окончания городов (грубо)
    for suf, base in (
        ("ы", ""), ("е", "а"), ("у", "а"), ("ой", "а"), ("ею", "я"),
        ("ом", ""), ("ем", ""),
    ):
        if len(q) > 3 and q.endswith(suf):
            # Москве -> Москва, Питере -> Питер
            candidate = q[: -len(suf)] + base
            if candidate:
                q = candidate
                break
    mapping = {
        "москв": "Moscow",
        "москва": "Moscow",
        "спб": "Saint Petersburg",
        "питер": "Saint Petersburg",
        "санкт-петербург": "Saint Petersburg",
        "петербург": "Saint Petersburg",
        "новосибирск": "Novosibirsk",
        "екатеринбург": "Yekaterinburg",
        "казан": "Kazan",
        "казань": "Kazan",
    }
    low = q.lower()
    for k, v in mapping.items():
        if low.startswith(k) or k in low:
            return v
    return q or "Moscow"



def _wttr_json(city: str) -> dict | None:
    """Пробует несколько вариантов URL wttr.in."""
    candidates = [city]
    # если кириллица — пробуем как есть
    for c in list(candidates):
        try:
            candidates.append(quote(c))
        except Exception:
            pass
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "ru,en;q=0.8",
    }
    last_err = None
    for c in candidates:
        url = f"https://wttr.in/{c}"
        try:
            r = requests.get(
                url,
                params={"format": "j1"},
                headers=headers,
                timeout=min(6, DEFAULT_TIMEOUT),
            )
            if r.status_code != 200:
                last_err = f"HTTP {r.status_code}"
                continue
            if not r.content or r.text.lstrip().startswith("<!"):
                last_err = "HTML instead of JSON"
                continue
            data = r.json()
            cur = (data.get("current_condition") or [None])[0]
            if not cur:
                last_err = "empty current_condition"
                continue
            area = ((data.get("nearest_area") or [{}])[0].get("areaName") or [{}])
            area_name = area[0].get("value", city) if area else city
            desc = ""
            # предпочтительно русский
            if cur.get("lang_ru"):
                desc = cur["lang_ru"][0].get("value", "")
            elif cur.get("weatherDesc"):
                desc = cur["weatherDesc"][0].get("value", "")
            snippet = (
                f"{area_name}: {desc}, {cur.get('temp_C', '?')}°C "
                f"(ощущается {cur.get('FeelsLikeC', '?')}°C), "
                f"влажность {cur.get('humidity', '?')}%, "
                f"ветер {cur.get('windspeedKmph', '?')} км/ч"
            )
            return {
                "title": f"Погода сейчас — {area_name}",
                "url": f"https://wttr.in/{city}",
                "snippet": snippet,
                "source": "wttr.in",
                "raw": {
                    "temp_C": cur.get("temp_C"),
                    "feels_C": cur.get("FeelsLikeC"),
                    "humidity": cur.get("humidity"),
                    "wind_kmh": cur.get("windspeedKmph"),
                    "desc": desc,
                    "area": area_name,
                },
            }
        except Exception as e:
            last_err = str(e)[:200]
            continue
    return None


def _open_meteo(city: str) -> dict | None:
    """Запасной источник: Open-Meteo geocoding + current weather."""
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 5, "language": "ru", "format": "json"},
            headers={"User-Agent": USER_AGENT},
            timeout=DEFAULT_TIMEOUT,
        )
        geo.raise_for_status()
        results = (geo.json() or {}).get("results") or []
        if not results:
            # повтор без language
            geo = requests.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": city, "count": 5, "format": "json"},
                headers={"User-Agent": USER_AGENT},
                timeout=DEFAULT_TIMEOUT,
            )
            geo.raise_for_status()
            results = (geo.json() or {}).get("results") or []
        if not results:
            return None
        place = results[0]
        lat, lon = place.get("latitude"), place.get("longitude")
        name = place.get("name") or city
        country = place.get("country") or ""
        admin = place.get("admin1") or ""
        w = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current_weather": "true",
                "timezone": "auto",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=DEFAULT_TIMEOUT,
        )
        w.raise_for_status()
        cur = (w.json() or {}).get("current_weather") or {}
        # WMO weather interpretation (упрощённо)
        codes = {
            0: "Ясно",
            1: "Преимущественно ясно",
            2: "Переменная облачность",
            3: "Пасмурно",
            45: "Туман",
            48: "Туман",
            51: "Морось",
            61: "Дождь",
            63: "Дождь",
            65: "Сильный дождь",
            71: "Снег",
            73: "Снег",
            75: "Сильный снег",
            80: "Ливень",
            95: "Гроза",
        }
        code = cur.get("weathercode")
        desc = codes.get(code, f"код {code}")
        temp = cur.get("temperature")
        wind = cur.get("windspeed")
        loc = ", ".join(x for x in (name, admin, country) if x)
        snippet = f"{loc}: {desc}, {temp}°C, ветер {wind} км/ч"
        return {
            "title": f"Погода сейчас — {name}",
            "url": f"https://open-meteo.com/",
            "snippet": snippet,
            "source": "open-meteo",
            "raw": {
                "temp_C": temp,
                "wind_kmh": wind,
                "desc": desc,
                "area": loc,
                "lat": lat,
                "lon": lon,
            },
        }
    except Exception:
        return None


def _weather_lookup(query: str) -> list:
    city = _extract_city_for_weather(query)
    results = []
    # Open-Meteo первым: чаще доступен из РФ, чем wttr.in
    item = _open_meteo(city)
    if item:
        results.append(item)
    if not results:
        item = _wttr_json(city)
        if item:
            results.append(item)
    # если город после эвристики «Moscow» а в запросе другое — попробовать сырой хвост
    if not results and query:
        raw = re.sub(
            r"(?i)\b(погода|weather|прогноз|температура|сейчас|какая|какой)\b",
            " ",
            query,
        )
        raw = re.sub(r"\s+", " ", raw).strip(" ?!,.")
        if raw and raw.lower() != city.lower():
            item = _wttr_json(raw) or _open_meteo(raw)
            if item:
                results.append(item)
    return results



def web_search(query: str, limit: int = 5, language: str | None = None) -> dict:
    """
    Поиск: RU-источники первыми, зарубежные — запасные.
    1) погода: Open-Meteo → wttr.in
    2) новости: RSS Lenta/RIA/RBC/Interfax/TASS
    3) Wikipedia.ru → Wikipedia.en
    4) DuckDuckGo Instant Answer (короткий timeout, может быть недоступен в РФ)
    """
    t0 = time.time()
    query = (query or "").strip()
    if not query:
        return _err("ValidationError", "query обязателен")
    limit = max(1, min(int(limit or 5), MAX_SEARCH_RESULTS))
    lang = (language or "").lower()
    prefer_ru = lang.startswith("ru") or any(ord(c) > 127 for c in query)

    bus.emit(
        "WEB_REQUEST",
        {"tool": "web_search", "query": query[:200], "limit": limit},
        source="web",
    )
    results: list = []
    errors: list = []

    # 1) Погода
    if _looks_like_weather(query):
        try:
            results.extend(_weather_lookup(query))
        except Exception as e:
            errors.append(f"weather:{e}")

    # 2) Новости — RSS российских агентств
    if len(results) < limit and _looks_like_news(query):
        try:
            results.extend(_news_rss(limit=limit))
        except Exception as e:
            errors.append(f"news:{e}")

    # 3) Wikipedia (RU приоритет)
    if len(results) < limit:
        try:
            wiki_lang = "ru" if prefer_ru else ("ru" if (language or "").startswith("ru") else "en")
            results.extend(_wikipedia_search(query, limit=limit - len(results), lang=wiki_lang))
            if len(results) < limit and wiki_lang == "ru":
                results.extend(_wikipedia_search(query, limit=limit - len(results), lang="en"))
        except Exception as e:
            errors.append(f"wiki:{e}")

    # 4) DuckDuckGo Instant Answer — короткий timeout, может быть недоступен в РФ
    if len(results) < limit:
        try:
            ddg = _ddg_instant(query, limit=limit - len(results), timeout=6)
            results.extend(ddg)
        except Exception as e:
            errors.append(f"ddg:{e}")

    # дедуп по url+title
    seen = set()
    uniq = []
    for item in results:
        key = (item.get("url") or "") + "|" + (item.get("title") or "")[:80]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(item)
        if len(uniq) >= limit:
            break

    elapsed = round(time.time() - t0, 3)
    return _ok(
        {
            "query": query,
            "limit": limit,
            "count": len(uniq),
            "results": uniq,
            "elapsed": elapsed,
            "errors": errors[:5] if errors and not uniq else [],
            "note": (
                "Зарубежные поисковики могут быть недоступны; использованы RU-источники"
                if prefer_ru
                else None
            ),
        }
    )


def _looks_like_news(query: str) -> bool:
    q = (query or "").lower()
    keys = (
        "новост", "news", "сегодня в мире", "главные события",
        "что произошло", "свежие новости", "лента новостей",
    )
    return any(k in q for k in keys)


def _news_rss(limit: int = 5) -> list:
    """RSS российских агентств. Берём по 1–2 с каждой ленты (не только Lenta)."""
    feeds = [
        ("https://lenta.ru/rss", "lenta.ru"),
        ("https://ria.ru/export/rss2/index.xml", "ria.ru"),
        ("https://rssexport.rbc.ru/rbcnews/news/30/full.rss", "rbc.ru"),
        ("https://www.interfax.ru/rss.asp", "interfax.ru"),
        ("https://tass.ru/rss/v2.xml", "tass.ru"),
    ]
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/rss+xml,application/xml,text/xml,*/*",
    }
    per_feed = max(1, (limit + len(feeds) - 1) // len(feeds))
    buckets: list[list] = []
    for url, source in feeds:
        bucket = []
        try:
            r = requests.get(url, headers=headers, timeout=8)
            if r.status_code != 200 or not r.content:
                continue
            text = r.content.decode(r.encoding or "utf-8", errors="replace")
            for block in re.findall(r"<item\b[^>]*>(.*?)</item>", text, re.I | re.S):
                title_m = re.search(
                    r"<title[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>",
                    block,
                    re.I | re.S,
                )
                link_m = re.search(
                    r"<link[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</link>",
                    block,
                    re.I | re.S,
                )
                desc_m = re.search(
                    r"<description[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>",
                    block,
                    re.I | re.S,
                )
                title = re.sub(r"<[^>]+>", "", (title_m.group(1) if title_m else "")).strip()
                link = re.sub(r"<[^>]+>", "", (link_m.group(1) if link_m else "")).strip()
                desc = re.sub(r"<[^>]+>", "", (desc_m.group(1) if desc_m else "")).strip()
                if not title:
                    continue
                bucket.append(
                    {
                        "title": title[:300],
                        "url": link[:1000],
                        "snippet": desc[:400],
                        "source": source,
                    }
                )
                if len(bucket) >= per_feed:
                    break
        except Exception:
            continue
        if bucket:
            buckets.append(bucket)
    # round-robin
    items = []
    idx = 0
    while len(items) < limit and buckets:
        progressed = False
        for b in buckets:
            if idx < len(b):
                items.append(b[idx])
                progressed = True
                if len(items) >= limit:
                    break
        if not progressed:
            break
        idx += 1
    return items


def _clean_search_query(query: str) -> str:
    """Убрать вопросительные обороты для Wikipedia/поиска."""
    q = (query or "").strip()
    for w in (
        "что такое", "кто такой", "кто такая", "расскажи про", "расскажи о",
        "что значит", "означает", "это", "пожалуйста", "скажи", "найди",
        "поищи", "в интернете", "информация о", "информацию о",
    ):
        q = re.sub(rf"(?i)\b{re.escape(w)}\b", " ", q)
    return re.sub(r"\s+", " ", q).strip(" ?!,.") or (query or "").strip()


def _wikipedia_search(query: str, limit: int = 5, lang: str = "ru") -> list:
    try:
        search_q = _clean_search_query(query)
        r = requests.get(
            f"https://{lang}.wikipedia.org/w/api.php",
            params={
                "action": "opensearch",
                "search": search_q,
                "limit": limit,
                "namespace": 0,
                "format": "json",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=8,
        )
        r.raise_for_status()
        arr = r.json()
        titles = arr[1] if len(arr) > 1 else []
        descs = arr[2] if len(arr) > 2 else []
        urls = arr[3] if len(arr) > 3 else []
        out = []
        for i, title in enumerate(titles):
            out.append(
                {
                    "title": str(title)[:300],
                    "url": (urls[i] if i < len(urls) else "")[:1000],
                    "snippet": (descs[i] if i < len(descs) else "")[:500],
                    "source": f"wikipedia:{lang}",
                }
            )
        return out
    except Exception:
        return []


def _ddg_instant(query: str, limit: int = 5, timeout: int = 6) -> list:
    try:
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        )
        if not resp.content:
            return []
        data = resp.json()
    except Exception:
        return []
    results = []
    if data.get("AbstractText") or data.get("AbstractURL"):
        results.append(
            {
                "title": (data.get("Heading") or query)[:300],
                "url": (data.get("AbstractURL") or "")[:1000],
                "snippet": (data.get("AbstractText") or "")[:500],
                "source": data.get("AbstractSource") or "duckduckgo",
            }
        )
    for topic in data.get("RelatedTopics") or []:
        if len(results) >= limit:
            break
        if isinstance(topic, dict) and topic.get("Text"):
            results.append(
                {
                    "title": (topic.get("Text") or "")[:120],
                    "url": (topic.get("FirstURL") or "")[:1000],
                    "snippet": (topic.get("Text") or "")[:500],
                    "source": "duckduckgo",
                }
            )
        elif isinstance(topic, dict):
            for sub in topic.get("Topics") or []:
                if len(results) >= limit:
                    break
                if isinstance(sub, dict) and sub.get("Text"):
                    results.append(
                        {
                            "title": (sub.get("Text") or "")[:120],
                            "url": (sub.get("FirstURL") or "")[:1000],
                            "snippet": (sub.get("Text") or "")[:500],
                            "source": "duckduckgo",
                        }
                    )
    return results[:limit]


def web_open(url: str, timeout: int = DEFAULT_TIMEOUT, max_length: int = MAX_TEXT_CHARS) -> dict:
    """Открыть HTTP/HTTPS URL и вернуть читаемый текст."""
    t0 = time.time()
    valid, msg = _validate_url(url)
    if not valid:
        return _err("ValidationError", msg)
    url = msg
    timeout = max(1, min(int(timeout or DEFAULT_TIMEOUT), 60))
    max_length = max(100, min(int(max_length or MAX_TEXT_CHARS), MAX_TEXT_CHARS))

    bus.emit("WEB_REQUEST", {"tool": "web_open", "url": url[:300]}, source="web")
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            allow_redirects=True,
            stream=True,
        )
        # limit body
        content = b""
        for chunk in resp.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > MAX_BODY_BYTES:
                break
        charset = resp.encoding or "utf-8"
        try:
            text_raw = content.decode(charset, errors="replace")
        except Exception:
            text_raw = content.decode("utf-8", errors="replace")
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "html" in ctype or text_raw.lstrip().startswith("<"):
            readable = _extract_readable(text_raw, max_length)
        else:
            readable = text_raw[:max_length]
            if len(text_raw) > max_length:
                readable += "…"
        elapsed = round(time.time() - t0, 3)
        payload = {
            "url": url,
            "final_url": str(resp.url),
            "status": resp.status_code,
            "content_type": ctype,
            "text": readable,
            "length": len(readable),
            "elapsed": elapsed,
        }
        if resp.status_code >= 400:
            return {
                "ok": False,
                "data": payload,
                "error": {"type": "HTTPError", "message": f"HTTP {resp.status_code}"},
                "success": False,
                "error_message": f"HTTP {resp.status_code}",
            }
        return _ok(payload)
    except requests.Timeout:
        return _err("Timeout", f"web_open timeout ({timeout}s)")
    except requests.RequestException as e:
        return _err("NetworkError", str(e)[:500])


def web_fetch(url: str, method: str = "GET", timeout: int = DEFAULT_TIMEOUT) -> dict:
    """HTTP GET/HEAD: status, headers, ограниченное тело."""
    t0 = time.time()
    valid, msg = _validate_url(url)
    if not valid:
        return _err("ValidationError", msg)
    url = msg
    method = (method or "GET").upper()
    if method not in {"GET", "HEAD"}:
        return _err("ValidationError", "web_fetch поддерживает только GET/HEAD")
    timeout = max(1, min(int(timeout or DEFAULT_TIMEOUT), 60))

    bus.emit(
        "WEB_REQUEST",
        {"tool": "web_fetch", "url": url[:300], "method": method},
        source="web",
    )
    try:
        resp = requests.request(
            method,
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            allow_redirects=True,
            stream=True,
        )
        headers = {k: v for k, v in resp.headers.items()}
        body = None
        if method == "GET":
            content = b""
            for chunk in resp.iter_content(chunk_size=8192):
                content += chunk
                if len(content) > MAX_BODY_BYTES:
                    break
            try:
                body = content.decode(resp.encoding or "utf-8", errors="replace")
            except Exception:
                body = content.decode("utf-8", errors="replace")
            if len(body) > 50_000:
                body = body[:50_000] + "…"
        elapsed = round(time.time() - t0, 3)
        return _ok(
            {
                "url": url,
                "final_url": str(resp.url),
                "status": resp.status_code,
                "headers": headers,
                "body": body,
                "elapsed": elapsed,
            }
        )
    except requests.Timeout:
        return _err("Timeout", f"web_fetch timeout ({timeout}s)")
    except requests.RequestException as e:
        return _err("NetworkError", str(e)[:500])


def web_download(
    url: str,
    dest_name: str | None = None,
    timeout: int = 60,
) -> dict:
    """
    Скачать файл только в разрешённый каталог BERTA (~/.berta/downloads).
    Запрет произвольной записи в ФС.
    """
    from pathlib import Path

    t0 = time.time()
    valid, msg = _validate_url(url)
    if not valid:
        return _err("ValidationError", msg)
    url = msg
    timeout = max(1, min(int(timeout or 60), 120))

    downloads = Path.home() / ".berta" / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)

    if dest_name:
        # только basename, без path traversal
        dest_name = Path(dest_name).name
        if not dest_name or dest_name in {".", ".."}:
            return _err("ValidationError", "Некорректное имя файла")
    else:
        dest_name = Path(urlparse(url).path).name or f"download_{int(time.time())}"
        dest_name = re.sub(r"[^\w.\-]+", "_", dest_name)[:180]

    target = (downloads / dest_name).resolve()
    if not str(target).startswith(str(downloads.resolve())):
        return _err("SecurityError", "Путь вне разрешённого каталога downloads")

    bus.emit(
        "WEB_REQUEST",
        {"tool": "web_download", "url": url[:300], "dest": str(target)},
        source="web",
    )
    try:
        with requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            stream=True,
            allow_redirects=True,
        ) as resp:
            resp.raise_for_status()
            size = 0
            max_size = 50 * 1024 * 1024  # 50 MB
            with open(target, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    size += len(chunk)
                    if size > max_size:
                        f.close()
                        target.unlink(missing_ok=True)
                        return _err("SizeLimit", "Файл больше 50 МБ")
                    f.write(chunk)
        elapsed = round(time.time() - t0, 3)
        return _ok(
            {
                "url": url,
                "path": str(target),
                "size": size,
                "elapsed": elapsed,
            }
        )
    except requests.Timeout:
        return _err("Timeout", f"web_download timeout ({timeout}s)")
    except requests.RequestException as e:
        return _err("NetworkError", str(e)[:500])
    except OSError as e:
        return _err("IOError", str(e)[:500])


def weather(city: str | None = None, query: str | None = None) -> dict:
    """
    Погода: сначала Open-Meteo (обычно доступен из РФ), затем wttr.in (зарубежный запасной).
    """
    t0 = time.time()
    text = (city or query or "").strip()
    if not text:
        return _err(
            "ValidationError",
            "Укажите city или query (например «Москва» или «погода Чучково»)",
        )
    lookup_q = text if _looks_like_weather(text) else f"погода {text}"
    results = _weather_lookup(lookup_q)
    if not results:
        results = _weather_lookup(f"погода {text}")
    if not results:
        return _err(
            "NotFound",
            f"Не удалось получить погоду для «{text}». "
            "Проверьте доступ к open-meteo.com / wttr.in.",
        )
    best = results[0]
    bus.emit(
        "WEB_REQUEST",
        {"tool": "weather", "city": text[:100], "source": best.get("source")},
        source="web",
    )
    return _ok(
        {
            "city": _extract_city_for_weather(lookup_q),
            "summary": best.get("snippet", ""),
            "url": best.get("url", ""),
            "source": best.get("source"),
            "details": best.get("raw"),
            "results": results,
            "elapsed": round(time.time() - t0, 3),
        }
    )

