# Kai- (KaiJakLike SMM Bot) — v12

## ណែនាំមិត្ត (Referral) — Bot master ប៉ុណ្ណោះ

- ម៉ឺនុយ **🎁 ណែនាំមិត្ត** → ទទួលតំណ `t.me/<bot>?start=ref<uid>` + ប៊ូតុងចែករំលែក
- មិត្តចូលតាមតំណ ហើយ **ដាក់លុយចាប់ពី $1 ឡើង** → អ្នកណែនាំទទួល **5%** ភ្លាមៗ ចូល Balance
- ដាក់ក្រោម $1 = គ្មានកម្រៃ · ភ្ជាប់បានតែម្តង · ណែនាំខ្លួនឯងមិនបាន
- Env (ជម្រើស): `REFERRAL_RATE` (default 0.05), `REFERRAL_MIN_DEPOSIT` (default 1)

## v12: Multi SMM API (ភ្ជាប់ Website API បានច្រើន)

Admin → **⚙️ កំណត់ SMM API**
- ➕ បន្ថែម Website API (URL + Key) បានគ្មានកំណត់
- ចុចលើ Website នីមួយៗ → 🔌 សាកល្បង/Balance · ✏️ កែ · 🏷️ ប្តូរឈ្មោះ · ⭐ Default · 🔴/🟢 បិទ/បើក · 🗑️ លុប
- **➕ បន្ថែម SMM** → ជ្រើស Category → Platform → **ជ្រើស Website** → ដាក់ Service IDs
- **💰 ឆែកលុយ API** → បង្ហាញ Balance គ្រប់ Website ម្តង
- Order / Status / Refill ទៅតាម Website របស់ Service នោះ (ច្រលំគ្នាមិនបាន)
- Website 1 ចាស់ត្រូវ migrate ស្វ័យប្រវត្តិទៅជា `p1` (Service + Order ចាស់នៅដដែល)

Data ថ្មី: `smm_providers.json` (មាន API Key — ត្រូវបាន ignore ក្នុង `.gitignore`)

## Env vars
BOT_TOKEN, ADMIN_ID, CAMRAPID_API_KEY, ... (មើល `render.yaml`)
