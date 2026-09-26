# shop

Core domain logic for a small storefront. Pure Python, no runtime dependencies.

| Module | What it does |
| --- | --- |
| `shop.money` | Decimal conversion and rounding to cents (half-up) |
| `shop.pricing` | Line totals: unit price x quantity, with volume tiers (5% from 10 units, 10% from 50, 15% from 100) |
| `shop.discounts` | Percentage and fixed coupons: minimum spend, expiry date, stacking rules |
| `shop.tax` | Sales tax by region (CA, NY, TX, OR), grocery exemptions |
| `shop.cart` | Add / remove / update lines, checkout totals |
| `shop.inventory` | In-memory stock with per-order reservations |

Nothing reads the system clock: functions that care about dates take `today` as an argument.

```python
from datetime import date
from shop import Cart, Coupon, PERCENT

cart = Cart()
cart.add("TSHIRT-M", "19.99", qty=2)
cart.add("MUG", "8.50")
totals = cart.checkout_totals("CA", today=date(2024, 6, 1),
                              coupons=[Coupon("SUMMER10", PERCENT, 10)])
```

## Development

```bash
pip install -e '.[test]'
pytest
```
