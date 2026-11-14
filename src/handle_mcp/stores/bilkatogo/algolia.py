"""BilkaToGo's public Algolia index: one home for search (__init__.py) and nutrition.

Public keys from bilkatogo.dk's own JavaScript. Not secrets: every visitor's browser sends them.
"""

ALGOLIA = "https://f9vbjlr1bk-dsn.algolia.net/1/indexes/*/queries"
ALGOLIA_HEADERS = {
    "x-algolia-application-id": "F9VBJLR1BK",
    "x-algolia-api-key": "1deaf41c87e729779f7695c00f190cc9",  # public search-only key
}
ALGOLIA_INDEX = "prod_BILKATOGO_PRODUCTS"

# A shared category (stores.OFFER_CATEGORIES) is one or more top levels of the tree behind
# `deepestCategoryPath`, `consumerFacingHierarchy.lvl0` (live 2026-11-14). The other tree,
# `categories`, puts cold-cut salads under fruit. "Mejeri & køl" holds the cold cuts too.
OFFER_CATEGORIES = {
    "frugt og grønt": ("Frugt & grønt",),
    "kød og fisk": ("Kød & fisk",),
    "mejeri og æg": ("Mejeri & køl",),
    "pålæg": ("Mejeri & køl",),
    "brød og kager": ("Brød & kager",),
    "kolonial": ("Kolonial", "Mad fra hele verden"),
    "frost": ("Frost",),
    "drikkevarer": ("Drikkevarer",),
    "slik og snacks": ("Slik & snacks",),
    "husholdning": ("Husholdning",),
    "pleje": ("Personlig pleje",),
    "baby": ("Baby & børn",),
}


def category_filter(category: str) -> str:
    names = OFFER_CATEGORIES[category]
    return "(" + " OR ".join(f'consumerFacingHierarchy.lvl0:"{n}"' for n in names) + ")"
