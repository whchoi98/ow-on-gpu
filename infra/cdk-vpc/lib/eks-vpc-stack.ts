import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';

const VPC_CIDR = '10.200.0.0/16';
const AZS = ['ap-northeast-2a', 'ap-northeast-2b', 'ap-northeast-2c', 'ap-northeast-2d'];

// ecr.api, ecr.dkr, sts, eks 엔드포인트 서비스는 ap-northeast-2d를 지원하지 않는다
// (aws ec2 describe-vpc-endpoint-services, 2026-11-14 확인). 2d의 워크로드는 프라이빗 DNS로
// 다른 가용 영역의 엔드포인트 ENI에 도달한다.
const AZS_WITHOUT_2D = AZS.filter((az) => az !== 'ap-northeast-2d');

const S = ec2.InterfaceVpcEndpointAwsService;
const INTERFACE_ENDPOINTS: { id: string; service: ec2.InterfaceVpcEndpointAwsService; azs: string[] }[] = [
  { id: 'BedrockRuntime', service: S.BEDROCK_RUNTIME, azs: AZS },
  { id: 'EcrApi', service: S.ECR, azs: AZS_WITHOUT_2D },
  { id: 'EcrDkr', service: S.ECR_DOCKER, azs: AZS_WITHOUT_2D },
  { id: 'Logs', service: S.CLOUDWATCH_LOGS, azs: AZS },
  { id: 'Ssm', service: S.SSM, azs: AZS },
  { id: 'SsmMessages', service: S.SSM_MESSAGES, azs: AZS },
  { id: 'Ec2Messages', service: S.EC2_MESSAGES, azs: AZS },
  { id: 'Sts', service: S.STS, azs: AZS_WITHOUT_2D },
  { id: 'Eks', service: S.EKS, azs: AZS_WITHOUT_2D },
  { id: 'EksAuth', service: S.EKS_AUTH, azs: AZS },
  { id: 'Elb', service: S.ELASTIC_LOAD_BALANCING, azs: AZS },
];

export class EksVpcStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: cdk.StackProps) {
    super(scope, id, props);

    const vpc = new ec2.Vpc(this, 'Vpc', {
      vpcName: 'eks-vpc',
      ipAddresses: ec2.IpAddresses.cidr(VPC_CIDR),
      availabilityZones: AZS,
      enableDnsSupport: true,
      enableDnsHostnames: true,
      natGateways: AZS.length,
      // CIDR은 선언 순서대로, 각 마스크 경계에 맞춰 배정된다.
      // Public 10.200.0.0/24부터, Private 10.200.16.0/20부터, Isolated 10.200.80.0/23부터.
      subnetConfiguration: [
        { name: 'Public', subnetType: ec2.SubnetType.PUBLIC, cidrMask: 24, mapPublicIpOnLaunch: true },
        { name: 'Private', subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS, cidrMask: 20 },
        { name: 'Isolated', subnetType: ec2.SubnetType.PRIVATE_ISOLATED, cidrMask: 23 },
      ],
    });

    // 서브넷 construct 아래에는 라우팅 테이블, EIP, NAT도 있으므로 태그 대상을 서브넷으로 한정한다.
    const subnetOnly = { includeResourceTypes: ['AWS::EC2::Subnet'] };
    vpc.publicSubnets.forEach((s) => cdk.Tags.of(s).add('kubernetes.io/role/elb', '1', subnetOnly));
    vpc.privateSubnets.forEach((s) => cdk.Tags.of(s).add('kubernetes.io/role/internal-elb', '1', subnetOnly));

    const s3 = vpc.addGatewayEndpoint('S3', { service: ec2.GatewayVpcEndpointAwsService.S3 });
    const dynamoDb = vpc.addGatewayEndpoint('DynamoDb', {
      service: ec2.GatewayVpcEndpointAwsService.DYNAMODB,
      subnets: [
        { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
        { subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
      ],
    });

    const endpointSg = new ec2.SecurityGroup(this, 'EndpointSg', {
      vpc,
      description: 'Interface endpoints: HTTPS from the VPC CIDR only',
      allowAllOutbound: false,
    });
    endpointSg.addIngressRule(ec2.Peer.ipv4(VPC_CIDR), ec2.Port.tcp(443), 'HTTPS from the VPC CIDR');

    new cdk.CfnOutput(this, 'VpcId', { value: vpc.vpcId });

    const subnetGroups = { Public: vpc.publicSubnets, Private: vpc.privateSubnets, Isolated: vpc.isolatedSubnets };
    for (const [group, subnets] of Object.entries(subnetGroups)) {
      for (const s of subnets) {
        new cdk.CfnOutput(this, `${group}Subnet${azSuffix(s)}`, {
          value: `${s.subnetId} (${s.availabilityZone})`,
        });
      }
    }

    for (const s of vpc.publicSubnets) {
      const nat = s.node.findChild('NATGateway') as ec2.CfnNatGateway;
      new cdk.CfnOutput(this, `NatGateway${azSuffix(s)}`, { value: `${nat.ref} (${s.availabilityZone})` });
    }

    new cdk.CfnOutput(this, 'S3EndpointId', { value: s3.vpcEndpointId });
    new cdk.CfnOutput(this, 'DynamoDbEndpointId', { value: dynamoDb.vpcEndpointId });

    for (const e of INTERFACE_ENDPOINTS) {
      const endpoint = vpc.addInterfaceEndpoint(e.id, {
        service: e.service,
        privateDnsEnabled: true,
        subnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS, availabilityZones: e.azs },
        securityGroups: [endpointSg],
        open: false,
      });
      new cdk.CfnOutput(this, `${e.id}EndpointId`, { value: endpoint.vpcEndpointId });
    }
  }
}

// 'ap-northeast-2a' -> '2a'. 출력 이름에 쓴다.
function azSuffix(subnet: ec2.ISubnet): string {
  return subnet.availabilityZone.slice(-2);
}
