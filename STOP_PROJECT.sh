#!/bin/bash

###############################################################################
# ⏹️ SMART-IDS STOP SCRIPT
# Shutdown all microservices cleanly
###############################################################################

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║             ⏹️  SMART-IDS PROJECT SHUTDOWN                   ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Stop ML Enrichment
echo "  Stopping 🧠 ML Enrichment Service..."
systemctl stop smart-ids-enrichment > /dev/null 2>&1
echo -e "    ${GREEN}✅ Stopped${NC}"

# Stop Backend API
echo "  Stopping 📡 Backend API..."
pkill -f "uvicorn.*backend:app" > /dev/null 2>&1
echo -e "    ${GREEN}✅ Stopped${NC}"

# Stop Frontend
echo "  Stopping 🎨 Frontend UI..."
pkill -f "react-scripts.*start" > /dev/null 2>&1
echo -e "    ${GREEN}✅ Stopped${NC}"

echo ""
echo -e "${GREEN}✅ All services stopped gracefully${NC}"
echo ""
