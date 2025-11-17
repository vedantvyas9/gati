#!/bin/bash
# Complete auth flow test - simulates what happens when user runs gati auth

echo "=========================================="
echo "Testing Complete Auth Flow"
echo "=========================================="
echo ""

# Test 1: Health check
echo "1. Testing health endpoint..."
HEALTH=$(curl -s https://gati-mvp-telemetry.vercel.app/api/health)
echo "   Response: $HEALTH"
echo ""

# Test 2: Request code (this is what's failing)
echo "2. Testing request-code endpoint..."
echo "   Email: vedant.p.vyas@gmail.com"

RESPONSE=$(curl -s -X POST "https://gati-mvp-telemetry.vercel.app/api/auth/request-code" \
  -H "Content-Type: application/json" \
  -d '{"email":"vedant.p.vyas@gmail.com"}')

echo "   Response: $RESPONSE"
echo ""

# Check if successful
if echo "$RESPONSE" | grep -q "success"; then
    echo "✅ SUCCESS! Code sent to email"
    echo ""
    echo "Next steps:"
    echo "1. Check your email for the 6-digit code"
    echo "2. Run: /tmp/gati-test-env/bin/gati auth"
    echo "3. Enter the code from your email"
else
    echo "❌ FAILED! Error response from server"
    echo ""
    echo "This means the Vercel deployment hasn't picked up the fix yet."
    echo "Wait for deployment to complete and try again."
fi

echo ""
echo "=========================================="
