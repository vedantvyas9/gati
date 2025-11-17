// Request verification code endpoint
// Sends a 6-digit code to user's email
const { Pool } = require('pg');
const crypto = require('crypto');

// Parse Supabase connection string
const { URL } = require('url');

// Lazy pool initialization to handle missing env vars gracefully
let pool = null;

function getPool() {
  if (!pool) {
    if (!process.env.POSTGRES_URL) {
      throw new Error('POSTGRES_URL environment variable is not set');
    }
    try {
      const dbUrl = new URL(process.env.POSTGRES_URL);
      pool = new Pool({
        host: dbUrl.hostname,
        port: parseInt(dbUrl.port),
        database: dbUrl.pathname.split('/')[1],
        user: dbUrl.username,
        password: dbUrl.password,
        ssl: {
          rejectUnauthorized: false
        }
      });
    } catch (error) {
      console.error('Failed to create database pool:', error);
      throw new Error(`Database configuration error: ${error.message}`);
    }
  }
  return pool;
}

// Email sending function (using a service like Resend, SendGrid, etc.)
async function sendVerificationEmail(email, code) {
  // TODO: Integrate with email service (Resend is free for 3000 emails/month)
  // For now, we'll use Resend API

  const RESEND_API_KEY = process.env.RESEND_API_KEY;

  console.log('Attempting to send email to:', email);
  console.log('RESEND_API_KEY exists:', !!RESEND_API_KEY);
  console.log('RESEND_API_KEY length:', RESEND_API_KEY ? RESEND_API_KEY.length : 0);

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
        to: [email],
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
      const errorData = await response.json().catch(() => ({}));
      console.error('Resend API error:', {
        status: response.status,
        statusText: response.statusText,
        error: errorData
      });
      
      // Log specific error message for debugging
      if (errorData.message) {
        console.error('Resend error message:', errorData.message);
      }
      
      return false;
    }

    const result = await response.json();
    console.log('Email sent successfully:', result);
    return true;
  } catch (error) {
    console.error('Failed to send email:', error);
    console.error('Error stack:', error.stack);
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
    // Validate environment first
    if (!process.env.POSTGRES_URL) {
      console.error('POSTGRES_URL not configured');
      return response.status(500).json({
        error: 'Server configuration error. Please contact support.'
      });
    }

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

    await getPool().query(
      `INSERT INTO gati_verification_codes (email, code_hash, expires_at, created_at)
       VALUES ($1, $2, $3, NOW())
       ON CONFLICT (email)
       DO UPDATE SET code_hash = $2, expires_at = $3, created_at = NOW(), attempts = 0`,
      [email.toLowerCase(), hashedCode, expiresAt]
    );

    // Send email
    const emailSent = await sendVerificationEmail(email, code);

    if (!emailSent) {
      // Check if this is a Resend validation error (testing mode limitation)
      // In testing mode, Resend only allows sending to the account owner's email
      return response.status(500).json({
        error: 'Failed to send verification email. Please try again or contact support if the issue persists.',
        hint: 'If you are testing, ensure you are using the correct email address.'
      });
    }

    return response.status(200).json({
      success: true,
      message: 'Verification code sent to your email'
    });

  } catch (error) {
    console.error('Error requesting code:', error);
    console.error('Error stack:', error.stack);
    return response.status(500).json({
      error: 'Internal server error',
      message: process.env.NODE_ENV === 'development' ? error.message : 'An error occurred. Please try again.'
    });
  }
};
