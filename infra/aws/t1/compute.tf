locals {
  user_data = templatefile("${path.module}/runtime/cloud-init.sh.tftpl", {
    bundle_uri      = "s3://${data.terraform_remote_state.t0.outputs.object_bucket_name}/${local.bundle_prefix}"
    compose_version = "5.5.0"
    compose_sha256  = "c57ab918abd5b05ca7e7d0f275875dd1330a695074f309dc9eab1b49efafcd4b"
    registry        = local.registry
  })
}

resource "aws_instance" "runtime" {
  ami                                  = "ami-0ae4c9718ffae6ca6"
  instance_type                        = "t3.small"
  subnet_id                            = data.terraform_remote_state.t0.outputs.public_subnet_id
  vpc_security_group_ids               = [data.terraform_remote_state.t0.outputs.runtime_security_group_id]
  iam_instance_profile                 = data.terraform_remote_state.t0.outputs.runtime_instance_profile
  associate_public_ip_address          = true
  monitoring                           = false
  user_data                            = local.user_data
  user_data_replace_on_change          = true
  instance_initiated_shutdown_behavior = "stop"

  credit_specification {
    cpu_credits = "standard"
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "disabled"
  }

  root_block_device {
    encrypted             = true
    volume_type           = "gp3"
    volume_size           = 16
    delete_on_termination = true
    iops                  = 3000
    throughput            = 125
  }

  tags = { Name = "fincilia-t1-remote-lab" }

  lifecycle {
    precondition {
      condition     = length(regexall("FINCILIA_REAL_DATA_ENABLED=false", local.bundle_files["up.sh"])) == 1
      error_message = "el bundle debe mantener datos reales deshabilitados."
    }
  }

  depends_on = [aws_s3_object.runtime, aws_iam_role_policy.runtime_bundle]
}
