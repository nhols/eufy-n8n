variable "name" {
  type = string
}

variable "bucket_arn" {
  type = string
}

variable "config_key" {
  type = string
}

variable "video_prefix" {
  type = string
}

variable "enable_bookings_read" {
  type    = bool
  default = false
}

variable "tags" {
  type    = map(string)
  default = {}
}
