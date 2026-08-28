output "instance_id" {
  value = aws_instance.beta.id
}

output "public_ipv4" {
  value = aws_eip.beta.public_ip
}

output "required_dns_record" {
  value = {
    type  = "A"
    name  = var.beta_domain
    value = aws_eip.beta.public_ip
    ttl   = 300
  }
}

output "public_url" {
  value = "https://${var.beta_domain}"
}

output "ssm_command" {
  value = "aws ssm start-session --profile fincilia-sandbox --target ${aws_instance.beta.id}"
}

output "release_sha" {
  value = var.release_sha
}
