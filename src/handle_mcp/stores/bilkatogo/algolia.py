"""BilkaToGo's public Algolia index: one home for search (__init__.py) and nutrition.

Public keys from bilkatogo.dk's own JavaScript. Not secrets: every visitor's browser sends them.
"""

ALGOLIA = "https://f9vbjlr1bk-dsn.algolia.net/1/indexes/*/queries"
ALGOLIA_HEADERS = {
    "x-algolia-application-id": "F9VBJLR1BK",
    "x-algolia-api-key": "1deaf41c87e729779f7695c00f190cc9",  # public search-only key
}
ALGOLIA_INDEX = "prod_BILKATOGO_PRODUCTS"
