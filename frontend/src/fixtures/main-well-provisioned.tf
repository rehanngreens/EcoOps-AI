# Demo: well-provisioned AWS setup (design doc section 30, scenario 1).
# 2 x t3.medium (2 vCPU / 4 GiB each) serving a modest API workload.
# Expected result: few or no recommendations.

provider "aws" {
  region = "ap-south-1"
}

resource "aws_instance" "api" {
  ami           = "ami-0abcd1234efgh5678"
  instance_type = "t3.medium"
  count         = 2

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  tags = {
    Name = "api-backend"
  }
}
