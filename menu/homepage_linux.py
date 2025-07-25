import time
import boto3
import psutil
import requests
import pandas as pd
import streamlit as st

from widget.side_bar import start_process

class Homepage:
    def __init__(self):
        self.homepage()

    def get_token(self):
        url = "http://169.254.169.254/latest/api/token"
        headers = {"X-aws-ec2-metadata-token-ttl-seconds": "3600"}
        response = requests.put(url, headers=headers)
        return response.text

    def get_instance_metadata(self, token, endpoint):
        url = f"http://169.254.169.254/latest/meta-data/{endpoint}"
        headers = {"X-aws-ec2-metadata-token": token}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.text
        else:
            return None

    def get_instance_name_tag(self, ec2_client, instance_id):
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        
        for reservation in response["Reservations"]:
            for instance in reservation["Instances"]:
                # 태그 목록 내에서 'Name' 키를 가진 태그를 찾는다.
                name_tag = next((tag['Value'] for tag in instance.get('Tags', []) if tag['Key'] == 'Name'), None)
                # 'Name' 태그 값 반환
                if name_tag:
                    return name_tag  
        return None

    def server_monitoring(self):
        # 상태 표시할 빈 컨테이너 생성
        col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
        cpu_slot = col1.empty()
        memory_slot = col2.empty()
        disk_usage_slot = col3.empty()
        uptime_slot = col4.empty()
        load_avg_slot_1 = col5.empty()
        load_avg_slot_5 = col6.empty()
        load_avg_slot_15 = col7.empty()

        # CPU 및 메모리 정보를 실시간으로 업데이트
        while True:
            # 메트릭 정보 수집
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk_usage = psutil.disk_usage('/')
            load_average = psutil.getloadavg()
            uptime_seconds = time.time() - psutil.boot_time()

            # 컬럼에 메트릭 정보 표시
            cpu_slot.metric(label="CPU Usage", value=cpu_percent)
            memory_slot.metric(label="Memory Usage", value=memory.percent)
            disk_usage_slot.metric(label="Disk Usage", value=disk_usage.percent)

            uptime_info = f"{uptime_seconds / 60:,.0f} M"
            uptime_slot.metric(label="Uptime", value=uptime_info)

            load_avg_slot_1.metric(label="Load Avg(1)", value=f"{load_average[0]:.2f}")
            load_avg_slot_5.metric(label="Load Avg(5)", value=f"{load_average[1]:.2f}")
            load_avg_slot_15.metric(label="Load Avg(15)", value=f"{load_average[2]:.2f}")

            # 1초간 쉬었다가 계속 진행 (데이터 새로고침 간격)
            time.sleep(1)

    def homepage(self):
        st.title("AWS AutoScalingGroup EC2 Information")
        # Monitoring and Load Button ----------
        col1, col2, col3 = st.columns([1, 1, 8])
        with col1:
            st.markdown("<span style='font-size: 15px; text-align: center;'>Start Monitoring</span>", unsafe_allow_html=True)
            placeholder_button = st.empty()
        with col2:
            st.markdown("<span style='font-size: 15px; text-align: center;'>Start Stress Test</span>", unsafe_allow_html=True)
            placeholder_stress = st.empty()
        with col3:
            placeholder_monitoring = st.empty()
        
        # Side-bar for entering timeout value of stress tool
        with st.sidebar:
            st.sidebar.header('System Control Panner')
            timeout = st.sidebar.number_input('Enter timeout for the stress test:', value=300)
            
            
        # EC2 Information area --------------------------------
        st.header('AutoScalingGroup Instance Information', divider = "gray")
        
        # AutoScaling Group에서 인스턴스 목록 가져오기
        token = self.get_token()
        region = self.get_instance_metadata(token, "placement/region")
        ec2_client = boto3.client('ec2', region_name=region)
        autoscaling_client = boto3.client('autoscaling', region_name=region)
        asg_name = "lab-edu-asg-web"
            
        instances_info = []
        try:
            asg_response = autoscaling_client.describe_auto_scaling_groups(
                AutoScalingGroupNames=[asg_name]
            )
            
            if not asg_response['AutoScalingGroups']:
                st.error(f"Unable to retrieve instance information.")
                return
            
            # ASG의 인스턴스 ID 목록 추출
            asg_instances = asg_response['AutoScalingGroups'][0]['Instances']
            instance_ids = [instance['InstanceId'] for instance in asg_instances if instance['LifecycleState'] == 'InService']
            
            if not instance_ids:
                st.warning(f"Unable to retrieve instance information.")
                return
            
            # EC2 인스턴스 세부 정보 가져오기
            ec2_response = ec2_client.describe_instances(InstanceIds=instance_ids)
            
            for reservation in ec2_response['Reservations']:
                for instance in reservation['Instances']:
                    instance_name = "N/A"
                    if 'Tags' in instance:
                        for tag in instance['Tags']:
                            if tag['Key'] == 'Name':
                                instance_name = tag['Value']
                                break
                    
                    # 인스턴스 정보 수집
                    instance_info = {
                        "Name": instance_name,
                        "Instance ID": instance['InstanceId'],
                        "Instance Type": instance['InstanceType'],
                        "State": instance['State']['Name'],
                        "Availability Zone": instance['Placement']['AvailabilityZone'],
                        "Private IP": instance.get('PrivateIpAddress', 'N/A'),
                        "Public IP": instance.get('PublicIpAddress', 'N/A'),
                        "Launch Time": instance['LaunchTime'].strftime('%Y-%m-%d %H:%M:%S')
                    }
                    instances_info.append(instance_info)
            
            # DataFrame 생성 및 테이블 출력
            if instances_info:
                df = pd.DataFrame(instances_info)
                st.subheader(f"EC2 Information Table: {asg_name}")
                st.table(df)
            else:
                st.warning("Unable to retrieve instance information.")

        except Exception as e:
            st.error(f"Error Message: {str(e)}")
            st.info("Replace with current instance information.")
            current_instance_id = self.get_instance_metadata(token, "instance-id")
            name_tag = self.get_instance_name_tag(ec2_client, current_instance_id)
            metadata_info = {
                "Name": name_tag,
                "Instance ID": current_instance_id,
                "Instance Type": self.get_instance_metadata(token, "instance-type"),
                "Region": region,
                "Availability Zone": self.get_instance_metadata(token, "placement/availability-zone"),
                "Private IP": self.get_instance_metadata(token, "local-ipv4"),
                "Public IP": self.get_instance_metadata(token, "public-ipv4"),
            }
            df = pd.DataFrame(list(metadata_info.items()), columns=['Metadata', 'Value'])
            st.table(df)
        

        # EBS Volume Information area --------------------------
        st.subheader(f'EBS Information Table: {asg_name}')
        
        # GET EBS Information TABLE format
        volume_data = []
        for instance_info in instances_info:
            instance_id = instance_info['Instance ID']
            volumes = ec2_client.describe_volumes(Filters=[{'Name': 'attachment.instance-id', 'Values': [instance_id]}])
            for volume in volumes['Volumes']:
                # volume_metadata_info = {}
                volume_data.append({
                    'Instance ID': instance_id,
                    'Volume ID': volume['VolumeId'],
                    'Type': volume['VolumeType'],
                    'Size (GB)': volume['Size'],
                    'State': volume['State'],
                    'Snapshot ID': volume.get('SnapshotId', 'N/A'),
                    'IOPS': volume.get('Iops', 'N/A'),
                    'Encrypted': volume['Encrypted'],
                    'Creation Date': volume['CreateTime'].strftime('%Y-%m-%d %H:%M:%S')
                })
        st.table(volume_data)

        with placeholder_button.container():
            if st.button("Push Button", use_container_width=True):
                with placeholder_stress.container():
                    if st.button("Stress Tool", use_container_width=True):
                        start_process(timeout)
                with placeholder_monitoring: self.server_monitoring()


        with placeholder_stress.container():
            if st.button("Stress Tool", use_container_width=True):
                start_process(timeout)
                with placeholder_monitoring: self.server_monitoring()