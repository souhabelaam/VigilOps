variable "region" {
  description = "AWS region. The Learner Lab only allows us-east-1 and us-west-2."
  type        = string
  default     = "us-east-1"
}

variable "instance_type" {
  description = "Server size. t3.medium = 2 vCPU, 4 GB: enough for k3s plus the 10 pods, about 0.04 USD per hour."
  type        = string
  default     = "t3.medium"
}

variable "my_ip_cidr" {
  description = "Your public IP followed by /32 (example 203.0.113.7/32). Only this address can reach the server. No default on purpose: you must choose."
  type        = string
}

variable "public_key_path" {
  description = "Path to the SSH PUBLIC key (.pub) that will be allowed to log in."
  type        = string
}
