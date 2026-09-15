# Demo: moderately overprovisioned AWS setup (design doc section 30, scenario 2).
# 3 x t3.large (2 vCPU / 8 GiB each) for the same workload profile as the
# well-provisioned demo. Expected result: some scale-down recommendations.
# NOTE: count and instance_type are literal values; the parser does not
# support variable interpolation.

provider "aws" {
  region = "ap-south-1"
}

resource "aws_instance" "api" {
  ami           = "ami-0abcd1234efgh5678"
  instance_type = "t3.large"
  count         = 3

  root_block_device {
    volume_size = 40
    volume_type = "gp3"
  }

  tags = {
    Name = "api-backend"
  }
}
