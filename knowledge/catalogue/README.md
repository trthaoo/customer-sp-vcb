# Product Catalogue Guide (US Market)

## Purpose
Guidelines on data schema specifications and how to add, inspect, and update jewelry pieces in the verified store catalogue.

## Product Schema Definition
Each product item in the catalogue conforms strictly to the following specification:
- `id` (string, required): Unique identifier of the product (e.g. "VCB_SP01").
- `name` (string, required): Official name of the handcrafted piece.
- `aliases` (array of strings): Recognized alternative names, search aliases, and descriptive keywords customers commonly use.
- `price` (number, nullable): Listed price of the item (null if unconfirmed or pending).
- `currency` (string, nullable): Currency code (e.g. "USD", "VND").
- `material` (string, nullable): Handcrafted precious metal and gemstone specification (e.g. "S925 Sterling Silver").
- `description` (string, nullable): Detailed English product description covering craftsmanship, stones, dimensions, spiritual symbolism, and styling/gifting occasions.
- `variants` (array of objects or strings, nullable): Available US ring sizes, chain lengths, or design options.
- `in_stock` (boolean, nullable): Stock availability (true: ready to ship, false: made-to-order / crafting in workshop, null: pending).
- `ship_note` (string, nullable): Fulfillment timeframes or specialized artisan packaging notes.
- `size_guide` (string, nullable): US standard sizing reference or dimensions guide.
- `url` (string, nullable): Link to the official studio product page.
- `image_url` (string, nullable): Hosted / static URL to the verified product image for visual reference and UI display.
- `image_path` (string, nullable): Local relative file path to the verified product image in the catalogue repository.
- `notes` (string, nullable): Internal context for studio hosts regarding spiritual symbolism, rotation mechanism, or craftsmanship details.

*Critical Grounding Rule: If any field is null or not found in the verified catalogue, the automated pipeline must never invent or assume facts.*

## TODO Sections
<!-- TODO: Integrate live inventory syncing with studio atelier ERP -->

<!-- EXAMPLE_DELETE_ME -->
EXAMPLE CONTENT THAT MUST BE COMPLETELY IGNORED BY LOADER:
```json
{
  "id": "SP_OLD_EXAMPLE_DELETE_ME",
  "name": "Old Sample Gold Ring",
  "aliases": ["old ring"],
  "price": 5000000,
  "currency": "VND",
  "material": "Hypothetical 24k Gold",
  "variants": ["Size 16"],
  "in_stock": true,
  "ship_note": "Ships immediately",
  "size_guide": "Measure circumference",
  "url": "https://example.com/old-sp",
  "notes": "Dead stock"
}
```
<!-- /EXAMPLE_DELETE_ME -->
