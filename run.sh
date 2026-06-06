#!/bin/bash
# ============================================
# KHANDHARS CHAT - Run Development Server
# Usage: bash run.sh
# ============================================

# Check venv exists
if [ ! -f "venv/bin/activate" ]; then
    echo "❌ Virtual environment not found."
    echo "   Run first: bash install.sh"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Set development environment
export FLASK_ENV=development
export FLASK_DEBUG=1

echo ""
echo "  ╔═══════════════════════════════════════╗"
echo "  ║       KHANDHARS CHAT Running          ║"
echo "  ╠═══════════════════════════════════════╣"
echo "  ║  App:   http://localhost:5000         ║"
echo "  ║  Admin: http://localhost:5000/admin   ║"
echo "  ║  Press Ctrl+C to stop                ║"
echo "  ╚═══════════════════════════════════════╝"
echo ""

python3 wsgi.py
