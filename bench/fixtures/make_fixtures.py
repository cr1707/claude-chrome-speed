#!/usr/bin/env python3
"""Generate the catalogue data for catalog.html and print every fixture's expected answer.

Deterministic: run it again and you get the same files and answers.
"""
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "catalog"
PER_PAGE = 20
PAGES = 6

ADJ = ["Arden", "Bramble", "Cove", "Dune", "Ember", "Fjord", "Glade", "Harbor", "Isle", "Juniper",
       "Kestrel", "Linden", "Moss", "Nordic", "Oak", "Pebble", "Quarry", "Ridge", "Slate", "Tide"]
NOUN = {
    "Lighting": ["Table Lamp", "Floor Lamp", "Pendant", "Wall Sconce", "Desk Lamp"],
    "Seating": ["Armchair", "Stool", "Bench", "Lounge Chair", "Dining Chair"],
    "Storage": ["Shelf", "Cabinet", "Sideboard", "Bookcase", "Chest"],
    "Tables": ["Side Table", "Coffee Table", "Desk", "Console", "Dining Table"],
    "Textiles": ["Throw", "Cushion", "Rug", "Curtain", "Blanket"],
}


def build():
    rng = random.Random(1707)
    items, used = [], set()
    for i in range(PER_PAGE * PAGES):
        cat = rng.choice(list(NOUN))
        while True:
            name = f"{rng.choice(ADJ)} {rng.choice(NOUN[cat])}"
            if name not in used:
                used.add(name)
                break
        # Ordinary items: never cheaper than 60 when they are well-rated Lighting.
        price = round(rng.uniform(60, 420), 2)
        rating = round(rng.uniform(2.6, 5.0), 1)
        items.append({"name": name, "category": cat, "price": price, "rating": rating})

    def place(idx, name, cat, price, rating):
        items[idx] = {"name": name, "category": cat, "price": price, "rating": rating}

    # The answer: three cheap, well-rated Lighting items, deep in the list (pages 3, 5 and 6).
    place(47, "Lumen Clip Lamp", "Lighting", 24.90, 4.3)
    place(91, "Halo Mini Pendant", "Lighting", 31.50, 4.6)
    place(113, "Wren Reading Lamp", "Lighting", 27.75, 4.1)
    # Decoys on page 1: cheaper Lighting, but rated below 4.
    place(4, "Spark Bulb Lamp", "Lighting", 14.99, 3.9)
    place(12, "Glint Night Light", "Lighting", 19.50, 3.4)
    # Decoy: cheap and well-rated, but not Lighting.
    place(66, "Pine Plant Stand", "Storage", 12.00, 4.8)
    return items


def main():
    items = build()
    OUT.mkdir(exist_ok=True)
    for p in range(PAGES):
        chunk = items[p * PER_PAGE:(p + 1) * PER_PAGE]
        payload = {"page": p + 1, "pages": PAGES, "total": len(items), "items": chunk}
        (OUT / f"page-{p + 1}.json").write_text(json.dumps(payload, indent=1) + "\n")

    best = sorted((i for i in items if i["category"] == "Lighting" and i["rating"] >= 4.0),
                  key=lambda i: i["price"])[:3]
    print("catalog:", [(b["name"], b["price"]) for b in best])

    # Supplier quotes (prices are written in the HTML; this mirrors the rules on each page).
    qty = 40
    a = qty * 16.90 + 45                      # tier 25-49 units, flat shipping
    b_sub = qty * 16.20                       # 10% off only from 50 units
    b = b_sub + qty * 2.10
    c_sub = qty * 17.40                       # free shipping over 600, handling fee in the notes
    c = c_sub + 12
    print(f"suppliers: Northline {a:.2f}  Varga {b:.2f}  Kestrel {c:.2f}")

    # App-style form: same FNV-1a hash as spa-form.html, over the normalised state.
    state = {"name": "Lena Fischer", "email": "lena.fischer@example.com", "company": "Brightpath",
             "plan": "Growth", "seats": "7", "annual": "yes", "start": "2026-11-02",
             "notes": "Invoice to finance team."}
    s = json.dumps(state, separators=(",", ":"), ensure_ascii=False)
    h = 0x811C9DC5
    for ch in s:
        h ^= ord(ch)
        h = (h * 0x01000193) & 0xFFFFFFFF
    print(f"spa-form code: {h:08X}")


if __name__ == "__main__":
    main()
