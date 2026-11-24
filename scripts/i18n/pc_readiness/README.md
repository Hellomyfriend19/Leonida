# PC check UI strings

English (`en.json`) is the master list of keys. Add or update a locale by copying every key from `en.json` into
`<code>.json` under the same directory (same codes as [`docs/i18n/README.md`](../../../docs/i18n/README.md)).

Run the check in a locale:

```text
python -I scripts/pc_readiness.py --lang de
set LEONIDA_LANG=ru
python -I scripts/pc_readiness.py
```

Missing keys in a locale fall back to the English string.

Shipped locales: `en`, `de`, `ru`. Copy `en.json` to add more.