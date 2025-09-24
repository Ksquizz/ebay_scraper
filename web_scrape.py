import requests, re, time, random
import numpy as np

from bs4 import BeautifulSoup
from urllib.parse import quote

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0 Safari/537.36',
]

def random_headers():
    return {"User-Agent": random.choice(USER_AGENTS)}

def smart_sleep(min_s=1.0, max_s=3.0, verbose=False):
    delay = random.uniform(min_s, max_s)
    if verbose:
        print(f"   → Sleeping {delay:.2f}s to avoid detection")
    time.sleep(delay)

def build_search_url(query, page=1, site="co.uk"):
    base = f"https://www.ebay.{site}/sch/i.html"
    params = [f"_nkw={quote(query)}", "LH_Sold=1", "LH_Complete=1", f"_pgn={page}", "_ipg=100"]
    return base + "?" + "&".join(params)

PRICE_REGEX = re.compile(r'([£$€])\s?([\d{1,3},]*\d+(?:\.\d+)?)')

def parse_price_text(text):
    text = text.replace(",", "")
    prices = []
    for m in PRICE_REGEX.finditer(text):
        try:
            prices.append(float(m.group(2)))
        except:
            continue
    return prices

def parse_listings_for_prices(html, exclude_keywords=None, verbose=False):
    soup = BeautifulSoup(html, "html.parser")

    items = soup.select(".s-item")
    if verbose:
        print(f"   → Found {len(items)} item blocks")

    results = []
    exclude_keywords = [k.lower() for k in (exclude_keywords or [])]

    for item in items:
        title = item.select_one(".s-item__title")
        title_text = title.get_text(strip=True) if title else ""

        # skip ads / templates
        if not title_text or "shop on ebay" in title_text.lower():
            continue

        if any(kw in title_text.lower() for kw in exclude_keywords):
            continue

        # Price selectors can vary
        price_tag = (
            item.select_one(".s-item__price") or
            item.select_one(".s-item__detail--primary") or
            item.find("span", string=re.compile(r"[£$€]"))
        )
        if not price_tag:
            continue

        prices = parse_price_text(price_tag.get_text())
        results.extend(prices)

    if verbose:
        print(f"   → Extracted {len(results)} prices")

    return results

def make_request(url, retries=3, verbose=False, base_timeout=15):
    timeout = base_timeout
    for attempt in range(retries):
        try:
            if verbose:
                print(f"   → Fetching {url} (attempt {attempt+1}, timeout={timeout}s)")
            r = requests.get(url, headers=random_headers(), timeout=timeout)

            if r.status_code == 200:
                # check for bot-detection text in HTML
                txt = r.text.lower()
                if any(kw in txt for kw in ["captcha", "access denied", "verify you are human"]):
                    print("⚠️ Detected bot-block page. Waiting 60s...")
                    time.sleep(60)
                    continue
                return r

            elif r.status_code == 503:
                print("⚠️ Blocked by eBay (503). Waiting 60s before retry...")
                time.sleep(60)
                continue

            else:
                if verbose:
                    print(f"   → Non-200 status: {r.status_code}")

        except requests.exceptions.ReadTimeout:
            print(f"⚠️ Request timed out after {timeout}s.")
            new_val = input("Enter new timeout (e.g. 30 or 45) or press Enter to skip: ").strip()
            if new_val.isdigit():
                timeout = int(new_val)
                print(f"   → Retrying with timeout={timeout}s (after short pause)...")
                time.sleep(3)
                continue
            else:
                print("   → Skipping this request.")
                return None

        except Exception as e:
            if verbose:
                print(f"   → Request error: {e}")

        # Exponential backoff
        wait = 5 * (attempt + 1)
        print(f"   → Waiting {wait}s before retry...")
        time.sleep(wait)

    return None

def scrape_sold_prices(query, pages=1, exclude_keywords=None, verbose=False):
    all_prices = []
    for p in range(1, pages+1):
        url = build_search_url(query, page=p)
        if verbose: print(f"\nProcessing query '{query}' page {p}/{pages}")
        if verbose: print(f"   → URL: {url}")

        resp = make_request(url, verbose=verbose)
        if not resp:
            if verbose: print("   → Request failed, skipping page")
            continue

        prices = parse_listings_for_prices(resp.text, exclude_keywords=exclude_keywords, verbose=verbose)
        all_prices.extend(prices)
        smart_sleep(verbose=verbose)

    return all_prices

def filter_outliers(prices):
    if not prices: return [], None, None
    arr = np.array(prices)
    if arr.size < 3:
        return prices, float(np.mean(arr)), float(np.std(arr))
    q1, q3 = np.percentile(arr, [25, 75])
    iqr = q3 - q1
    lower, upper = q1 - 1.5*iqr, q3 + 1.5*iqr
    filtered = arr[(arr >= lower) & (arr <= upper)]
    mean = float(np.mean(filtered)) if filtered.size else float(np.mean(arr))
    std = float(np.std(filtered)) if filtered.size else float(np.std(arr))
    return filtered.tolist(), mean, std
