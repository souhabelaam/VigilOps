output "public_ip" {
  description = "Address of the server (changes every time it is created)"
  value       = aws_instance.vigilops.public_ip
}

output "ssh_command" {
  description = "Command to log in (replace the key path with your private key)"
  value       = "ssh -i <private-key> ubuntu@${aws_instance.vigilops.public_ip}"
}
