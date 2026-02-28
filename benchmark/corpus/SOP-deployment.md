# Standard Operating Procedure: Deployment

## Pre-Deployment Checklist

- [ ] All tests passing in CI
- [ ] Database migrations reviewed
- [ ] Rollback plan documented
- [ ] On-call engineer notified

## Deployment Steps

### 1. Prepare
```bash
# Pull latest images
docker-compose pull

# Verify health
curl -f http://localhost:8080/health || exit 1
```

### 2. Deploy
```bash
# Deploy with zero-downtime
docker-compose up -d --scale gateway=2 --no-recreate gateway
docker-compose up -d --scale gateway=1

# Run migrations
python scripts/migrate.py --target latest
```

### 3. Verify
```bash
# Health check
curl -f http://localhost:8080/health

# Smoke tests
pytest tests/smoke/
```

## Rollback Procedure

If deployment fails:

1. **Stop current deployment**
   ```bash
   docker-compose down
   ```

2. **Restore previous version**
   ```bash
   git checkout previous-release
docker-compose pull
docker-compose up -d
   ```

3. **Run database rollback script**
   ```bash
   python scripts/migrate.py --target previous
   ```

4. **Verify health check**
   ```bash
   curl -f http://localhost:8080/health
   ```

## Post-Deployment

- Update change log
- Notify stakeholders
- Monitor dashboards for 1 hour
