#!/bin/bash
# ============================================
# KHANDHARS CHAT - One-Command Mac Installer
# Usage: bash install.sh
# ============================================

set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║    KHANDHARS CHAT - Mac Installer 🚀    ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── Python Check ──────────────────────────────
echo -e "${BLUE}▶ Checking Python...${NC}"
if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 --version 2>&1)
    echo -e "${GREEN}  ✅ $PY_VERSION${NC}"
    PYTHON=python3
else
    echo -e "${RED}  ❌ Python 3 not found.${NC}"
    echo "  Install from: https://www.python.org/downloads/"
    exit 1
fi

# ── Virtual Environment ───────────────────────
echo -e "${BLUE}▶ Setting up virtual environment...${NC}"
if [ ! -d "venv" ]; then
    $PYTHON -m venv venv
    echo -e "${GREEN}  ✅ venv created${NC}"
else
    echo -e "${YELLOW}  ⚠️  venv already exists${NC}"
fi
source venv/bin/activate

# ── pip upgrade ───────────────────────────────
echo -e "${BLUE}▶ Upgrading pip...${NC}"
pip install --upgrade pip --quiet 2>&1 | tail -1
echo -e "${GREEN}  ✅ pip ready${NC}"

# ── Install packages ──────────────────────────
echo -e "${BLUE}▶ Installing packages (2-3 min)...${NC}"
pip install -r requirements.txt --quiet
echo -e "${GREEN}  ✅ All packages installed${NC}"

# ── .env setup ────────────────────────────────
echo -e "${BLUE}▶ Creating .env configuration...${NC}"
if [ ! -f ".env" ]; then
    cp .env.example .env
    # Generate random secret keys automatically
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    # macOS sed syntax
    sed -i '' "s|CHANGE_THIS_TO_A_RANDOM_64_CHAR_STRING|$SECRET|g" .env
    sed -i '' "s|CHANGE_THIS_TO_ANOTHER_RANDOM_STRING|$JWT_SECRET|g" .env
    echo -e "${GREEN}  ✅ .env created with auto-generated keys${NC}"
else
    echo -e "${YELLOW}  ⚠️  .env already exists (keeping it)${NC}"
fi

# ── Database ──────────────────────────────────
echo -e "${BLUE}▶ Setting up database...${NC}"
# Default is SQLite - no setup needed
if grep -q "sqlite" .env; then
    echo -e "${GREEN}  ✅ Using SQLite (development mode - no setup needed)${NC}"
elif command -v psql &>/dev/null; then
    echo -e "${YELLOW}  Trying PostgreSQL...${NC}"
    createdb khandhars_chat 2>/dev/null && echo -e "${GREEN}  ✅ PostgreSQL database created${NC}" || echo -e "${YELLOW}  ⚠️  DB may already exist${NC}"
else
    echo -e "${YELLOW}  ⚠️  PostgreSQL not found, using SQLite${NC}"
    sed -i '' 's|DATABASE_URL=postgresql://.*|DATABASE_URL=sqlite:///khandhars_dev.db|' .env
fi

echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║     ✅ Installation Complete!            ║${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BOLD}Start the app:${NC}"
echo -e "  ${GREEN}bash run.sh${NC}"
echo ""
echo -e "${BOLD}Then open:${NC}"
echo -e "  App:    ${BLUE}http://localhost:5000${NC}"
echo -e "  Admin:  ${BLUE}http://localhost:5000/admin/login${NC}"
echo ""
echo -e "${BOLD}Admin credentials:${NC}"
echo -e "  Username: ${YELLOW}admin${NC}"
echo -e "  Password: ${YELLOW}ChangeMe123!${NC}"
echo -e "  ${RED}(Change password in Admin > Settings after login)${NC}"
echo ""
