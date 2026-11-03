# The network that already exists in every AWS account: we reuse it instead of building one.
data "aws_vpc" "default" {
  default = true
}

# Look up the newest official Ubuntu 24.04 image instead of hard-coding an id that goes out of date.
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical, the company that makes Ubuntu

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
}

# The firewall: nothing gets in unless a rule below says so.
resource "aws_security_group" "vigilops" {
  name        = "vigilops-demo"
  description = "VigilOps demo server: only my IP can connect"
  vpc_id      = data.aws_vpc.default.id

  tags = { Name = "vigilops-demo" }
}

resource "aws_vpc_security_group_ingress_rule" "ssh" {
  security_group_id = aws_security_group.vigilops.id
  description       = "SSH from my IP only"
  cidr_ipv4         = var.my_ip_cidr
  ip_protocol       = "tcp"
  from_port         = 22
  to_port           = 22
}

resource "aws_vpc_security_group_ingress_rule" "kube_api" {
  security_group_id = aws_security_group.vigilops.id
  description       = "Kubernetes API (kubectl) from my IP only"
  cidr_ipv4         = var.my_ip_cidr
  ip_protocol       = "tcp"
  from_port         = 6443
  to_port           = 6443
}

resource "aws_vpc_security_group_ingress_rule" "apps" {
  security_group_id = aws_security_group.vigilops.id
  description       = "NodePorts of notes-api (30002) and report-api (30003) from my IP only"
  cidr_ipv4         = var.my_ip_cidr
  ip_protocol       = "tcp"
  from_port         = 30002
  to_port           = 30003
}

# The server needs to download packages and images, so it may open connections to anywhere.
resource "aws_vpc_security_group_egress_rule" "all_out" {
  security_group_id = aws_security_group.vigilops.id
  description       = "Outgoing traffic: updates, k3s, image pulls"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

# Uploads YOUR public key to AWS. The private key never leaves your laptop.
resource "aws_key_pair" "vigilops" {
  key_name   = "vigilops-demo"
  public_key = file(var.public_key_path)
}

# The server itself.
# Two Checkov findings are accepted on purpose (a skip must always say why):
resource "aws_instance" "vigilops" {
  #checkov:skip=CKV_AWS_126:Detailed (1 minute) monitoring costs extra and the server lives about 30 minutes; Prometheus monitors it.
  #checkov:skip=CKV2_AWS_41:The Learner Lab does not allow creating IAM roles and the server never calls AWS, so a role would only add rights.
  ami                    = data.aws_ami.ubuntu.id
  ebs_optimized          = true
  instance_type          = var.instance_type
  key_name               = aws_key_pair.vigilops.key_name
  vpc_security_group_ids = [aws_security_group.vigilops.id]

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
    encrypted   = true
  }

  # Version 2 of the instance metadata service: blocks a class of "steal the server's credentials" attacks.
  metadata_options {
    http_tokens = "required"
  }

  tags = { Name = "vigilops-demo" }
}
