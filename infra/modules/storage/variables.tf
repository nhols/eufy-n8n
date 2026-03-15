variable "bucket_name" {
  type = string
}

variable "video_prefix" {
  type    = string
  default = "videos"
}

variable "video_expiration_days" {
  type    = number
  default = null
}

variable "tags" {
  type    = map(string)
  default = {}
}
