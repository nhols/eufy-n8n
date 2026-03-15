output "instance_id" {
  value = module.instance.instance_id
}

output "instance_public_ip" {
  value = module.instance.public_ip
}

output "instance_public_dns" {
  value = module.instance.public_dns
}

output "bucket_name" {
  value = module.storage.bucket_name
}

output "config_key" {
  value = var.config_key
}

output "video_prefix" {
  value = module.storage.video_prefix
}
