# Hy-EWS WhatsApp Bot

Flask webhook for Twilio WhatsApp flood reporting.

## Environment variables (set in Railway)
- TWILIO_SID — your Twilio Account SID
- TWILIO_TOKEN — your Twilio Auth Token
- TWILIO_FROM — your Twilio WhatsApp number e.g. whatsapp:+14155238886
- SHEETS_URL — your Google Apps Script Web App URL

## Deploy
1. Push to GitHub
2. Connect repo to Railway
3. Set environment variables
4. Railway gives you a public URL — paste it into Twilio webhook
