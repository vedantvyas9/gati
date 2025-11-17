// Debug endpoint to check environment variables
module.exports = async function handler(request, response) {
  response.setHeader('Access-Control-Allow-Origin', '*');

  const hasResendKey = !!process.env.RESEND_API_KEY;
  const keyLength = process.env.RESEND_API_KEY ? process.env.RESEND_API_KEY.length : 0;
  const keyPreview = process.env.RESEND_API_KEY ? process.env.RESEND_API_KEY.substring(0, 10) + '...' : 'NOT SET';

  return response.status(200).json({
    environment: process.env.NODE_ENV || 'not set',
    hasResendKey: hasResendKey,
    resendKeyLength: keyLength,
    resendKeyPreview: keyPreview,
    hasPostgresUrl: !!process.env.POSTGRES_URL,
    allEnvKeys: Object.keys(process.env).filter(k => !k.includes('PATH') && !k.includes('npm')).sort()
  });
};
