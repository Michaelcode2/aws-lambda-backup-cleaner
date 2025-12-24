# AWS Lambda Backup Cleaner

An AWS Lambda function that automatically deletes old backups from S3 buckets based on configurable retention policies. Each backup folder can have its own retention configuration with age-based and count-based rules.

## Features

- **Flexible Retention Policies**: Configure retention for each backup folder individually
- **Dual Protection**:
  - Delete backups older than N days
  - Always preserve the last X backups (even if older than N days)
- **Safe by Default**: Ensures minimum number of backups are always retained
- **Automated Deployment**: GitHub Actions with OIDC for secure, credential-free deployment
- **Infrastructure as Code**: SAM/CloudFormation templates for reproducible deployments
- **Scheduled Execution**: Runs on CloudWatch Events schedule (daily by default)

## Architecture

```
┌─────────────────┐
│ CloudWatch Event│
│  (Daily Cron)   │
└────────┬────────┘
         │ Trigger
         ▼
┌─────────────────┐
│ Lambda Function │
│  (Python 3.11)  │
└────────┬────────┘
         │
         ├─► Read retention config (S3 or environment)
         │
         ├─► List objects in each backup folder
         │
         ├─► Apply retention policy:
         │   • Keep last X backups
         │   • Delete backups older than N days
         │
         └─► Delete expired backups
```

## Retention Policy Configuration

Each backup folder has two configuration parameters:

1. **`days_to_keep`**: Delete backups older than this many days
2. **`min_backups_to_keep`**: Always keep at least this many latest backups

### Example Configuration (`config.json`)

```json
{
  "retention_policies": [
    {
      "folder": "database-backups/production/",
      "days_to_keep": 30,
      "min_backups_to_keep": 7
    },
    {
      "folder": "database-backups/staging/",
      "days_to_keep": 14,
      "min_backups_to_keep": 5
    }
  ]
}
```

### How It Works

For each backup folder:
1. List all backups sorted by modification date (newest first)
2. **Always keep** the last `min_backups_to_keep` backups
3. For remaining backups, delete those older than `days_to_keep`

**Example**: With `days_to_keep=30` and `min_backups_to_keep=5`:
- If you have 10 backups and the 5 newest are all 35 days old → Keep all 5 (protected by min_backups_to_keep)
- If you have 10 backups where 7 are newer than 30 days → Keep 7, delete 3 oldest

## Project Structure

```
.
├── src/
│   └── lambda_function.py      # Main Lambda function code
├── .github/
│   └── workflows/
│       └── deploy.yml          # GitHub Actions workflow with OIDC
├── template.yaml               # SAM/CloudFormation template
├── samconfig.toml             # SAM CLI configuration
├── config.json                # Example retention policy configuration
├── requirements.txt           # Python dependencies
├── .gitignore
└── README.md
```

## Prerequisites

- AWS Account
- GitHub repository
- AWS IAM Role configured for GitHub OIDC
- S3 bucket containing backups
- Python 3.11+ (for local development)
- AWS SAM CLI (for local testing)

## Setup

### 1. AWS OIDC Configuration

Create an IAM OIDC identity provider and role for GitHub Actions:

```bash
# Create OIDC provider (only once per AWS account)
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1

# Create IAM role with trust policy for GitHub
# See AWS documentation for detailed trust policy configuration
```

**Trust Policy Example**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:YOUR_ORG/YOUR_REPO:*"
        }
      }
    }
  ]
}
```

**Required IAM Permissions for the Role**:
- CloudFormation full access (for SAM deployment)
- Lambda full access
- S3 read/write access to backup bucket
- IAM role creation (for Lambda execution role)
- CloudWatch Logs access

### 2. GitHub Secrets Configuration

Add the following secrets to your GitHub repository:

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `AWS_ROLE_ARN` | ARN of the IAM role for OIDC | `arn:aws:iam::123456789012:role/GitHubActionsRole` |
| `BACKUP_BUCKET_NAME` | Name of S3 bucket with backups | `my-backups-bucket` |
| `RETENTION_CONFIG_PATH` | S3 path or JSON config | `s3://my-config-bucket/config.json` |

### 3. Upload Retention Configuration to S3

```bash
# Upload config.json to S3
aws s3 cp config.json s3://my-config-bucket/backup-retention-config.json
```

