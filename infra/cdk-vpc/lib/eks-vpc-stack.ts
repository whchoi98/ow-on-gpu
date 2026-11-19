import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';

export interface EksVpcStackProps extends cdk.StackProps {
  vpcCidr: string;
  azs: string[];
  // ecr.api, ecr.dkr, sts, eks 엔드포인트 서비스가 지원하지 않는 AZ. 이 네 서비스의 엔드포인트는 이 AZ를 빼고 만든다.
  // 그 AZ의 워크로드는 프라이빗 DNS로 다른 가용 영역의 엔드포인트 ENI에 도달한다.
  azsWithoutCoreEndpoints?: string[];
}

const S = ec2.InterfaceVpcEndpointAwsService;
// core가 true인 서비스는 azsWithoutCoreEndpoints의 AZ를 뺀다.
const INTERFACE_ENDPOINTS: { id: string; service: ec2.InterfaceVpcEndpointAwsService; core?: boolean }[] = [
  { id: 'BedrockRuntime', service: S.BEDROCK_RUNTIME },
  { id: 'EcrApi', service: S.ECR, core: true },
  { id: 'EcrDkr', service: S.ECR_DOCKER, core: true },
  { id: 'Logs', service: S.CLOUDWATCH_LOGS },
  { id: 'Ssm', service: S.SSM },
  { id: 'SsmMessages', service: S.SSM_MESSAGES },
  { id: 'Ec2Messages', service: S.EC2_MESSAGES },
  { id: 'Sts', service: S.STS, core: true },
  { id: 'Eks', service: S.EKS, core: true },
  { id: 'EksAuth', service: S.EKS_AUTH },
  { id: 'Elb', service: S.ELASTIC_LOAD_BALANCING },
];

export class EksVpcStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: EksVpcStackProps) {
    super(scope, id, props);

    const azs = props.azs;
    const excluded = props.azsWithoutCoreEndpoints ?? [];
    const coreAzs = azs.filter((az) => !excluded.includes(az));

    const vpc = new ec2.Vpc(this, 'Vpc', {
      vpcName: 'eks-vpc',
      ipAddresses: ec2.IpAddresses.cidr(props.vpcCidr),
      availabilityZones: azs,
      enableDnsSupport: true,
      enableDnsHostnames: true,
      natGateways: azs.length,
      // CIDR은 선언 순서대로, 각 마스크 경계에 맞춰 배정된다.
      // 서울(10.200.0.0/16, AZ 4개)은 Public 10.200.0.0/24부터, Private 10.200.16.0/20부터, Isolated 10.200.80.0/23부터.
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
    endpointSg.addIngressRule(ec2.Peer.ipv4(props.vpcCidr), ec2.Port.tcp(443), 'HTTPS from the VPC CIDR');

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
        subnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS, availabilityZones: e.core ? coreAzs : azs },
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
