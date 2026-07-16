![AWS](https://img.shields.io/badge/AWS-ECS%20%2B%20SQS%20%2B%20DynamoDB-FF9900?style=flat&logo=amazonaws&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=flat&logo=docker&logoColor=white)
![Terraform](https://img.shields.io/badge/Terraform-IaC-7B42BC?style=flat&logo=terraform&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-Generator-339933?style=flat&logo=nodedotjs&logoColor=white)
![Cost](https://img.shields.io/badge/Monthly%20Cost-~%240-27ae60?style=flat)
![Status](https://img.shields.io/badge/Status-Live-27ae60?style=flat)

# Real-Time Event Analytics Platform

A distributed, containerized streaming analytics platform on AWS that
ingests high-volume sensor events, processes them through a decoupled
queue layer, aggregates into 30-second time windows, and serves a
live dashboard — with a full CI/CD pipeline deploying automatically
on every GitHub push.

**Live dashboard:** https://d2l3mkblvlm7wz.cloudfront.net

**Live API:** https://x4ipgihuba.execute-api.ap-south-1.amazonaws.com/metrics

---

## Architecture
Node.js Generator (5-100 events/sec)
↓
API Gateway + Lambda (event receiver)
↓
SQS Queue (decoupled buffer + DLQ)
↓
ECS Fargate Container — Python processor
(polls SQS, aggregates into 30-sec windows)
↓
DynamoDB time-series table (with TTL)
↓
Query Lambda + API Gateway
↓
React Dashboard on CloudFront (HTTPS, auto-refresh 10s)
─────────────── CI/CD ───────────────
GitHub push → main
↓
CodePipeline triggers automatically
↓
CodeBuild builds + tests Docker image
↓
ECR stores new image version
↓
ECS rolling deployment (zero downtime)
↓
New container version live in ~3 minutes

---

## AWS Services Used

| Service | Purpose | Role |
|---|---|---|
| ECS Fargate | Stream processor container | Core compute |
| SQS | Event buffer + decoupling | Messaging |
| SQS DLQ | Failed message handling | Reliability |
| DynamoDB | Time-series metrics store | Storage |
| API Gateway | Event ingestion + query API | Networking |
| Lambda ×2 | Receiver + query functions | Serverless |
| ECR | Docker image registry | Containers |
| CodePipeline | CI/CD orchestration | DevOps |
| CodeBuild | Docker build + push | DevOps |
| CloudFront | HTTPS CDN for dashboard | Frontend |
| S3 | Dashboard hosting + artifacts | Storage |
| VPC | Network isolation | Security |
| CloudWatch | Container logs + metrics | Observability |
| IAM | Least-privilege roles | Security |

**14 AWS services. ~$0/month within free tier limits.**

---

## Key Features

- **Decoupled architecture** — SQS queue between API and processor
  means they scale independently. Producer and consumer are fully
  isolated — if the processor crashes, zero events are lost
- **30-second aggregation windows** — processor batches events into
  time windows computing min, max, avg, count per sensor per window
- **Dead letter queue** — messages that fail processing 3 times are
  automatically moved to DLQ for inspection, zero silent failures
- **TTL on DynamoDB** — data auto-expires after 24 hours, keeping
  storage costs at zero indefinitely
- **Full CI/CD** — git push → CodePipeline → CodeBuild → ECR →
  ECS rolling deploy in ~3 minutes, fully automated
- **Zero-downtime deployment** — ECS rolling update strategy keeps
  the old container running until the new one is healthy
- **Live dashboard** — auto-refreshes every 10 seconds, shows all
  sensors, event log, and real-time aggregations
- **Full IaC** — all 14 AWS resources provisioned via Terraform

---

## Data Model

DynamoDB time-series schema:

| PK | SK | Attributes |
|---|---|---|
| `SENSOR#sensor-karnataka-01` | `WINDOW#1784185560` | count, avg_value, min_value, max_value, event_types, expires_at |

Access patterns:
- Fetch all windows for a sensor → Query by PK
- Fetch all sensors overview → Scan with limit

TTL field `expires_at` automatically deletes records after 24 hours.

---

## Project Structure
realtime-analytics-platform/
├── infra/
│   └── main.tf                  # All 14 AWS resources as Terraform
├── services/
│   ├── processor/
│   │   ├── processor.py         # Python stream processor (runs in ECS)
│   │   ├── Dockerfile           # Container definition
│   │   └── buildspec.yml        # CodeBuild CI/CD build instructions
│   ├── receiver/
│   │   └── handler.py           # Lambda: API Gateway → SQS + query
│   └── generator/
│       └── generator.js         # Node.js load generator (local only)
├── dashboard/
│   └── index.html               # Live dashboard (CloudFront HTTPS)
├── .gitignore
└── README.md

---

## API Reference

### Ingest an event
POST /events

Body:
```json
{
  "sensor_id":  "sensor-karnataka-01",
  "event_type": "nitrogen_reading",
  "value":      142.5,
  "timestamp":  1784185560
}
```

Response:
```json
{
  "status":   "accepted",
  "event_id": "8c85d87b-35a3-4750-bc07-427f0a4465f4"
}
```

### Query aggregated metrics
GET /metrics
GET /metrics?sensor_id=sensor-karnataka-01&limit=20

Response:
```json
{
  "count": 33,
  "items": [
    {
      "sensor_id":   "sensor-karnataka-01",
      "window_ts":   1784185560,
      "window_start":"2026-07-16T07:06:00+00:00",
      "count":       8,
      "avg_value":   "156.32",
      "min_value":   "102.41",
      "max_value":   "211.83",
      "event_types": "{\"nitrogen_reading\": 5, \"phosphorus_reading\": 3}",
      "expires_at":  1784271960
    }
  ]
}
```

---

## How to Deploy

### Prerequisites
- AWS account with CLI configured (`aws configure`)
- Terraform installed
- Docker Desktop running
- Node.js installed

### Deploy infrastructure

```bash
# 1. Clone the repository
git clone https://github.com/abhi6850/realtime-analytics-platform.git
cd realtime-analytics-platform

# 2. Deploy all AWS resources
cd infra
terraform init
terraform apply
# Takes ~8 minutes (CloudFront deploys globally)

# 3. Note the outputs
# ecr_repository_url = "xxxx.dkr.ecr.ap-south-1.amazonaws.com/..."
# api_url            = "https://xxxx.execute-api.ap-south-1.amazonaws.com"
# dashboard_url      = "https://xxxx.cloudfront.net"
```

### Build and push Docker image

```bash
# Login to ECR
aws ecr get-login-password --region ap-south-1 | \
  docker login --username AWS --password-stdin YOUR_ECR_URL

# Build and push
cd services/processor
docker build -t analytics-processor .
docker tag analytics-processor:latest YOUR_ECR_URL:latest
docker push YOUR_ECR_URL:latest
```

### Upload dashboard

```bash
aws s3 cp dashboard/index.html \
  s3://YOUR_DASHBOARD_BUCKET/index.html \
  --content-type "text/html"
```

### Run the event generator

```bash
cd services/generator
npm install
API_URL=https://YOUR_API_URL/events RATE_PER_SEC=10 node generator.js
```

### Authorize GitHub connection (one-time)

Go to AWS Console → Developer Tools → Connections →
find your connection → click "Update pending connection" →
authorize GitHub OAuth.

### Tear down

```bash
cd infra
terraform destroy
```

---

## CI/CD Pipeline

Every push to `main` triggers the full pipeline automatically:
git push origin main
↓ (~10 seconds)
CodePipeline: Source stage pulls from GitHub
↓ (~2 minutes)
CodeBuild: builds Docker image, pushes to ECR
↓ (~1 minute)
ECS: rolling deployment of new container
↓
Zero-downtime update complete

Build logs available in CloudWatch under `/codebuild/analytics-*`.

---

## Key Design Decisions

**SQS decoupling over direct Lambda-to-ECS**
Direct invocation couples producer and consumer — if ECS is slow,
the API backs up. SQS absorbs bursts, enables independent scaling,
and provides at-least-once delivery with DLQ for failures. Classic
distributed systems pattern used at every major scale company.

**ECS Fargate over Lambda for stream processing**
Lambda has a 15-minute timeout — unsuitable for a long-running
polling loop. ECS Fargate runs the processor as a persistent
container that polls SQS indefinitely, the correct pattern for
continuous stream processing.

**DynamoDB time-series over dedicated TSDB**
TimestreamDB costs $0.036/GB. DynamoDB with a window-based SK
pattern achieves time-series storage at $0/month within free tier,
with TTL for automatic data expiry.

**Rolling deployment over recreate**
ECS rolling strategy keeps `minimumHealthyPercent: 100` — the old
task stays running until the new one passes health checks. Zero
downtime on every deploy.

---

## What I Would Add Next

- **Auto-scaling** — ECS service auto-scaling based on SQS queue depth
- **CloudWatch alarms** — alert when queue depth exceeds 1000 or
  processor error rate spikes
- **ML inference** — plug a SageMaker endpoint into the processor
  for real-time anomaly detection on sensor readings
- **Authentication** — Cognito on API Gateway for multi-tenant access
- **WebSocket** — replace polling with WebSocket push for true
  real-time dashboard updates

---

Built by Abhijeet Kulkarni — B.Tech CSE, Manipal Institute of Technology, Bengaluru

[![GitHub](https://img.shields.io/badge/GitHub-abhi6850-181717?style=flat&logo=github)](https://github.com/abhi6850)