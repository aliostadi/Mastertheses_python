# 📤 Deployment Guide

This guide explains how to deploy the parking lot prediction project after cloning from GitLab.

---

## 📋 Prerequisites

- Git installed
- Python 3.9+
- PostgreSQL database (local or cloud)
- Docker & Docker Compose (for production)
- AWS account (for cloud deployment)
- Parking Pilot API credentials
- ~30-60 minutes for initial data preparation

---

## 🚀 Quick Start (Local Testing)

Perfect for professors who want to test the code locally.

### **Step 1: Clone Repository**

```bash
git clone <gitlab-repo-url>
cd Mastertheses_python
```

### **Step 2: Training Pipeline Setup**

```bash
cd training_pipeline

# Create fresh Python environment
python -m venv venv

# Activate environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure with your credentials
cp src/config/settings.py.example src/config/settings.py
# Edit settings.py with your database & API credentials

# Prepare training data (8 steps, ~30-60 minutes)
# Windows:
prepare_training_data.bat
# macOS/Linux:
bash prepare_training_data.sh
```

### **Step 3: Train ML Models**

```bash
# Train models on the prepared data
# Windows:
python -m src.training.lot38_trainer
python -m src.training.lot634_trainer
# macOS/Linux:
python -m src.training.lot38_trainer
python -m src.training.lot634_trainer

# Check results
ls results/lot38/
ls results/lot634/
```

### **Verify Success:**

```bash
# Should see these files:
# - linear_regression_model.pkl
# - encoder_decoder_model.keras
# - training_report.json
```

---

## 🐳 Docker + Local Database

For testing both training and prediction pipelines locally.

### **Step 1: Start PostgreSQL**

**Option A: Docker**
```bash
cd prediction_pipeline
docker-compose up -d postgres
```

**Option B: Local PostgreSQL**
- Install PostgreSQL locally
- Create database: `createdb parking`
- Create user: `createuser parking_user`

### **Step 2: Initialize Database**

```bash
# Apply schema
psql -U parking_user -d parking -f training_pipeline/database/init.sql
```

### **Step 3: Configure & Run Training**

```bash
cd training_pipeline
cp src/config/settings.py.example src/config/settings.py

# Edit settings.py:
# DB_URL = "postgresql://parking_user:PASSWORD@localhost:5432/parking"

python -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate
pip install -r requirements.txt

bash prepare_training_data.sh  # or: prepare_training_data.bat
```

### **Step 4: Start Prediction Services (Optional)**

```bash
cd prediction_pipeline
docker-compose up -d  # Starts all services
```

Access dashboard: `http://localhost:5000`

---

## ☁️ AWS Deployment (Production)

For deploying to AWS for continuous predictions.

### **Step 1: Create AWS Resources**

```bash
# Option 1: Using automated scripts (in prediction_pipeline/)
bash manage_aws_services.sh create

# Option 2: Manual AWS setup
# - EC2 instance (Ubuntu 22.04 recommended)
# - RDS PostgreSQL database
# - S3 bucket for backups
# - CloudWatch for monitoring
```

### **Step 2: Connect to EC2**

```bash
# SSH into your EC2 instance
ssh -i your-key.pem ubuntu@your-ec2-ip

# Clone repository
cd /home/ubuntu
git clone <gitlab-repo-url>
cd Mastertheses_python
```

### **Step 3: Setup Environment on EC2**

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
sudo apt install docker.io docker-compose -y
sudo usermod -aG docker ubuntu

# Install PostgreSQL client (for testing)
sudo apt install postgresql-client -y

# Get credentials from encrypted AWS Secrets Manager
# (Or securely copy from local machine)
```

### **Step 4: Configure Environment**

```bash
# Create .env file with credentials
cat > prediction_pipeline/.env << EOF
DB_HOST=your-rds-endpoint.rds.amazonaws.com
DB_PORT=5432
DB_NAME=parking
DB_USER=parking_user
DB_PASSWORD=secure_password_from_aws_secrets

PARKING_API_USERNAME=FutureIOT_MOBI
PARKING_API_PASSWORD=your_api_password

DASHBOARD_PORT=5000
PREDICTION_FREQUENCY=hourly
EOF

