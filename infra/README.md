# Infrastructure

This directory contains a minimal AWS deployment layout for one instance of the
stack.

Current scope:

- one EC2 instance
- one S3 bucket
- one IAM role / instance profile
- EC2 instance in an existing VPC / subnet with a public IPv4
- SSH access restricted by CIDR
- no DNS
- no Terraform-managed secrets

## Layout

- `modules/storage`: S3 bucket and lifecycle configuration
- `modules/iam`: EC2 IAM role, instance profile, and S3 access policy
- `modules/instance`: EC2 instance, security group, and bootstrap user data
- `environments/example`: example environment wiring the modules together
- `scripts/bootstrap.sh.tftpl`: instance bootstrap script used by Terraform
- `scripts/deploy.sh`: local deploy helper to sync the repo, copy `.env`, and start Compose

## Typical flow

1. Copy `infra/environments/example/terraform.tfvars.example` to `terraform.tfvars` and fill in values.
2. Run `terraform init` and `terraform apply` from the environment directory.
3. Use `infra/scripts/deploy.sh` to:
   - sync the repo to the instance
   - copy the `.env`
   - run `docker compose up -d --build`
