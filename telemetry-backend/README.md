# GATI Telemetry Backend (Vercel)

Serverless telemetry collection for GATI SDK.

---

## Quick Deploy

### 1. Install Vercel CLI

```bash
npm install -g vercel
```

### 2. Login to Vercel

```bash
vercel login
```

### 3. Set Up Database

```bash
# Create Vercel Postgres database
vercel postgres create gati-telemetry-db
```

### 4. Create Database Table

Connect to your database and run:

```sql
CREATE TABLE IF NOT EXISTS gati_metrics (
    id SERIAL PRIMARY KEY,
    installation_id VARCHAR(255) NOT NULL,
    sdk_version VARCHAR(50) NOT NULL,
    agents_tracked INTEGER NOT NULL,
    events_today INTEGER NOT NULL,
    lifetime_events INTEGER NOT NULL,
    mcp_queries INTEGER DEFAULT 0,
    frameworks_detected TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    received_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_installation (installation_id),
    INDEX idx_received (received_at)
);
```

To connect to your database:

```bash
# Get connection string
vercel env pull .env.local

# Connect using psql
psql "$(grep POSTGRES_URL .env.local | cut -d '=' -f2-)"
```

Or use Vercel's web interface:
1. Go to your project dashboard
2. Click "Storage" tab
3. Click your database
4. Click "Query" tab
5. Paste the SQL above

### 5. Deploy

```bash
cd telemetry-backend
vercel deploy --prod
```

You'll get a URL like: `https://gati-telemetry.vercel.app`

### 6. Set Admin Token (Optional)

For the `/api/stats` endpoint:

```bash
vercel env add ADMIN_TOKEN
# Enter a secure random token
```

### 7. Test It

```bash
# Test health check
curl https://your-project.vercel.app/api/health

# Test metrics endpoint
curl -X POST https://your-project.vercel.app/api/metrics \
  -H "Content-Type: application/json" \
  -d '{
    "installation_id": "test-123",
    "sdk_version": "0.1.0",
    "agents_tracked": 1,
    "events_today": 10,
    "lifetime_events": 100,
    "frameworks_detected": ["langchain"],
    "timestamp": "2024-01-15T10:00:00Z"
  }'

# View stats (requires admin token)
curl https://your-project.vercel.app/api/stats \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

### 8. Update SDK

Update the telemetry endpoint in your SDK:

```python
# In sdk/gati/core/telemetry.py, line 22
DEFAULT_ENDPOINT = "https://your-project.vercel.app/api/metrics"
```

Or users can override:

```python
observe.init(
    backend_url="http://localhost:8000",
    telemetry_endpoint="https://your-project.vercel.app/api/metrics"
)
```

---

## Monitoring

### View Logs

```bash
vercel logs
```

### View Database

```bash
# Connect to database
vercel postgres connect gati-telemetry-db

# Query data
SELECT * FROM gati_metrics ORDER BY received_at DESC LIMIT 10;
```

### View Analytics

Vercel dashboard shows:
- Request count
- Response times
- Error rates
- Database queries

---

## Costs

**Vercel Free Tier:**
- 100GB bandwidth/month
- 100,000 requests/month
- 1GB PostgreSQL storage
- 60 hours compute time/month

**Estimated usage for 1000 users:**
- ~1000 requests/day (1 per user per day)
- ~30,000 requests/month
- Well within free tier!

**If you exceed free tier:**
- Pro plan: $20/month
- Includes 1TB bandwidth, 1M requests

---

## Security

1. **Rate limiting** is automatic on Vercel
2. **DDoS protection** included
3. **HTTPS** automatic
4. Add authentication to `/api/stats`:
   ```bash
   vercel env add ADMIN_TOKEN
   ```

## Troubleshooting

### Database connection errors

```bash
# Check environment variables
vercel env ls

# Pull latest .env
vercel env pull .env.local
```

### Function timeouts

Edit `vercel.json`:
```json
{
  "functions": {
    "api/*.js": {
      "maxDuration": 30
    }
  }
}
```

### CORS issues

Already handled in `api/metrics.js`, but if needed:
```javascript
response.setHeader('Access-Control-Allow-Origin', 'https://your-domain.com');
```

---

## Alternative: Vercel KV (Redis)

If you prefer Redis over Postgres:

```bash
# Create KV store
vercel kv create gati-telemetry-kv

# Update api/metrics.js to use KV
import { kv } from '@vercel/kv';
await kv.set(`metrics:${installation_id}`, data);
```

---

## Production Tips

1. **Set up alerts** in Vercel dashboard
2. **Monitor costs** regularly
3. **Back up database** periodically
4. **Rotate admin token** every 6 months
5. **Set up custom domain** (optional)

---

## Support

- Vercel Docs: https://vercel.com/docs
- Vercel Postgres: https://vercel.com/docs/storage/vercel-postgres
- Issues: https://github.com/gati-ai/gati-sdk/issues
