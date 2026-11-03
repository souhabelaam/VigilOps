terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.region
  # No credentials here on purpose: Terraform reads AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY and
  # AWS_SESSION_TOKEN from your terminal. They are temporary and must never be written in a file.
}
