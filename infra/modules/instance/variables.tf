variable "name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_id" {
  type = string
}

variable "instance_type" {
  type    = string
  default = "t3.small"
}

variable "instance_profile_name" {
  type = string
}

variable "key_name" {
  type    = string
  default = null
}

variable "ssh_cidr" {
  type    = string
  default = "0.0.0.0/0"
}

variable "root_volume_size_gb" {
  type    = number
  default = 20
}

variable "app_dir" {
  type    = string
  default = "/opt/argusai"
}

variable "user_data_template" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
