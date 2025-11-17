// Test the request-code function locally

// Set required environment variables BEFORE loading the module
process.env.POSTGRES_URL = 'postgres://user:pass@localhost:5432/testdb';

// Load environment variables from .env
require('dotenv').config();

const handler = require('./telemetry-backend/api/auth/request-code.js');

// Mock request and response objects
const mockRequest = {
  method: 'POST',
  body: {
    email: 'vedant.p.vyas@gmail.com'
  }
};

const mockResponse = {
  headers: {},
  statusCode: 200,
  body: null,

  setHeader(key, value) {
    this.headers[key] = value;
  },

  status(code) {
    this.statusCode = code;
    return this;
  },

  json(data) {
    this.body = data;
    console.log('\n📤 Response:');
    console.log('Status:', this.statusCode);
    console.log('Body:', JSON.stringify(data, null, 2));
    return this;
  },

  end() {
    console.log('Response ended');
    return this;
  }
};

// Override .env values with our test config if needed
require('dotenv').config();

// Mock the database pool to avoid actual database connection
const Module = require('module');
const originalRequire = Module.prototype.require;
Module.prototype.require = function(id) {
  if (id === 'pg') {
    return {
      Pool: class MockPool {
        async query() {
          console.log('📝 [MOCK] Database query called (skipped for test)');
          return { rows: [] };
        }
      }
    };
  }
  return originalRequire.apply(this, arguments);
};

console.log('🧪 Testing request-code function locally...\n');
console.log('Environment check:');
console.log('- RESEND_API_KEY exists:', !!process.env.RESEND_API_KEY);
console.log('- RESEND_API_KEY length:', process.env.RESEND_API_KEY?.length || 0);
console.log('- RESEND_API_KEY preview:', process.env.RESEND_API_KEY?.substring(0, 10) + '...');
console.log('- POSTGRES_URL exists:', !!process.env.POSTGRES_URL);
console.log('');

// Run the handler
console.log('🚀 Calling handler with test email...\n');
handler(mockRequest, mockResponse).catch(err => {
  console.error('\n❌ Error:', err);
  console.error('Stack:', err.stack);
  process.exit(1);
});
