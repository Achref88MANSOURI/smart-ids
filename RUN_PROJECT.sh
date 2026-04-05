#!/bin/bash

###############################################################################
# 🚀 SMART-IDS RUN SCRIPT
# Complete startup of all microservices
###############################################################################

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           🚀 SMART-IDS PROJECT LAUNCHER v5.0                 ║"
echo "║         Network IDS + Endpoint Detection + LLM Analysis       ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

###############################################################################
# SECTION 1: PRE-FLIGHT CHECKS
###############################################################################

echo "📋 PRE-FLIGHT CHECKS..."
echo ""

# Check Elasticsearch
echo -n "  ✓ Elasticsearch: "
if curl -s http://10.0.1.7:9200 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Connected${NC}"
else
    echo -e "${RED}❌ Not reachable${NC}"
    echo "    Start Elasticsearch: systemctl start elasticsearch"
    exit 1
fi

# Check .env
echo -n "  ✓ Configuration (.env): "
if [ -f .env ]; then
    echo -e "${GREEN}✅ Found${NC}"
else
    echo -e "${RED}❌ Missing${NC}"
    echo "    Create .env with required API keys"
    exit 1
fi

# Check Python venv
echo -n "  ✓ ML Environment (venv_ml): "
if [ -d venv_ml ] && [ -f venv_ml/bin/python ]; then
    echo -e "${GREEN}✅ Ready${NC}"
else
    echo -e "${RED}❌ Not found${NC}"
    exit 1
fi

# Check Frontend
echo -n "  ✓ Frontend (React): "
if [ -d dashboard/frontend/node_modules ]; then
    echo -e "${GREEN}✅ Dependencies OK${NC}"
else
    echo -e "${YELLOW}⚠️  Installing dependencies...${NC}"
    cd dashboard/frontend
    npm install > /dev/null 2>&1
    cd - > /dev/null
    echo "    ✅ Dependencies installed"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo ""

###############################################################################
# SECTION 2: START SERVICES
###############################################################################

echo "🚀 STARTING SERVICES..."
echo ""

# 1. Enrichment Service (ML Pipeline)
echo "  [1/3] 🧠 ML Enrichment Service..."
if systemctl is-active --quiet smart-ids-enrichment; then
    echo -e "        ${YELLOW}Already running${NC}"
else
    systemctl start smart-ids-enrichment > /dev/null 2>&1
    sleep 2
    if systemctl is-active --quiet smart-ids-enrichment; then
        echo -e "        ${GREEN}✅ Started${NC}"
    else
        echo -e "        ${RED}❌ Failed to start${NC}"
        journalctl -u smart-ids-enrichment -n 20 --no-pager
        exit 1
    fi
fi

# 2. Backend API (FastAPI)
echo "  [2/3] 📡 Dashboard API (FastAPI)..."
pgrep -f "uvicorn.*backend:app" > /dev/null 2>&1 && pkill -f "uvicorn.*backend:app"; sleep 1

source venv/bin/activate 2>/dev/null || source venv_ml/bin/activate
cd dashboard

nohup uvicorn backend:app --host 0.0.0.0 --port 8080 > backend.log 2>&1 &
sleep 3

if curl -s http://localhost:8080/api/health > /dev/null 2>&1; then
    echo -e "        ${GREEN}✅ Started${NC} (Port 8080)"
else
    echo -e "        ${RED}❌ Failed to start${NC}"
    tail -20 backend.log
    exit 1
fi

cd - > /dev/null

# 3. Frontend (React)
echo "  [3/3] 🎨 Dashboard UI (React)..."
pgrep -f "react-scripts.*start" > /dev/null 2>&1 && pkill -f "react-scripts.*start"; sleep 1

cd dashboard/frontend
export REACT_APP_API_URL="http://localhost:8080"
nohup npm start > frontend.log 2>&1 &
sleep 5

if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo -e "        ${GREEN}✅ Started${NC} (Port 3000)"
else
    echo -e "        ${YELLOW}⚠️  Starting (takes ~30s)...${NC}"
    tail -10 frontend.log
fi

cd - > /dev/null

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo ""

###############################################################################
# SECTION 3: SERVICE STATUS
###############################################################################

echo "📊 SERVICE STATUS:"
echo ""

# Enrichment
echo -n "  🧠 ML Enrichment: "
systemctl is-active --quiet smart-ids-enrichment && echo -e "${GREEN}✅ Running${NC}" || echo -e "${RED}❌ Stopped${NC}"

# Backend
echo -n "  📡 Backend API: "
curl -s http://localhost:8080/api/health > /dev/null 2>&1 && echo -e "${GREEN}✅ Running${NC}" || echo -e "${RED}❌ Stopped${NC}"

# Frontend
echo -n "  🎨 Frontend UI: "
curl -s http://localhost:3000 > /dev/null 2>&1 && echo -e "${GREEN}✅ Running${NC}" || echo -e "${RED}❌ Starting${NC}"

# Elasticsearch
echo -n "  📦 Elasticsearch: "
curl -s http://10.0.1.7:9200 > /dev/null 2>&1 && echo -e "${GREEN}✅ Connected${NC}" || echo -e "${RED}❌ Down${NC}"

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo ""

###############################################################################
# SECTION 4: ACCESS POINTS
###############################################################################

echo "🌐 ACCESS POINTS:"
echo ""
echo "  📊 Dashboard UI:          ${GREEN}http://localhost:3000${NC}"
echo "  🔌 API (Health check):    ${GREEN}http://localhost:8080/api/health${NC}"
echo "  📡 API (Alerts):          ${GREEN}http://localhost:8080/api/alerts${NC}"
echo "  🔍 API Docs:              ${GREEN}http://localhost:8080/docs${NC}"
echo "  📈 Stats:                 ${GREEN}http://localhost:8080/api/stats${NC}"
echo ""

###############################################################################
# SECTION 5: MONITORING
###############################################################################

echo "📝 MONITORING & LOGS:"
echo ""
echo "  View Enrichment logs:"
echo "    ${YELLOW}journalctl -u smart-ids-enrichment -f --no-pager | grep -v absl | grep -v cuda${NC}"
echo ""
echo "  View Backend logs:"
echo "    ${YELLOW}tail -f dashboard/backend.log${NC}"
echo ""
echo "  View Frontend logs:"
echo "    ${YELLOW}tail -f dashboard/frontend/frontend.log${NC}"
echo ""

###############################################################################
# SECTION 6: SECURITY WARNING
###############################################################################

echo "⚠️  SECURITY WARNING:"
echo ""
echo "  This project has CRITICAL security vulnerabilities:"
echo "  - API Keys exposed in .env"
echo "  - CORS allow-all (open source)"
echo "  - NO authentication required"
echo "  - Elasticsearch unencrypted"
echo ""
echo "  📄 Review the security audit:"
echo "    ${YELLOW}cat SECURITY_AUDIT_REPORT.md${NC}"
echo ""
echo "  🔒 For production deployment, apply all P0 security fixes first!"
echo ""

###############################################################################
# SECTION 7: STOP INSTRUCTIONS
###############################################################################

echo "⏹️  TO STOP ALL SERVICES:"
echo ""
echo "  Stop individually:"
echo "    systemctl stop smart-ids-enrichment"
echo "    pkill -f 'uvicorn.*backend:app'"
echo "    pkill -f 'react-scripts.*start'"
echo ""
echo "  Or run cleanup:"
echo "    bash STOP_PROJECT.sh"
echo ""

echo "═══════════════════════════════════════════════════════════════════"
echo -e "${GREEN}✅ SMART-IDS is RUNNING!${NC}"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
