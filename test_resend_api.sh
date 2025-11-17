#!/bin/bash
# Test Resend API directly to see the actual error
# This uses the RESEND_API_KEY from your .env file

# Load from .env
if [ -f .env ]; then
    export $(cat .env | grep RESEND_API_KEY | xargs)
fi

# Remove quotes if present
RESEND_API_KEY=$(echo $RESEND_API_KEY | tr -d '"')

echo "Testing Resend API..."
echo "API Key (first 10 chars): ${RESEND_API_KEY:0:10}..."
echo ""

curl -X POST 'https://api.resend.com/emails' \
  -H "Authorization: Bearer $RESEND_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "from": "GATI <onboarding@resend.dev>",
    "to": ["vedant.p.vyas@gmail.com"],
    "subject": "GATI Test Email",
    "html": "<p>This is a test email from GATI</p>"
  }' | python3 -m json.tool

echo ""
echo "If you see an error above, that's what's preventing emails from sending!"
