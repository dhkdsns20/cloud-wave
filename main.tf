provider "aws" {
  region = "ap-northeast-2"
}

resource "aws_launch_configuration" "example" {
  image_id        = "ami-08943a151bd468f4e"
  instance_type   = "t3.micro"
  security_groups = [aws_security_group.instance.id]
  user_data       = <<-EOF
    #!/bin/bash
    echo "hello world" > index.html
    nohup busybox httpd -f -p ${var.server_port} &
    EOF
  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_autoscaling_group" "example" {
  health_check_type    = "ELB"
  launch_configuration = aws_launch_configuration.example.name
  # 특정 서브넷 ID를 직접 지정합니다.
  vpc_zone_identifier = ["subnet-0337b72aa6b2be512"]
  min_size            = 2
  max_size            = 10
  tag {
    key                 = "Name"
    value               = "terraform-asg-example"
    propagate_at_launch = true
  }
}

resource "aws_security_group" "alb" {
  name = "terraform-example-alb"
  vpc_id = "vpc-036c2d9eccbf142be"
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "instance" {
  name = "terraform-example-instance"
  ingress {
    from_port       = var.server_port
    to_port         = var.server_port
    protocol        = "tcp"
    # ALB 보안 그룹에서 오는 트래픽만 허용
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

variable "server_port" {
  description = "The port the server will use for HTTP requests"
  type        = number
  default     = 8080
}

# 기본 VPC를 찾는 data 블록을 삭제하거나, 특정 VPC ID를 사용하도록 수정합니다.
# 이 경우 직접 VPC ID를 지정하거나, 아래와 같이 데이터 소스를 사용합니다.
data "aws_vpc" "custom_vpc" {
  id = "vpc-036c2d9eccbf142be"
}

data "aws_subnets" "custom_subnets" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.custom_vpc.id]
  }
}

resource "aws_lb" "example" {
  name               = "terraform-asg-example-lb"
  load_balancer_type = "application"
  # Auto Scaling Group과 동일한 서브넷을 사용하도록 합니다.
  subnets         = aws_autoscaling_group.example.vpc_zone_identifier
  security_groups = [aws_security_group.alb.id]
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.example.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.asg.arn
  }
}

resource "aws_lb_listener_rule" "asg" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 100
  condition {
    path_pattern {
      values = ["*"]
    }
  }
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.asg.arn
  }
}

resource "aws_lb_target_group" "asg" {
  name     = "terraform-asg-example"
  port     = var.server_port
  protocol = "HTTP"
  # 특정 VPC ID를 직접 지정합니다.
  vpc_id   = data.aws_vpc.custom_vpc.id
  health_check {
    path                = "/"
    protocol            = "HTTP"
    matcher             = "200"
    interval            = 15
    timeout             = 3
    healthy_threshold   = 2
    unhealthy_threshold = 2
  }
}

output "alb_dns_name" {
  value       = aws_lb.example.dns_name
  description = "The domain name of the load balancer"
}