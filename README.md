# Kai- (KaiJakLike SMM Bot) — v12

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
