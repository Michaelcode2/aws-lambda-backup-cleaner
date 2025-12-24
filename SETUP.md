# Setup Guide: AWS Lambda Backup Cleaner

This guide provides step-by-step instructions for setting up the AWS Lambda Backup Cleaner with GitHub Actions deployment using OIDC.

## Table of Contents

1. [AWS Configuration](#aws-configuration)
2. [GitHub Configuration](#github-configuration)
3. [First Deployment](#first-deployment)
4. [Verification](#verification)

## AWS Configuration

### Step 1: Create IAM OIDC Provider for GitHub

This step is required **once per AWS account**.

```bash
# Create the OIDC provider
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

Verify the provider was created:

```bash
aws iam list-open-id-connect-providers
```

### Step 2: Create IAM Role for GitHub Actions

Create a trust policy file `github-trust-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::YOUR_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:YOUR_GITHUB_ORG/YOUR_REPO_NAME:*"
        }
      }
    }
  ]
}
```

**Important**: Replace:
- `YOUR_ACCOUNT_ID` with your AWS account ID (e.g., `123456789012`)
- `YOUR_GITHUB_ORG/YOUR_REPO_NAME` with your GitHub repository (e.g., `myorg/aws-lambda-backup-cleaner`)

Create the role:

```bash
aws iam create-role \
  --role-name GitHubActionsBackupCleaner \
  --assume-role-policy-document file://github-trust-policy.json \
  --description "Role for GitHub Actions to deploy Lambda Backup Cleaner"
```

### Step 3: Attach Permissions to the Role

Create a permissions policy file `github-permissions-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:CreateStack",
        "cloudformation:UpdateStack",
        "cloudformation:DeleteStack",
        "cloudformation:DescribeStacks",
        "cloudformation:DescribeStackEvents",
        "cloudformation:DescribeStackResources",
        "cloudformation:GetTemplate",
        "cloudformation:ValidateTemplate",
        "cloudformation:CreateChangeSet",
        "cloudformation:GetTemplateSummary",
        "cloudformation:DescribeChangeSet",
        "cloudformation:ExecuteChangeSet",
        "cloudformation:DeleteChangeSet",
        "cloudformation:ListStacks"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "lambda:CreateFunction",
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration",
        "lambda:DeleteFunction",
        "lambda:GetFunction",
        "lambda:GetFunctionConfiguration",
        "lambda:ListFunctions",
        "lambda:AddPermission",
        "lambda:RemovePermission",
        "lambda:InvokeFunction",
        "lambda:TagResource",
        "lambda:UntagResource"
      ],
      "Resource": "arn:aws:lambda:*:*:function:backup-cleaner-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:GetRole",
        "iam:PassRole",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:GetRolePolicy",
        "iam:TagRole",
        "iam:UntagRole"
    ],
      "Resource": "arn:aws:iam::*:role/backup-cleaner-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:GetBucketLocation",
        "s3:GetBucketVersioning"
      ],
      "Resource": [
        "arn:aws:s3:::YOUR_SAM_ARTIFACTS_BUCKET",
        "arn:aws:s3:::YOUR_SAM_ARTIFACTS_BUCKET/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::YOUR_CONFIG_BUCKET/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:DeleteLogGroup",
        "logs:PutRetentionPolicy",
        "logs:DescribeLogGroups",
        "logs:TagResource",
        "logs:UntagResource"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "events:PutRule",
        "events:DeleteRule",
        "events:DescribeRule",
        "events:PutTargets",
        "events:RemoveTargets"
      ],
      "Resource": "*"
    }
  ]
}
```

**Note**: This policy is configured to use the `YOUR-BUCKET` bucket for both SAM artifacts and backup data, organized by prefixes.

Attach the policy:

```bash
aws iam put-role-policy \
  --role-name GitHubActionsBackupCleaner \
  --policy-name BackupCleanerDeploymentPolicy \
  --policy-document file://github-permissions-policy.json
```

### Step 4: Get the Role ARN

```bash
aws iam get-role \
  --role-name GitHubActionsBackupCleaner \
  --query 'Role.Arn' \
  --output text
```

Save this ARN - you'll need it for GitHub secrets.

### Step 5: Verify S3 Bucket

Ensure your S3 bucket exists:

```bash
# Verify bucket exists
aws s3 ls s3://your-backups/

# The bucket will be organized with prefixes:
# YOUR-BUCKET/backup-cleaner-dev/      - SAM deployment artifacts for dev
# YOUR-BUCKET/backup-cleaner-prod/     - SAM deployment artifacts for prod
# YOUR-BUCKET/database-backups/        - Your actual backup files
# YOUR-BUCKET/configs/                 - Configuration files
```

### Step 6: Create and Upload Retention Configuration

Create your `config.json`:

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

Upload to S3:

```bash
# Upload config to YOUR-BUCKET with proper prefix
aws s3 cp config.json s3://YOUR-BUCKET/configs/backup-retention-config.json

