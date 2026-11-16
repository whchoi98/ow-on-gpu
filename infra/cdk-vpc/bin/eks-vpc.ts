#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { EksVpcStack } from '../lib/eks-vpc-stack';

const account = process.env.CDK_DEFAULT_ACCOUNT;
if (!account) {
  throw new Error('CDK_DEFAULT_ACCOUNT가 비어 있습니다. AWS 자격 증명을 확인하세요.');
}

const app = new cdk.App();
new EksVpcStack(app, 'EksVpcStack', {
  // 가용 영역을 직접 지정하려면 환경이 확정되어야 한다. 계정 ID는 소스에 남기지 않고 CLI 자격 증명에서 받는다.
  env: { account, region: 'ap-northeast-2' },
  description: 'eks-vpc: 10.200.0.0/16, 4 AZs, public/private/isolated subnets, NAT per AZ, VPC endpoints',
});
