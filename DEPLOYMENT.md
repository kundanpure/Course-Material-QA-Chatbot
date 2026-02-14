# 🚀 Production Deployment Guide

## Table of Contents
1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Infrastructure Setup](#infrastructure-setup)
3. [Configuration Management](#configuration-management)
4. [Database Migrations](#database-migrations)
5. [Deployment Strategies](#deployment-strategies)
6. [Monitoring & Observability](#monitoring--observability)
7. [Security Hardening](#security-hardening)
8. [Scaling Strategies](#scaling-strategies)
9. [Disaster Recovery](#disaster-recovery)

---

## Pre-Deployment Checklist

### ✅ Required Services
- [ ] PostgreSQL 15+ (managed service recommended)
- [ ] Redis 7+ (managed service recommended)
- [ ] Qdrant (self-hosted or cloud)
- [ ] Neo4j (self-hosted or Aura)
- [ ] S3-compatible object storage
- [ ] Load balancer with SSL/TLS
- [ ] DNS configured
- [ ] Monitoring stack (Prometheus + Grafana)

### ✅ API Keys & Secrets
- [ ] OpenAI API key (with billing alerts)
- [ ] Groq API key (fallback provider)
- [ ] LangSmith API key (optional, for tracing)
- [ ] AWS credentials (S3 access)
- [ ] Strong SECRET_KEY (min 32 chars)
- [ ] Secure database passwords
- [ ] Redis authentication password

### ✅ Performance Targets
- [ ] Avg latency p50 < 1s
- [ ] Avg latency p99 < 3s
- [ ] Cache hit rate > 30%
- [ ] Uptime > 99.9%

---

## Infrastructure Setup

### Option 1: AWS (Recommended)

```bash
# 1. VPC & Networking
- VPC with public/private subnets
- NAT Gateway for private subnets
- Security groups properly configured

# 2. Managed Services
- RDS PostgreSQL (Multi-AZ)
- ElastiCache Redis (Cluster mode)
- ECS/EKS for container orchestration
- ALB for load balancing
- S3 for document storage

# 3. Compute
- ECS Fargate or EC2 instances
- Auto-scaling group (2-10 instances)
- 2 vCPU, 4GB RAM minimum per instance
```

### Option 2: Docker Swarm / Kubernetes

#### Kubernetes Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: course-qa-api
  namespace: production
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: course-qa-api
  template:
    metadata:
      labels:
        app: course-qa-api
    spec:
      containers:
      - name: api
        image: your-registry/course-qa:latest
        ports:
        - containerPort: 8000
        env:
        - name: POSTGRES_HOST
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: host
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
```

---

## Configuration Management

### Environment-Specific Configs

```bash
# Production .env
DEBUG=False
ENVIRONMENT=production
LOG_LEVEL=INFO

# Rate limits (more restrictive)
RATE_LIMIT_REQUESTS=50
RATE_LIMIT_WINDOW=60

# Enable all production features
ENABLE_PROMPT_INJECTION_SHIELD=true
ENABLE_ANSWER_VALIDATION=true
ENABLE_GRAPH_RETRIEVAL=true

# Observability
ENABLE_TRACING=true
LANGSMITH_PROJECT=course-qa-production
```

### Secrets Management

```bash
# Use AWS Secrets Manager, HashiCorp Vault, or K8s Secrets

# Example: AWS Secrets Manager
aws secretsmanager create-secret \
  --name prod/course-qa/openai-key \
  --secret-string "sk-..."

# Retrieve in app:
import boto3
client = boto3.client('secretsmanager')
secret = client.get_secret_value(SecretId='prod/course-qa/openai-key')
```

---

## Database Migrations

### Alembic Setup

```bash
# Generate migration
alembic revision --autogenerate -m "Add query logs table"

# Review migration file
vim alembic/versions/xxx_add_query_logs_table.py

# Apply to staging first
alembic upgrade head

# Apply to production (with backup!)
pg_dump course_qa > backup_$(date +%Y%m%d).sql
alembic upgrade head
```

### Zero-Downtime Migrations

```python
# alembic/env.py - use asyncio
from sqlalchemy.ext.asyncio import create_async_engine

# Run migrations during deployment
# Use blue-green deployment to avoid downtime
```

---

## Deployment Strategies

### 1. Blue-Green Deployment (Recommended)

```bash
# 1. Deploy new version to "green" environment
docker-compose -f docker-compose.green.yml up -d

# 2. Run health checks
curl http://green.internal:8000/api/v1/health

# 3. Switch load balancer to green
# Update ALB target group

# 4. Monitor for issues
# Check Grafana dashboards

# 5. If success, decommission blue
# If failure, rollback to blue immediately
```

### 2. Rolling Update

```bash
# Update instances one at a time
# Kubernetes handles this automatically with:
kubectl set image deployment/course-qa-api \
  api=your-registry/course-qa:v2.1.0

# Monitor rollout
kubectl rollout status deployment/course-qa-api

# Rollback if needed
kubectl rollout undo deployment/course-qa-api
```

### 3. Canary Deployment

```bash
# Deploy to 10% of traffic first
# Monitor metrics closely
# Gradually increase to 100%

# Example with Istio
kubectl apply -f canary-virtual-service.yaml
```

---

## Monitoring & Observability

### Grafana Dashboard Setup

```yaml
# grafana-dashboard.json (excerpt)
{
  "dashboard": {
    "title": "Course QA - Production Metrics",
    "panels": [
      {
        "title": "Request Rate",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])"
          }
        ]
      },
      {
        "title": "Latency p99",
        "targets": [
          {
            "expr": "histogram_quantile(0.99, http_request_duration_seconds_bucket)"
          }
        ]
      },
      {
        "title": "Circuit Breaker State",
        "targets": [
          {
            "expr": "circuit_breaker_state"
          }
        ]
      },
      {
        "title": "Cache Hit Rate",
        "targets": [
          {
            "expr": "cache_hits_total / (cache_hits_total + cache_misses_total)"
          }
        ]
      }
    ]
  }
}
```

### Alert Rules

```yaml
# prometheus-alerts.yml
groups:
  - name: course_qa_alerts
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate detected"
      
      - alert: CircuitBreakerOpen
        expr: circuit_breaker_state{service="llm"} == 1
        for: 2m
        annotations:
          summary: "LLM circuit breaker is OPEN"
      
      - alert: HighLatency
        expr: histogram_quantile(0.99, http_request_duration_seconds_bucket) > 5
        for: 5m
        annotations:
          summary: "p99 latency > 5s"
      
      - alert: LowCacheHitRate
        expr: cache_hits_total / (cache_hits_total + cache_misses_total) < 0.2
        for: 15m
        annotations:
          summary: "Cache hit rate dropped below 20%"
```

---

## Security Hardening

### 1. Network Security

```bash
# Security group rules (AWS)
- Allow HTTPS (443) from Internet
- Allow HTTP (80) redirect to HTTPS
- Allow 8000 only from load balancer
- PostgreSQL (5432) only from app servers
- Redis (6379) only from app servers
- No public access to databases
```

### 2. Application Security

```python
# Enable security headers
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["yourdomain.com", "*.yourdomain.com"]
)

app.add_middleware(HTTPSRedirectMiddleware)

# CORS properly configured
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

### 3. API Security

```bash
# Rate limiting per tenant
RATE_LIMIT_REQUESTS=100

# Strong JWT secrets
SECRET_KEY=$(openssl rand -hex 32)

# API key rotation policy (every 90 days)
```

---

## Scaling Strategies

### Horizontal Scaling

```yaml
# Auto-scaling based on metrics
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: course-qa-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: course-qa-api
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Database Scaling

```bash
# PostgreSQL
- Read replicas for analytics queries
- Connection pooling (PgBouncer)
- Partition large tables by tenant_id

# Qdrant
- Sharding by tenant_id
- Replicas for read scaling

# Redis
- Cluster mode for horizontal scaling
- Separate cache vs. message broker
```

---

## Disaster Recovery

### Backup Strategy

```bash
# Automated daily backups
# PostgreSQL
0 2 * * * pg_dump course_qa | gzip > /backups/course_qa_$(date +\%Y\%m\%d).sql.gz

# Qdrant snapshots
curl -X POST 'http://qdrant:6333/collections/course_materials/snapshots'

# Neo4j backups
neo4j-admin backup --to=/backups/neo4j-$(date +\%Y\%m\%d)

# S3 document versioning enabled
# Retention: 30 days
```

### Recovery Procedures

```bash
# 1. Database restore
gunzip -c backup_20240101.sql.gz | psql course_qa

# 2. Qdrant restore
curl -X PUT 'http://qdrant:6333/collections/course_materials/snapshots/upload' \
  --data-binary @snapshot.tar.gz

# 3. Verify data integrity
python scripts/verify_recovery.py

# RTO: < 4 hours
# RPO: < 1 hour (continuous WAL shipping)
```

---

## Cost Optimization

### LLM Costs

```python
# 1. Aggressive caching (35-40% hit rate)
# Savings: ~$1000/month on 100k queries

# 2. Use cheaper models when possible
# GPT-3.5 for simple queries
# GPT-4 only for complex reasoning

# 3. Prompt optimization
# Reduce token count by 30%
# Use system prompts effectively

# 4. Circuit breaker to cheaper provider
# Groq (free tier) as fallback
```

### Infrastructure Costs

```bash
# Monthly estimates (1000 concurrent users)
- RDS PostgreSQL (Multi-AZ): $200
- ElastiCache Redis: $150
- EC2/ECS (3 instances): $300
- Qdrant (self-hosted): $100
- Neo4j (self-hosted): $100
- S3 storage: $50
- Data transfer: $100
- Total: ~$1000/month
```

---

## Production Checklist

- [ ] SSL/TLS certificates installed
- [ ] Environment variables secured
- [ ] Database backups automated
- [ ] Monitoring dashboards configured
- [ ] Alert rules tested
- [ ] Load testing completed (1000+ concurrent)
- [ ] Security scan passed
- [ ] Documentation updated
- [ ] Runbook created
- [ ] On-call rotation scheduled

---

**Remember**: Test in staging first, deploy during low-traffic hours, have rollback plan ready!