import requests
import time

class eBayAPIScraper:
    def __init__(self, api_key, pause_between_calls=2):
        self.api_key = api_key
        self.api_calls = 0  # track usage
        self.pause = pause_between_calls  # seconds to wait between calls

    def scrape_sold_prices(self, query, exclude_keywords=None, max_items=100):
        """
        Returns a list of sold/completed item prices for a single query.
        Automatically pages through results in increments of 25 items per request.
        """
        url = "https://svcs.ebay.com/services/search/FindingService/v1"
        headers = {"X-EBAY-SOA-SECURITY-APPNAME": self.api_key}

        prices = []
        items_per_page = 25
        pages_needed = (max_items + items_per_page - 1) // items_per_page  # ceil division

        for page in range(1, pages_needed + 1):
            params = {
                "OPERATION-NAME": "findCompletedItems",
                "SERVICE-VERSION": "1.0.0",
                "RESPONSE-DATA-FORMAT": "JSON",
                "REST-PAYLOAD": "",
                "keywords": query,
                "itemFilter(0).name": "SoldItemsOnly",
                "itemFilter(0).value": "true",
                "paginationInput.entriesPerPage": items_per_page,
                "paginationInput.pageNumber": page
            }

            try:
                r = requests.get(url, params=params, headers=headers, timeout=15)
                self.api_calls += 1

                if r.status_code == 200:
                    data = r.json()
                    items = data.get("findCompletedItemsResponse", [{}])[0]\
                                .get("searchResult", [{}])[0]\
                                .get("item", [])

                    for item in items:
                        title = item.get("title", "").lower()
                        if exclude_keywords and any(kw in title for kw in exclude_keywords):
                            continue
                        try:
                            price = float(item["sellingStatus"]["currentPrice"]["__value__"])
                            prices.append(price)
                        except:
                            continue

                    # Stop early if we've reached max_items
                    if len(prices) >= max_items:
                        prices = prices[:max_items]
                        break

                else:
                    print("API error:", r.status_code, r.text[:200])
                    break

            except Exception as e:
                print("API request failed:", e)
                break

            time.sleep(self.pause)  # pause between calls

        return prices

    def bulk_search(self, queries, exclude_keywords=None, max_items=100):
        """
        Returns a dictionary {query: [prices]} for multiple queries.
        """
        results = {}
        for q in queries:
            results[q] = self.scrape_sold_prices(q, exclude_keywords=exclude_keywords, max_items=max_items)
            time.sleep(self.pause)  # optional pause between queries
        return results
