import { Box, Chip, Divider, Typography, useTheme } from '@mui/material';
import { ReactElement } from 'react';
import { ScanSummary } from '../api';
import { getSeverityColor, SUMMARY_SEVERITIES } from '../severity';

interface Props {
  summary: ScanSummary;
}

export const SummaryBar = ({ summary }: Props): ReactElement => {
  const theme = useTheme();

  return (
    <Box
      display="flex"
      alignItems="center"
      gap={3}
      flexWrap="wrap"
      px={2}
      py={1.5}
      mb={2}
      sx={{
        borderRadius: 1,
        border: `1px solid ${theme.palette.divider}`,
        bgcolor: theme.palette.action.hover,
      }}
    >
      {SUMMARY_SEVERITIES.map((sev) => (
        <Box key={sev} textAlign="center" minWidth={48}>
          <Typography
            variant="h5"
            fontWeight={700}
            lineHeight={1}
            sx={{ color: getSeverityColor(theme, sev) }}
          >
            {summary[sev]}
          </Typography>
          <Typography
            variant="caption"
            sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', color: 'text.secondary' }}
          >
            {sev}
          </Typography>
        </Box>
      ))}

      <Divider orientation="vertical" flexItem sx={{ mx: 1 }} />

      <Box display="flex" gap={1} alignItems="center" ml="auto" flexWrap="wrap">
        <Chip
          label={`${summary.pass} PASS`}
          color="success"
          size="small"
          variant="outlined"
          sx={{ fontWeight: 600 }}
        />
        <Chip
          label={`${summary.fail} FAIL`}
          color="error"
          size="small"
          variant="outlined"
          sx={{ fontWeight: 600 }}
        />
        <Chip
          label={`${summary.total} total`}
          size="small"
          variant="outlined"
          sx={{ fontWeight: 600 }}
        />
      </Box>
    </Box>
  );
};
