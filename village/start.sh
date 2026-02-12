# start.sh
#!/bin/bash
set -e

cd /app/village || cd /app || true

echo "========================================="
echo "🚀 VILLAGE FARM BOT - STARTUP"
echo "========================================="

echo "📦 Installing dependencies..."
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt > /dev/null 2>&1
echo "✅ Dependencies installed"

echo ""
echo "🤖 Starting bot..."
echo "========================================="
exec python -m app.main