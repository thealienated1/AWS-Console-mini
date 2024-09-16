import boto3

# VPC Creation
def create_vpc(vpc_name, region, cidr_block, subnet_configs=None):
    """Creates a VPC with specified parameters and optionally sets up subnets, an internet gateway, a route table, and a security group."""
    ec2 = boto3.client('ec2', region_name=region)

    # Create VPC
    vpc = ec2.create_vpc(CidrBlock=cidr_block)
    vpc_id = vpc['Vpc']['VpcId']
    print(f"VPC {vpc_name} created with ID: {vpc_id} in region {region}")

    # Add a name tag to the VPC
    ec2.create_tags(Resources=[vpc_id], Tags=[{'Key': 'Name', 'Value': vpc_name}])

    # Enable DNS support and DNS hostnames
    ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsSupport={'Value': True})
    ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsHostnames={'Value': True})

    # Create subnets, internet gateway, route table, and security group if subnet configurations are provided
    if subnet_configs:
        subnets = create_subnets(ec2, vpc_id, subnet_configs)
        ig_id = create_internet_gateway(ec2, vpc_id)
        route_table_id = create_route_table(ec2, vpc_id, subnets)
        security_group_id = create_security_group(ec2, vpc_id, vpc_name)

    return vpc_id

# Subnet Creation
def create_subnets(ec2, vpc_id, subnet_configs):
    """Creates public and private subnets for a VPC and returns the subnet IDs."""
    subnets = []
    for i, config in enumerate(subnet_configs):
        subnet = ec2.create_subnet(
            VpcId=vpc_id,
            CidrBlock=config['CidrBlock'],
            AvailabilityZone=config['AvailabilityZone']
        )
        subnet_id = subnet['Subnet']['SubnetId']
        subnets.append(subnet_id)
        print(f"{config['Type']} Subnet ID: {subnet_id}")

        # Add a tag to identify the subnet
        ec2.create_tags(Resources=[subnet_id], Tags=[{'Key': 'Name', 'Value': f"{config['Type']}_subnet-{i+1}"}])

    return subnets

# EC2 Instance Creation
def create_ec2_instance(region):
    """Creates EC2 instances with customizable VPC, subnet, and security group."""
    
    ec2_resource = boto3.resource('ec2', region_name=region)
    ec2_client = boto3.client('ec2', region_name=region)

    # Get user input for the number of instances
    num_instances = int(input("Enter the number of EC2 instances to create: "))

    # Instance default parameters
    instance_defaults = {
        'ImageId': 'ami-0e86e20dae9224db8',  # AMI
        'NetworkInterfaces': [{
            'AssociatePublicIpAddress': True,
            'DeviceIndex': 0
        }]
    }

    # Fetch available VPCs, subnets, and security groups
    vpcs = ec2_resource.vpcs.all()
    vpc_id = select_vpc(vpcs)

    subnets = list_subnets(ec2_client, vpc_id)
    subnet_id = select_subnet(subnets)

    security_groups = ec2_resource.security_groups.filter(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])
    sg_id = select_security_group(security_groups)

    for i in range(num_instances):
        instance_type = input("Enter instance type (e.g., t2.micro): ")
        volume_size = int(input("Enter storage size (min 8GB): "))

        # Update instance configuration with user selections
        instance_defaults['NetworkInterfaces'][0]['SubnetId'] = subnet_id
        instance_defaults['NetworkInterfaces'][0]['Groups'] = [sg_id]

        # Create the EC2 instance
        instance = ec2_resource.create_instances(
            **instance_defaults,
            MinCount=1,
            MaxCount=1,
            InstanceType=instance_type,
            BlockDeviceMappings=[
                {
                    'DeviceName': '/dev/sda1',
                    'Ebs': {
                        'VolumeSize': volume_size
                    }
                }
            ]
        )[0]

        instance.wait_until_running()
        instance.reload()

        # Display instance details
        print(f"Instance ID: {instance.id}")
        print(f"Public IP: {instance.public_ip_address}, Private IP: {instance.private_ip_address}")

