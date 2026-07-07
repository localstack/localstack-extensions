import { Theme } from '@mui/material/styles';

export const SEVERITY_ORDER: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
  informational: 4,
};

export const SUMMARY_SEVERITIES = ['critical', 'high', 'medium', 'low'] as const;

export function getSeverityColor(theme: Theme, severity: string): string {
  const palette: Record<string, string> = {
    critical: theme.palette.error.main,
    high: theme.palette.warning.main,
    medium: theme.palette.warning.light,
    low: theme.palette.info.main,
    informational: theme.palette.text.secondary,
  };
  return palette[severity] ?? theme.palette.text.secondary;
}
