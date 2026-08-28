output "state_bucket_name" {
  description = "Bucket remoto del estado T0."
  value       = aws_s3_bucket.state.id
}
