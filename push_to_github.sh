#!/data/data/com.termux/files/usr/bin/bash
# ប្រើក្នុង Termux:  bash push_to_github.sh "សារ commit"
# ត្រូវដាក់ឯកសារថ្មី (kaijaklike_bot.py ។ល។) ក្នុង folder ~/Kai- ជាមុន
set -e
cd ~/Kai- || { echo "❌ រក folder ~/Kai- មិនឃើញ"; exit 1; }
MSG="${1:-v12: Multi SMM API (Website API ច្រើន)}"

python -m py_compile kaijaklike_bot.py && echo "✅ syntax OK"

# ការពារ: កុំ push data/secret
if git ls-files | grep -qE '(^|/)smm_.*\.json$|\.env$'; then
  echo "⚠️ ឃើញ data/secret ក្នុង git! លុបចេញពី tracking:"
  git ls-files | grep -E '(^|/)smm_.*\.json$|\.env$'
  git ls-files | grep -E '(^|/)smm_.*\.json$|\.env$' | xargs git rm --cached -q
fi

git add kaijaklike_bot.py README.md .gitignore render.yaml requirements.txt requirements-bot.txt
git status --short
git commit -m "$MSG" || echo "ℹ️ គ្មានអ្វីត្រូវ commit"
git pull --rebase origin main
git push origin main
echo "✅ Push ជោគជ័យ"
