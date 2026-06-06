#!/bin/bash
# ============================================
# KHANDHARS CHAT - Mac Setup Script
# Run: bash setup_mac.sh
# ============================================

set -e  # Exit on any error

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "╔══════════════════════════════════════╗"
echo "║      KHANDHARS CHAT - Setup          ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ─── Step 1: Check Python ─────────────────────
echo -e "${BLUE}[1/7] Checking Python...${NC}"
if command -v python3 &>/dev/null; then
    PYTHON=python3
    echo -e "${GREEN}✅ Python3 found: $(python3 --version)${NC}"
else
    echo -e "${RED}❌ Python3 not found. Install from https://python.org${NC}"
    exit 1
fi

# ─── Step 2: Create Virtual Environment ───────
echo -e "${BLUE}[2/7] Creating virtual environment...${NC}"
if [ ! -d "venv" ]; then
    $PYTHON -m venv venv
    echo -e "${GREEN}✅ Virtual environment created${NC}"
else
    echo -e "${YELLOW}⚠️  Virtual environment already exists, skipping${NC}"
fi

# ─── Step 3: Activate venv ────────────────────
echo -e "${BLUE}[3/7] Activating virtual environment...${NC}"
source venv/bin/activate
echo -e "${GREEN}✅ Virtual environment activated${NC}"

# ─── Step 4: Upgrade pip ──────────────────────
echo -e "${BLUE}[4/7] Upgrading pip...${NC}"
pip install --upgrade pip --quiet
echo -e "${GREEN}✅ pip upgraded${NC}"

# ─── Step 5: Install dependencies ─────────────
echo -e "${BLUE}[5/7] Installing Python packages (this may take 2-3 minutes)...${NC}"
pip install -r requirements.txt --quiet
echo -e "${GREEN}✅ All packages installed${NC}"

# ─── Step 6: Setup .env ───────────────────────
echo -e "${BLUE}[6/7] Setting up environment config...${NC}"
if [ ! -f ".env" ]; then
    cp .env.example .env
    # Generate random secret keys
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i '' "s/your-super-secret-key-change-this-in-production-use-64-chars/$SECRET/" .env
    sed -i '' "s/your-jwt-secret-key-change-this-too/$JWT_SECRET/" .env
    echo -e "${GREEN}✅ .env created with auto-generated secret keys${NC}"
    echo -e "${YELLOW}⚠️  Edit .env to set your DATABASE_URL and other settings${NC}"
else
    echo -e "${YELLOW}⚠️  .env already exists, skipping${NC}"
fi

# ─── Step 7: Check PostgreSQL ─────────────────
echo -e "${BLUE}[7/7] Checking PostgreSQL...${NC}"
if command -v psql &>/dev/null; then
    echo -e "${GREEN}✅ PostgreSQL found${NC}"
    # Try to create database
    echo -e "${YELLOW}   Attempting to create database 'khandhars_chat'...${NC}"
    createdb khandhars_chat 2>/dev/null && echo -e "${GREEN}✅ Database created${NC}" || echo -e "${YELLOW}⚠️  Database may already exist or needs manual creation${NC}"
else
    echo -e "${YELLOW}⚠️  PostgreSQL not found. Using SQLite for development...${NC}"
    # Set SQLite as fallback in .env
    sed -i '' 's|DATABASE_URL=postgresql://.*|DATABASE_URL=sqlite:///khandhars_dev.db|' .env
    echo -e "${GREEN}✅ Switched to SQLite (development mode)${NC}"
fi

echo ""
echo "╔══════════════════════════════════════╗"
echo "║         Setup Complete! 🎉           ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo ""
echo "  1. Edit your .env file (optional, SQLite is ready):"
echo "     nano .env"
echo ""
echo "  2. Start the server:"
echo "     ${GREEN}bash run.sh${NC}"
echo ""
echo "  3. Open in browser:"
echo "     ${GREEN}http://localhost:5000${NC}"
echo ""
echo "  4. Admin panel:"
echo "     ${GREEN}http://localhost:5000/admin/login${NC}"
echo "     Username: admin"
echo "     Password: ChangeMe123! (change this!)"
echo ""