# Verify
aws s3 ls s3://YOUR-BUCKET/configs/
```

## GitHub Configuration

### Step 1: Add Repository Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions → New repository secret

Add the following secrets:

| Secret Name | Value | Example |
|-------------|-------|---------|
| `AWS_ROLE_ARN` | ARN from Step 4 | `arn:aws:iam::123456789012:role/GitHubActionsBackupCleaner` |
| `SAM_ARTIFACTS_BUCKET` | S3 bucket for SAM artifacts | `YOUR-BUCKET` |
| `BACKUP_BUCKET_NAME` | Your backup bucket name | `YOUR-BUCKET` |
| `RETENTION_CONFIG_PATH` | S3 path to config | `s3://YOUR-BUCKET/configs/backup-retention-config.json` |
| `SCHEDULE_EXPRESSION` | (Optional) Cron expression | `cron(0 2 * * ? *)` |

### Step 2: Create Environment (Optional)

For production deployments, you can create GitHub environments:

1. Go to Settings → Environments → New environment
2. Create environments: `dev`, `staging`, `prod`
3. Add protection rules (e.g., require approvals for prod)

### Step 3: Configure Branch Protection

1. Go to Settings → Branches → Add branch protection rule
2. For `main` branch:
   - Require pull request reviews
   - Require status checks to pass
   - Require branches to be up to date

## First Deployment

### Option 1: Via GitHub Actions (Recommended)

1. Push to `develop` branch for dev deployment:

```bash
git checkout -b develop
git add .
git commit -m "Initial Lambda backup cleaner setup"
git push origin develop
```

2. Check GitHub Actions tab to monitor deployment

3. For production, merge to `main`:

```bash
git checkout main
git merge develop
git push origin main
```

### Option 2: Manual Deployment with SAM CLI

1. Configure SAM (optional for local deployments):

```bash
# Copy the example config and customize it
cp samconfig.toml.example samconfig.toml

# Edit samconfig.toml with your bucket name and region
# Note: samconfig.toml is gitignored for security
```

2. Install SAM CLI:

```bash
# macOS
brew install aws-sam-cli

# Linux
pip install aws-sam-cli

# Verify
sam --version
```

3. Configure AWS credentials:

```bash
aws configure
```

4. Build and deploy:

```bash
# Validate template
sam validate --lint

# Deploy (guided mode for first time)
sam deploy --guided

# Or deploy with parameters
sam deploy \
  --stack-name backup-cleaner-dev \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    Environment=dev \
    BucketName=my-backups-bucket \
    RetentionConfigPath=s3://my-lambda-configs/backup-retention-config.json
```

## Verification

### 1. Check CloudFormation Stack

```bash
aws cloudformation describe-stacks \
  --stack-name backup-cleaner-dev \
  --query 'Stacks[0].StackStatus'
```

Expected output: `CREATE_COMPLETE` or `UPDATE_COMPLETE`

### 2. Check Lambda Function

```bash
aws lambda get-function \
  --function-name backup-cleaner-dev
```

### 3. Test Lambda Function

```bash
aws lambda invoke \
  --function-name backup-cleaner-dev \
  --log-type Tail \
  --query 'LogResult' \
  --output text \
  response.json | base64 --decode

# View response
cat response.json
```

### 4. Check CloudWatch Logs

```bash
# Get recent logs
aws logs tail /aws/lambda/backup-cleaner-dev --follow

# Or via AWS Console
# Navigate to CloudWatch → Log groups → /aws/lambda/backup-cleaner-dev
```

### 5. Verify Scheduled Event

```bash
aws events list-rules --query 'Rules[?contains(Name, `backup-cleaner`)].{Name:Name,Schedule:ScheduleExpression}'
```

## Troubleshooting

### OIDC Provider Already Exists

If you get an error that the OIDC provider already exists, that's okay - it means it was created before. You can list existing providers:

```bash
aws iam list-open-id-connect-providers
```

### Permission Denied During Deployment

1. Verify the role ARN is correct in GitHub secrets
2. Check the trust policy allows your repository
3. Ensure all required permissions are attached

### Lambda Can't Access S3 Bucket

1. Check bucket policy allows Lambda execution role
2. Verify bucket name in environment variables
3. Check Lambda execution role has S3 permissions

### Config Not Found

1. Verify config file exists in S3:
   ```bash
   aws s3 ls s3://my-lambda-configs/backup-retention-config.json
   ```
2. Check `RETENTION_CONFIG_PATH` environment variable
3. Ensure Lambda role can read from config bucket

## Next Steps

1. **Test with sample backups**: Upload test files to your backup folders
2. **Monitor logs**: Watch CloudWatch Logs during scheduled executions
3. **Adjust retention policies**: Modify config.json and re-upload to S3
4. **Set up alerts**: Create CloudWatch alarms for Lambda errors
5. **Review costs**: Monitor Lambda invocations and S3 operations in AWS Cost Explorer

## Additional Resources

- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [GitHub Actions OIDC with AWS](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [CloudWatch Events Schedule Expressions](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-rule-schedule.html)

