#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { EksVpcStack } from '../lib/eks-vpc-stack';

const account = process.env.CDK_DEFAULT_ACCOUNT;
if (!account) {
  throw new Error('CDK_DEFAULT_ACCOUNT가 비어 있습니다. AWS 자격 증명을 확인하세요.');
}

// 가용 영역을 직접 지정하려면 환경이 확정되어야 한다. 계정 ID는 소스에 남기지 않고 CLI 자격 증명에서 받는다.
// 스택을 이름으로 골라 다룬다: cdk diff EksVpcStack, cdk diff EksVpcStackTokyo
const app = new cdk.App();

// 서울
new EksVpcStack(app, 'EksVpcStack', {
  env: { account, region: 'ap-northeast-2' },
  description: 'eks-vpc: 10.200.0.0/16, 4 AZs, public/private/isolated subnets, NAT per AZ, VPC endpoints',
  vpcCidr: '10.200.0.0/16',
  azs: ['ap-northeast-2a', 'ap-northeast-2b', 'ap-northeast-2c', 'ap-northeast-2d'],
  // ecr.api, ecr.dkr, sts, eks 엔드포인트 서비스는 ap-northeast-2d를 지원하지 않는다
  // (aws ec2 describe-vpc-endpoint-services, 2026-11-14 확인).
  azsWithoutCoreEndpoints: ['ap-northeast-2d'],
});

// 도쿄. 이 계정이 쓸 수 있는 AZ는 셋이고, 엔드포인트 서비스 11종이 세 AZ를 모두 지원한다(2026-11-19 확인).
// CIDR은 서울과 같은 값으로 정했다(2026-11-19). 두 VPC를 피어링이나 Transit Gateway로 이으려면 한쪽을 다시 만들어야 한다.
new EksVpcStack(app, 'EksVpcStackTokyo', {
  env: { account, region: 'ap-northeast-1' },
  description: 'eks-vpc: 10.200.0.0/16, 3 AZs, public/private/isolated subnets, NAT per AZ, VPC endpoints',
  vpcCidr: '10.200.0.0/16',
  azs: ['ap-northeast-1a', 'ap-northeast-1c', 'ap-northeast-1d'],
});