Or use the configuration directly as a JSON string in the environment variable.

## Deployment

### Automated Deployment (GitHub Actions)

The project automatically deploys when you push to specific branches:

- **Push to `develop`** → Deploys to `dev` environment
- **Push to `main`** → Deploys to `prod` environment
- **Manual trigger** → Choose environment (dev/staging/prod)

```bash
# Push to trigger deployment
git push origin main

# Or trigger manually from GitHub Actions UI
```

### Manual Deployment with SAM CLI

```bash
# Validate template
sam validate --lint

# Deploy to dev
sam deploy \
  --config-env dev \
  --parameter-overrides \
    BucketName=my-backups-bucket \
    RetentionConfigPath=s3://my-config-bucket/config.json

# Deploy to prod
sam deploy \
  --config-env prod \
  --parameter-overrides \
    BucketName=my-backups-bucket \
    RetentionConfigPath=s3://my-config-bucket/config.json
```

## Local Testing

### Test Lambda Function Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Test with SAM CLI
sam local invoke BackupCleanerFunction \
  --parameter-overrides \
    BucketName=my-test-bucket \
    RetentionConfigPath='{"retention_policies":[{"folder":"test/","days_to_keep":30,"min_backups_to_keep":5}]}'
```

### Manual Invocation

```bash
# Invoke deployed Lambda function
aws lambda invoke \
  --function-name backup-cleaner-dev \
  --log-type Tail \
  --query 'LogResult' \
  --output text \
  response.json | base64 --decode

# View response
cat response.json
```

## Configuration Options

### SAM Template Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `BucketName` | S3 bucket containing backups | (required) |
| `RetentionConfigPath` | S3 path or JSON string with config | (required) |
| `ScheduleExpression` | CloudWatch Events schedule | `cron(0 2 * * ? *)` |
| `Environment` | Environment name (dev/staging/prod) | `dev` |

### Lambda Configuration

- **Runtime**: Python 3.11
- **Memory**: 512 MB
- **Timeout**: 300 seconds (5 minutes)
- **Schedule**: Daily at 2 AM UTC (configurable)

## Monitoring

### CloudWatch Logs

View Lambda execution logs:

```bash
# Stream logs
aws logs tail /aws/lambda/backup-cleaner-dev --follow

# Query logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/backup-cleaner-dev \
  --filter-pattern "ERROR"
```

### CloudWatch Insights Queries

```sql
# Count deletions by folder
fields @timestamp, folder, deleted
| filter @message like /processing complete/
| stats sum(deleted) by folder

# Find errors
fields @timestamp, @message
| filter @message like /ERROR/
| sort @timestamp desc
```

## Security Considerations

- **Least Privilege**: Lambda execution role only has access to specified S3 bucket
- **OIDC Authentication**: No long-lived AWS credentials in GitHub
- **Encryption**: Use S3 bucket encryption for backups and config
- **Audit**: All deletions are logged to CloudWatch Logs
- **Protected Backups**: Minimum backup count prevents accidental deletion of all backups

## Troubleshooting

### Common Issues

**Lambda times out**:
- Increase timeout in `template.yaml` (max 900 seconds)
- Reduce number of folders processed per invocation

**Access denied errors**:
- Verify Lambda execution role has S3 permissions
- Check bucket policies and CORS settings

**Config not found**:
- Verify `RETENTION_CONFIG_PATH` is correct
- Ensure Lambda can read from config S3 bucket

**No backups deleted**:
- Check retention policy configuration
- Verify backup timestamps are correct
- Review CloudWatch logs for details

## Cost Estimation

Approximate monthly costs (us-east-1):

- **Lambda**: ~$0.01 (1 daily execution, 512MB, 30s runtime)
- **CloudWatch Logs**: ~$0.50 (500 MB logs/month)
- **S3 API Calls**: ~$0.01 (ListObjects, DeleteObjects)

**Total**: ~$0.52/month

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test locally with SAM
5. Submit a pull request

## License

See [LICENSE](LICENSE) file for details.

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Review CloudWatch logs for debugging
- Check AWS SAM documentation: https://docs.aws.amazon.com/serverless-application-model/

## Changelog

### v1.0.0 (2025-12-24)
- Initial release
- Support for age-based and count-based retention
- GitHub Actions deployment with OIDC
- SAM/CloudFormation infrastructure