chmod 600 prediction_pipeline/.env
```

### **Step 5: Deploy Services**

```bash
cd prediction_pipeline

# Build and start all services
docker-compose -f docker-compose.yml -f docker-compose.aws-deploy.yml up -d

# Verify services are running
docker-compose ps

# View logs
docker-compose logs -f
```

### **Step 6: Setup Reverse Proxy (HTTPS)**

```bash
# Install nginx
sudo apt install nginx -y

# Copy nginx config (provided in docker-compose.aws-deploy.yml)
sudo cp nginx.conf /etc/nginx/sites-available/parking-app
sudo ln -s /etc/nginx/sites-available/parking-app /etc/nginx/sites-enabled/

# Get SSL certificate (free with Let's Encrypt)
sudo apt install certbot python3-certbot-nginx -y
sudo certbot certonly --standalone -d your-domain.com

# Start nginx
sudo systemctl start nginx
sudo systemctl enable nginx
```

### **Step 7: Verify Deployment**

```bash
# Check all services health
docker-compose ps

# View recent logs
docker-compose logs --tail=50

# Test API endpoint
curl https://your-domain.com/api/predictions/lot38

# Access dashboard
# https://your-domain.com
```

---

## 📊 Database Backup & Recovery

### **Backup (AWS)**

```bash
# Automated daily snapshot (RDS)
# Configured in AWS RDS console

# Manual backup
aws rds create-db-snapshot \
  --db-instance-identifier parking-db \
  --db-snapshot-identifier parking-backup-$(date +%Y%m%d)

# Export to S3
aws rds start-export-task \
  --export-task-identifier parking-export \
  --source-arn <snapshot-arn> \
  --s3-bucket-name your-bucket \
  --iam-role-arn <role-arn>
```

### **Restore**

```bash
# Restore from latest snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier parking-db-restored \
  --db-snapshot-identifier <snapshot-id>
```

---

## 🔄 Update Models

When you train new models locally, deploy them to production:

```bash
# After training locally, copy models to cloud
scp -i your-key.pem -r training_pipeline/results/ \
    ubuntu@your-ec2-ip:/home/ubuntu/Mastertheses_python/prediction_pipeline/services/predictor/models/

# Restart predictor service
ssh -i your-key.pem ubuntu@your-ec2-ip
cd Mastertheses_python/prediction_pipeline
docker-compose restart predictor

# Verify new predictions are generated
docker-compose logs predictor | tail -20
```

---

## 🔐 Security Checklist

- [ ] `.env` file configured with secure passwords (not in git)
- [ ] AWS Secrets Manager stores sensitive credentials
- [ ] SSL/HTTPS enabled for all external connections
- [ ] Database backups automated and tested
- [ ] CloudWatch alarms setup for service failures
- [ ] Security groups restrict access (only needed ports open)
- [ ] Regular security updates applied to EC2
- [ ] API credentials rotated monthly

---

## 📈 Monitoring & Troubleshooting

### **View Logs**

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f predictor
docker-compose logs -f dashboard

# Real-time log streaming
docker-compose logs -f --tail=100
```

### **Common Issues**

| Issue | Cause | Solution |
|-------|-------|----------|
| Services not starting | Port already in use | Change port in `.env` or kill process |
| Database connection fails | .env credentials wrong | Update DB credentials in `.env` |
| API authentication error | API credentials expired | Update in `.env`, restart services |
| Predictions not updating | Data not flowing | Check data_transformer logs |
| High memory usage | Large dataset | Increase EC2 instance size |

---

## 🚦 Before Going Live

- [ ] Test end-to-end: data → predictions → dashboard
- [ ] Monitor logs for 24 hours
- [ ] Verify backups work
- [ ] Document any customizations
- [ ] Setup monitoring & alerts
- [ ] Train team on operations
- [ ] Create runbook for incident response

---

## 📞 Support

For issues or questions:
1. Check service logs: `docker-compose logs service-name`
2. Review [Troubleshooting Guide](training_pipeline/README.md#-troubleshooting)
3. Check AWS CloudWatch for system metrics
4. Review [Architecture Diagram](prediction_pipeline/README.md#-architecture-overview)

---

**Last Updated**: April 2026