# Helper function for VPC selection
def select_vpc(vpcs):
    vpc_options = [(vpc['VpcId'], vpc.get('Tags', [])) for vpc in vpcs]
    while True:
        print("Available VPCs:")
        for vpc_id, tags in vpc_options:
            tag_name = next((tag['Value'] for tag in tags if tag['Key'] == 'Name'), 'No Name')
            print(f"- {vpc_id}: {tag_name}")
        vpc_id = input("Enter the VPC ID: ")
        if vpc_id in [vpc_id for vpc_id, _ in vpc_options]:
            return vpc_id
        print("Invalid VPC ID. Please try again.")

# Helper function for subnet selection
def select_subnet(subnets):
    while True:
        print("Available Subnets:")
        for subnet in subnets:
            print(f"- {subnet['SubnetId']} ({subnet['CidrBlock']})")
        subnet_id = input("Enter the subnet ID: ")
        if subnet_id in [subnet['SubnetId'] for subnet in subnets]:
            return subnet_id
        print("Invalid subnet ID. Please try again.")

# Helper function for security group selection
def select_security_group(security_groups):
    sg_options = [(sg.id, sg.tags) for sg in security_groups]
    while True:
        print("Available Security Groups:")
        for sg_id, tags in sg_options:
            print(f"- {sg_id}: {tags}")
        sg_id = input("Enter the security group ID: ")
        if sg_id in [sg_id for sg_id, _ in sg_options]:
            return sg_id
        print("Invalid security group ID. Please try again.")

# List subnets in a VPC
def list_subnets(ec2, vpc_id):
    """Lists all available subnets within a specified VPC."""
    subnets = ec2.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])
    return subnets['Subnets']

# Create an Internet Gateway
def create_internet_gateway(ec2, vpc_id):
    """Creates and attaches an Internet Gateway to the VPC."""
    ig = ec2.create_internet_gateway()
    ig_id = ig['InternetGateway']['InternetGatewayId']
    ec2.attach_internet_gateway(InternetGatewayId=ig_id, VpcId=vpc_id)
    print(f"Internet Gateway {ig_id} attached to VPC {vpc_id}")
    return ig_id

# Subnet action function
def create_subnet(vpc_id, cidr_block, availability_zone, subnet_type, region):
    """Creates a subnet within the specified VPC and returns the subnet ID."""
    ec2 = boto3.client('ec2', region_name=region)

    # Create subnet
    subnet = ec2.create_subnet(
        VpcId=vpc_id,
        CidrBlock=cidr_block,
        AvailabilityZone=availability_zone
    )
    subnet_id = subnet['Subnet']['SubnetId']
    print(f"Subnet {subnet_type} created with ID: {subnet_id}")

    # Add a name tag to the subnet
    ec2.create_tags(Resources=[subnet_id], Tags=[{'Key': 'Name', 'Value': subnet_type}])

    return subnet_id

# Main function
def main():
    ec2_client = boto3.client('ec2')

    action = input("Enter action (vpc/ec2/subnet/internet gateway): ").strip().lower()

    if action == "vpc":
        vpc_name = input("Enter VPC name: ")
        region = input("Enter region (e.g., us-east-1): ")
        cidr_block = input("Enter VPC CIDR block: ")
        create_vpc(vpc_name, region, cidr_block)

    elif action == "ec2":
        region = input("Enter region: ")
        create_ec2_instance(region)

    elif action == "subnet":
        region = input("Enter region (e.g., us-east-1): ")
        vpcs = ec2_client.describe_vpcs()
        vpc_id = select_vpc(vpcs['Vpcs'])

        cidr_block = input("Enter subnet CIDR block: ")
        availability_zone = input("Enter availability zone: ")
        subnet_type = input("Enter subnet type (public/private): ")
        create_subnet(vpc_id, cidr_block, availability_zone, subnet_type, region)

if __name__ == "__main__":
    main()
