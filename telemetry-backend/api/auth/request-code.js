// Request verification code endpoint
// Sends a 6-digit code to user's email
const { Pool } = require('pg');
const crypto = require('crypto');

// Parse Supabase connection string
const { URL } = require('url');
const dbUrl = new URL(process.env.POSTGRES_URL);

const pool = new Pool({
  host: dbUrl.hostname,
  port: parseInt(dbUrl.port),
  database: dbUrl.pathname.split('/')[1],
  user: dbUrl.username,
  password: dbUrl.password,
  ssl: {
    rejectUnauthorized: false
  }
});

// Email sending function (using a service like Resend, SendGrid, etc.)
async function sendVerificationEmail(email, code) {
  // TODO: Integrate with email service (Resend is free for 3000 emails/month)
  // For now, we'll use Resend API

  const RESEND_API_KEY = process.env.RESEND_API_KEY;

  if (!RESEND_API_KEY) {
    console.error('RESEND_API_KEY not configured');
    return false;
  }

  try {
    const response = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${RESEND_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        from: 'GATI <onboarding@resend.dev>',
        to: email,
        subject: 'Your GATI Verification Code',
        html: `
          <h2>Welcome to GATI!</h2>
          <p>Your verification code is:</p>
          <h1 style="font-size: 32px; letter-spacing: 8px; color: #4F46E5;">${code}</h1>
          <p>This code will expire in 10 minutes.</p>
          <p>If you didn't request this code, please ignore this email.</p>
        `
      })
    });

    if (!response.ok) {
      const errorData = await response.json();
      console.error('Resend API error:', errorData);
      return false;
    }

    const result = await response.json();
    console.log('Email sent successfully:', result);
    return true;
  } catch (error) {
    console.error('Failed to send email:', error);
    return false;
  }
}

module.exports = async function handler(request, response) {
  // Set CORS headers
  response.setHeader('Access-Control-Allow-Origin', '*');
  response.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  response.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  // Handle preflight
  if (request.method === 'OPTIONS') {
    return response.status(200).end();
  }

  // Only accept POST
  if (request.method !== 'POST') {
    return response.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { email } = request.body;

    // Validate email
    if (!email || !email.match(/^[^\s@]+@[^\s@]+\.[^\s@]+$/)) {
      return response.status(400).json({ error: 'Valid email is required' });
    }

    // Generate 6-digit code
    const code = Math.floor(100000 + Math.random() * 900000).toString();

    // Hash the code for storage
    const hashedCode = crypto.createHash('sha256').update(code).digest('hex');

    // Store in database with 10-minute expiration
    const expiresAt = new Date(Date.now() + 10 * 60 * 1000); // 10 minutes

    await pool.query(
      `INSERT INTO gati_verification_codes (email, code_hash, expires_at, created_at)
       VALUES ($1, $2, $3, NOW())
       ON CONFLICT (email)
       DO UPDATE SET code_hash = $2, expires_at = $3, created_at = NOW(), attempts = 0`,
      [email.toLowerCase(), hashedCode, expiresAt]
    );

    // Send email
    const emailSent = await sendVerificationEmail(email, code);

    if (!emailSent) {
      return response.status(500).json({
        error: 'Failed to send verification email. Please try again.'
      });
    }

    return response.status(200).json({
      success: true,
      message: 'Verification code sent to your email'
    });

  } catch (error) {
    console.error('Error requesting code:', error);
    return response.status(500).json({
      error: 'Internal server error',
      message: error.message
    });
  }
};
