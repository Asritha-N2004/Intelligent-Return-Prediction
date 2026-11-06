# Synthetic data dictionary

All records are generated, not collected. Currency: INR. Dates: ISO 8601. Seed: 42.

| Field | Meaning | Prediction input |
|---|---|---|
| order_id | Unique synthetic transaction identifier | Reference only |
| customer_id | Synthetic customer identifier | Reference only |
| product_id | Synthetic catalog identifier | Reference only |
| product_category | Apparel, Electronics, Footwear, Home, Beauty, Sports | Yes |
| product_price | Unit list price, INR | Yes |
| quantity | Units ordered | Yes |
| order_date | Synthetic purchase date | No |
| delivery_date | Observed synthetic delivery date | Policy only |
| payment_method | Card, UPI, Cash on delivery | Yes |
| customer_location | One of six Indian cities | Yes |
| product_rating | Catalog rating, 0–5 | Yes |
| product_review_score | Duplicate catalog rating proxy | No |
| discount_percentage | Discount from list price | Yes |
| previous_orders | Prior purchase snapshot | Yes |
| previous_returns | Prior return snapshot | Yes |
| customer_return_rate | Prior returns / prior orders | Recomputed |
| delivery_delay | Delay in days, available after delivery | Yes |
| product_condition | Post-return condition | No |
| return_reason | Observed return feedback | No |
| return_requested | Binary target | Target only |
| return_date | Return request date, nullable | No |
| refund_amount | Synthetic historical refund | No |
| shipping_cost | Historical shipping estimate | No |
| warehouse_id | Historical facility allocation | No |
| return_processing_time | Post-return processing days | No |
| product_resale_value | Post-return valuation | No |

Engineered inputs: order value; smoothed historical risk `(returns+1)/(orders+5)`; delivery performance `1/(1+delay)`; log prior-order count as a purchase-frequency proxy; fixed price bucket. Actual purchase intervals, lifetime revenue, inspection quality and behavioral trends cannot be inferred from this snapshot and are not fabricated as model inputs.
