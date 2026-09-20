"""unito26 — course package for Python for Finance (University of Turin, 2026).

Modules are added here as they are built (e.g. constants, models, pricers).

Subpackages
-----------
``unito26.lob``
    Limit order books: folding a stream of orders into a book, the performance
    ladder over the best-price lookup, and Hawkes order flow to drive them.
"""

from unito26 import lob

__all__ = ["lob"]
