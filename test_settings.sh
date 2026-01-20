#!/bin/bash
# Test script for LAIM Settings API
# Run this on the server where Docker is running

BASE_URL="${1:-http://localhost:8000}"
USERNAME="${2:-admin}"
PASSWORD="${3:-admin}"

echo "=== LAIM Settings API Test ==="
echo "Base URL: $BASE_URL"
echo ""

# Login and get cookie
echo "1. Logging in as $USERNAME..."
LOGIN_RESPONSE=$(curl -s -c cookies.txt -X POST "$BASE_URL/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$USERNAME&password=$PASSWORD" \
  -w "\n%{http_code}")

HTTP_CODE=$(echo "$LOGIN_RESPONSE" | tail -1)
if [ "$HTTP_CODE" != "200" ] && [ "$HTTP_CODE" != "303" ] && [ "$HTTP_CODE" != "302" ]; then
  echo "   FAILED: Login returned $HTTP_CODE"
  exit 1
fi
echo "   OK: Logged in successfully"
echo ""

# Test GET item types
echo "2. Testing GET /api/settings/item-types..."
RESPONSE=$(curl -s -b cookies.txt "$BASE_URL/api/settings/item-types")
echo "   Response: $RESPONSE"

if echo "$RESPONSE" | grep -q '"item_types"'; then
  echo "   OK: Response contains 'item_types' key"
else
  echo "   FAILED: Response missing 'item_types' key"
fi
echo ""

# Test GET rooms
echo "3. Testing GET /api/settings/rooms..."
RESPONSE=$(curl -s -b cookies.txt "$BASE_URL/api/settings/rooms")
echo "   Response: $RESPONSE"

if echo "$RESPONSE" | grep -q '"rooms"'; then
  echo "   OK: Response contains 'rooms' key"
else
  echo "   FAILED: Response missing 'rooms' key"
fi
echo ""

# Test PUT item types
echo "4. Testing PUT /api/settings/item-types..."
RESPONSE=$(curl -s -b cookies.txt -X PUT "$BASE_URL/api/settings/item-types" \
  -H "Content-Type: application/json" \
  -d '{"item_types": ["Switch", "Server", "Firewall", "AP", "UPS", "PDU", "Other"]}')
echo "   Response: $RESPONSE"

if echo "$RESPONSE" | grep -q '"item_types"'; then
  echo "   OK: Item types updated successfully"
else
  echo "   FAILED: Could not update item types"
fi
echo ""

# Test PUT rooms
echo "5. Testing PUT /api/settings/rooms..."
RESPONSE=$(curl -s -b cookies.txt -X PUT "$BASE_URL/api/settings/rooms" \
  -H "Content-Type: application/json" \
  -d '{"rooms": ["MDF", "IDF-1", "IDF-2", "Server Room"]}')
echo "   Response: $RESPONSE"

if echo "$RESPONSE" | grep -q '"rooms"'; then
  echo "   OK: Rooms updated successfully"
else
  echo "   FAILED: Could not update rooms"
fi
echo ""

# Test password change endpoint exists
echo "6. Testing PUT /api/me/password (with wrong current password - should fail)..."
RESPONSE=$(curl -s -b cookies.txt -X PUT "$BASE_URL/api/me/password" \
  -H "Content-Type: application/json" \
  -d '{"current_password": "wrong", "new_password": "newpass123", "confirm_password": "newpass123"}')
echo "   Response: $RESPONSE"

if echo "$RESPONSE" | grep -q '"detail"'; then
  echo "   OK: Endpoint exists and validates correctly"
else
  echo "   WARN: Unexpected response"
fi
echo ""

# Cleanup
rm -f cookies.txt

echo "=== Test Complete ==="
