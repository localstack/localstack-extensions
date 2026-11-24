import {
  Alert, Box, Card, CardContent, CardHeader, CircularProgress,
  Divider, IconButton, LinearProgress, Link, Tooltip, Typography, useTheme,
} from '@mui/material';
import GitHubIcon from '@mui/icons-material/GitHub';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import SecurityIcon from '@mui/icons-material/Security';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import { ReactElement, useCallback, useEffect, useRef, useState } from 'react';
import { getLatestScan, getStatus, startScan, ScanResult, ScanStatus } from '../api';
import { ScanControls } from './ScanControls';
import { SummaryBar } from './SummaryBar';
import { FindingsTable } from './FindingsTable';

const POLL_INTERVAL_MS = 3000;

export const Dashboard = (): ReactElement => {
  const [status, setStatus] = useState<ScanStatus | null>(null);
  const [result, setResult] = useState<ScanResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const theme = useTheme();

  const fetchStatus = useCallback(async () => {
    try {
      const s = await getStatus();
      setStatus(s);
      if (s.status === 'completed' || s.status === 'failed') {
        if (pollRef.current) clearInterval(pollRef.current);
        if (s.status === 'completed') {
          const latest = await getLatestScan();
          setResult(latest);
        }
      }
    } catch (e) {
      // ignore transient errors during polling
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [fetchStatus]);

  const handleRun = async (services: string[], severity: string[]) => {
    setError(null);
    setResult(null);
    try {
      await startScan(services, severity);
      await fetchStatus();
      pollRef.current = setInterval(fetchStatus, POLL_INTERVAL_MS);
    } catch (e: any) {
      setError(e.message || 'Failed to start scan');
    }
  };

  const isRunning = status?.status === 'running';
  const elapsed = status?.started_at && isRunning
    ? Math.round((Date.now() - new Date(status.started_at).getTime()) / 1000)
    : null;

  return (
    <Card elevation={0} variant="outlined">
      <CardHeader
        avatar={
          <Box
            component="img"
            src="https://avatars.githubusercontent.com/u/97106991?s=200&v=4"
            alt="Prowler"
            sx={{ width: 36, height: 36, borderRadius: '50%' }}
          />
        }
        title={
          <Typography variant="h6" fontWeight={700}>
            Prowler Security Scanner
          </Typography>
        }
        subheader="Run Prowler security checks against your LocalStack environment"
        action={
          <Box display="flex" alignItems="center" gap={0.5} pr={1}>
            <Tooltip title="Prowler on GitHub">
              <IconButton
                size="small"
                component={Link}
                href="https://github.com/prowler-cloud/prowler"
                target="_blank"
                rel="noopener noreferrer"
              >
                <GitHubIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="prowler.com">
              <IconButton
                size="small"
                component={Link}
                href="https://www.prowler.com/"
                target="_blank"
                rel="noopener noreferrer"
              >
                <OpenInNewIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        }
        sx={{ pb: 1 }}
      />
      <Divider />

      {isRunning && <LinearProgress />}

      <CardContent>
        <ScanControls isRunning={isRunning} onRun={handleRun} error={error} />

        {isRunning && (
          <Box
            display="flex"
            alignItems="center"
            gap={1.5}
            mb={3}
            p={1.5}
            sx={{
              borderRadius: 1,
              bgcolor: theme.palette.action.hover,
              border: `1px solid ${theme.palette.divider}`,
            }}
          >
            <CircularProgress size={18} thickness={5} />
            <Typography variant="body2" color="text.secondary">
              Scan in progress
              {elapsed !== null && (
                <Box component="span" sx={{ ml: 1, fontFamily: 'monospace', color: 'text.primary' }}>
                  {elapsed}s
                </Box>
              )}
            </Typography>
          </Box>
        )}

        {status?.status === 'failed' && (
          <Alert severity="error" sx={{ mb: 2 }}>
            Scan failed: {status.error || 'Unknown error'}
          </Alert>
        )}

        {result && (
          <>
            <SummaryBar summary={result.summary} />
            <Divider sx={{ mb: 2 }} />
            <FindingsTable findings={result.findings} />
          </>
        )}

        {!result && !isRunning && status?.status !== 'failed' && (
          <Box py={8} textAlign="center">
            <SecurityIcon
              sx={{ fontSize: 56, color: 'text.disabled', mb: 1.5, display: 'block', mx: 'auto' }}
            />
            <Typography color="text.secondary" variant="body2">
              No scan results yet. Select services and click{' '}
              <Box component="span" fontWeight={700} color="text.primary">Run Scan</Box>{' '}
              to get started.
            </Typography>
          </Box>
        )}

        {result && result.summary.fail === 0 && (
          <Box display="flex" alignItems="center" gap={1} mt={2}>
            <CheckCircleOutlineIcon color="success" fontSize="small" />
            <Typography variant="body2" color="success.main">
              All checks passed — no failures detected.
            </Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};
