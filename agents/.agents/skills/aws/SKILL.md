---
name: aws
description: AWS work of any kind (Bedrock, SageMaker, Cognito, CDK, CloudFormation, EC2, containers, databases, CI/CD, IAM, messaging, networking, CloudWatch, SDKs, security, serverless, storage, billing, credentials). Pick the matching guide from this skill's table and read only that one.
---

# AWS guides

Each AWS area has its own guide under this folder. Pick the one row that matches
the task, read `aws/<guide>/GUIDE.md`, and follow it. Read a second guide only
when the task crosses into its area. When the AWS MCP server is connected,
prefer its tools for running commands and its `retrieve_skill` for any skill not
listed here.

The guides were written as standalone skills. Where one says `SKILL.md`, it
means its own `GUIDE.md`, and "the X skill" means the X guide in this table.
Paths such as `references/` resolve from the guide's own folder.

| Guide | Use for |
| --- | --- |
| `signing-in-to-aws` | Getting CLI/SDK credentials with `aws login`, or fixing expired or missing credentials |
| `amazon-bedrock` | Bedrock model calls, Knowledge Bases, Agents, Guardrails, AgentCore, prompt caching, throttling |
| `aws-ai-ml` | SageMaker fine-tuning, model selection, evaluation, endpoints and their diagnostics |
| `aws-auth` | Cognito user and identity pools, sign-in flows, OAuth/OIDC, JWT authorizers |
| `aws-billing-and-cost-management` | Cost analysis, budgets, Savings Plans, right-sizing, pricing, CUR, Free Tier |
| `aws-blocks` | Apps built with the AWS Blocks infrastructure-from-code framework |
| `launch-with-aws` | Moving an existing web app onto AWS using AWS Blocks |
| `aws-cdk` | CDK in TypeScript or Python: constructs, synth/deploy, drift, refactors |
| `aws-cloudformation` | CloudFormation templates: authoring, cfn-lint/guard validation, failed stacks |
| `aws-compute` | EC2, Auto Scaling groups, launch templates, IMDSv2, SSM fleet operations |
| `aws-containers` | EKS, ECS, Fargate, ECR and Elastic Beanstalk |
| `aws-database` | Choosing or running Aurora, RDS, DSQL, DynamoDB, DocumentDB, Neptune, ElastiCache and others |
| `aws-deployment` | CodePipeline, CodeBuild, CodeDeploy, CodeConnections, CodeArtifact |
| `aws-iam` | IAM and bucket policies, trust policies, STS, Organizations, service roles |
| `aws-messaging-and-streaming` | SQS, SNS, EventBridge, MQ, Kinesis, Firehose, MSK, Flink; routes SES and SMS |
| `aws-networking` | Route 53, CloudFront, Transit Gateway, Direct Connect, VPN, WAF, Shield |
| `aws-observability` | CloudWatch logs, alarms, Application Signals, Omni queries and dashboards |
| `setting-up-cloudwatch-observability` | First-time CloudWatch Omni setup: spaces, access, ingestion, ADOT |
| `aws-sdk-js-v3-usage` | JavaScript/TypeScript code using `@aws-sdk/*` |
| `aws-sdk-python-usage` | Python code using boto3 or botocore |
| `aws-sdk-swift-usage` | Swift code using `aws-sdk-swift` |
| `aws-security` | Security Hub, GuardDuty, Inspector, KMS, Secrets Manager and other security services |
| `aws-serverless` | Lambda, API Gateway, Step Functions, SAM |
| `aws-storage` | S3, EFS, FSx, EBS: choosing, cost, performance, troubleshooting |
