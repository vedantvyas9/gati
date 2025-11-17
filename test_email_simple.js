// Simple test of just the email sending part
process.env.POSTGRES_URL = 'postgres://user:pass@localhost:5432/test';
process.env.RESEND_API_KEY = 're_3SaVBPf6_JYnMrL4aXMW1Xg27Ch39TpZg';

async function testEmailSending() {
  const email = 'vedant.p.vyas@gmail.com';
  const code = '123456';
  
  console.log('Testing email sending...');
  console.log('To:', email);
  console.log('Code:', code);
  console.log('');
  
  try {
    const response = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${process.env.RESEND_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        from: 'GATI <onboarding@resend.dev>',
        to: [email],  // Array format - THIS WAS THE FIX
        subject: 'Your GATI Verification Code',
        html: `
          <h2>Welcome to GATI!</h2>
          <p>Your verification code is:</p>
          <h1 style="font-size: 32px; letter-spacing: 8px; color: #4F46E5;">${code}</h1>
          <p>This code will expire in 10 minutes.</p>
        `
      })
    });

    console.log('Response status:', response.status);
    const data = await response.json();
    console.log('Response data:', JSON.stringify(data, null, 2));
    
    if (response.ok) {
      console.log('\n✅ SUCCESS! Email sent');
      console.log('Check your inbox:', email);
    } else {
      console.log('\n❌ FAILED!');
    }
  } catch (error) {
    console.error('❌ Error:', error.message);
  }
}

testEmailSending();
