output "region" {
  value = var.region
}

output "vpc_id" {
  value = aws_vpc.t0.id
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}

output "public_subnet_id" {
  value = aws_subnet.public.id
}

output "runtime_security_group_id" {
  value = aws_security_group.runtime.id
}

output "object_bucket_name" {
  value = aws_s3_bucket.objects.id
}

output "ecr_repository_urls" {
  value = { for name, repository in aws_ecr_repository.runtime : name => repository.repository_url }
}

output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.t0.id
}

output "cognito_web_client_id" {
  value = aws_cognito_user_pool_client.web.id
}

output "cognito_domain" {
  value = aws_cognito_user_pool_domain.t0.domain
}

output "runtime_instance_profile" {
  value = aws_iam_instance_profile.runtime.name
}

output "cloudtrail_name" {
  value = aws_cloudtrail.t0.name
}
