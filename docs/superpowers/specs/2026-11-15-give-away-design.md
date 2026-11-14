# Design: give recyclables or compost away free (short design)

## Intent
When something leaves the MRF, the operator chooses **Sell** (with a price) or **Give free** (no price), for recyclables and for compost. Today:
- Recyclables can't leave free at all, because a sale needs a price.
- Compost on the kiosk is always free, even though the website allows a price.

## Approaches
- **A. A new outgoing kind, "Given away" (chosen by the user).** Reports show it apart from sales, income is untouched, and the admin reviews it like any outgoing. Needs a small database change.
- **B. A sale with no price.** Rejected: reports would lump free give-aways in with sales ("Sold 40 kg" when 12 kg were free).

## Decided
- **Outgoing kinds:**
  - **sale:** material, area, price (required)
  - **giveaway (new):** material, area, no price
  - **compost:** price optional (price = sold, no price = given free)
  - **disposal:** unchanged
- **Labels:** "Recyclables given away" on the website and in reports. "Given away: 12 kg" this month on Outgoing, next to Sold, Compost given out and Residual disposed.
- **Rules:**
  - A giveaway takes stock at once (like a sale), and the admin reviews it (OK / Reverse).
  - Income is unaffected (no total).
  - The API refuses a price on a giveaway, and refuses a giveaway with no material or area.

## Kiosk (my calls: check these)
- **The first tab** on the Sell screen is renamed **Sale → Recyclables**. Tabs: Recyclables / Compost / Residual.
- **The form** gets a two-button switch at the top of the left column: **Sell** | **Give free**. It shows for Recyclables and Compost, never for Residual.
- **Default is Sell for recyclables** (the price starts at the last sale) and **Give free for compost** (what happens today).
- **Give free** hides the price row. Save reads "Save · 2 kg · free". The receipt says **"Given free"** instead of a total.
- **Compost sold:** the price starts empty (there's no "last compost price" yet). Save asks for it like a sale.

## Website
- The operator/admin "Record outgoing" form gets the type **Recyclables given away** (material + area, no price).
- **Compost:** the price stays optional, with the hint "leave empty if given free".

## Not changing
Residual disposal; how review and reverse work; past records.

## Left to the builder
Migration naming; exact strings in both languages; test cases following the existing outgoing tests.
