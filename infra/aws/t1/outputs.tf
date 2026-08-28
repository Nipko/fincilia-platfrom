output "instance_id" {
  value = aws_instance.runtime.id
}

output "instance_state" {
  value = aws_instance.runtime.instance_state
}

output "ssm_web_tunnel_command" {
  value = "aws ssm start-session --profile fincilia-sandbox --target ${aws_instance.runtime.id} --document-name AWS-StartPortForwardingSession --parameters portNumber=53000,localPortNumber=53000"
}

output "release_sha" {
  value = var.release_sha
}
