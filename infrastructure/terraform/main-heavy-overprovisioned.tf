# Demo: heavily overprovisioned AWS setup (design doc section 30, scenario 3).
# 8 x m5.2xlarge (8 vCPU / 32 GiB each) for an e-commerce workload with
# 10,000 users. Expected result: multiple scale-down recommendations.

provider "aws" {
  region = "ap-south-1"
}

resource "aws_instance" "web" {
  ami           = "ami-0abcd1234efgh5678"
  instance_type = "m5.2xlarge"
  count         = 8

  root_block_device {
    volume_size = 100
    volume_type = "gp3"
  }

  tags = {
    Name = "web-frontend"
  }
}
