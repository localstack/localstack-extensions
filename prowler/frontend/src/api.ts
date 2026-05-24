// Derive the base path from the page URL so API calls work when the app is
// served at a sub-path (e.g. /_extension/prowler/) as well as on a local dev server.
const BASE = window.location.pathname.replace(/\/$/, '');

export interface ScanSummary {
  critical: number;
  high: number;
  medium: number;
  low: number;
  informational: number;
  pass: number;
  fail: number;
  total: number;
}

export interface ScanStatus {
  scan_id: string;
  status: 'idle' | 'running' | 'completed' | 'failed';
  started_at: string | null;
  finished_at: string | null;
  services: string[];
  severity: string[];
  summary: ScanSummary;
  error: string | null;
}

export interface Finding {
  check_id: string;
  check_title: string;
  service: string;
  severity: string;
  status: string;
  status_extended: string;
  resource_uid: string;
  region: string;
  raw: Record<string, unknown>;
}

export interface ScanResult extends ScanStatus {
  findings: Finding[];
}

export async function getStatus(): Promise<ScanStatus> {
  const res = await fetch(`${BASE}/api/status`);
  return res.json();
}

export async function startScan(services: string[], severity: string[]): Promise<{ scan_id: string; status: string }> {
  const res = await fetch(`${BASE}/api/scans`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ services, severity }),
  });
  if (res.status === 409) throw new Error('A scan is already in progress');
  return res.json();
}

// Maps LocalStack service names → Prowler CLI service names.
// Only entries where Prowler actually has checks are included.
const LS_TO_PROWLER: Record<string, string> = {
  accessanalyzer:    'accessanalyzer',
  acm:               'acm',
  cloudformation:    'cloudformation',
  cloudfront:        'cloudfront',
  cloudtrail:        'cloudtrail',
  cloudwatch:        'cloudwatch',
  'cognito-idp':     'cognito',
  config:            'config',
  dynamodb:          'dynamodb',
  ec2:               'ec2',
  ecr:               'ecr',
  ecs:               'ecs',
  eks:               'eks',
  elb:               'elb',
  elbv2:             'elbv2',
  emr:               'emr',
  events:            'eventbridge',
  glacier:           'glacier',
  glue:              'glue',
  guardduty:         'guardduty',
  iam:               'iam',
  kms:               'kms',
  lambda:            'lambda',
  opensearch:        'opensearch',
  organizations:     'organizations',
  rds:               'rds',
  redshift:          'redshift',
  route53:           'route53',
  s3:                's3',
  sagemaker:         'sagemaker',
  secretsmanager:    'secretsmanager',
  ses:               'ses',
  shield:            'shield',
  sns:               'sns',
  sqs:               'sqs',
  ssm:               'ssm',
  stepfunctions:     'stepfunctions',
  sts:               'sts',
  transfer:          'transfer',
  wafv2:             'waf',
};

/** Fetch services available in LocalStack and map them to Prowler service names. */
export async function getLocalStackServices(): Promise<string[]> {
  const res = await fetch(`${window.location.origin}/_localstack/health`);
  if (!res.ok) throw new Error('Failed to fetch LocalStack health');
  const data = await res.json();
  const available = Object.keys(data.services ?? {});
  // Map and deduplicate Prowler names
  const prowlerNames = new Set<string>();
  for (const svc of available) {
    const prowler = LS_TO_PROWLER[svc];
    if (prowler) prowlerNames.add(prowler);
  }
  return [...prowlerNames].sort();
}

export async function getLatestScan(): Promise<ScanResult> {
  const res = await fetch(`${BASE}/api/scans/latest`);
  if (!res.ok) throw new Error('No scan results yet');
  return res.json();
}
