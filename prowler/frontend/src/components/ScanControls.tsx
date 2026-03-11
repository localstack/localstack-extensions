import {
  Box, Button, Chip, CircularProgress, FormControl,
  InputLabel, MenuItem, OutlinedInput, Select, SelectChangeEvent,
  Typography,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import { ReactElement, useEffect, useState } from 'react';
import { getLocalStackServices } from '../api';

const SEVERITIES = ['critical', 'high', 'medium', 'low', 'informational'];

interface Props {
  isRunning: boolean;
  onRun: (services: string[], severity: string[]) => void;
  error?: string | null;
}

export const ScanControls = ({ isRunning, onRun, error }: Props): ReactElement => {
  const [services, setServices] = useState<string[]>([]);
  const [severity, setSeverity] = useState<string[]>([]);
  const [availableServices, setAvailableServices] = useState<string[]>([]);

  useEffect(() => {
    getLocalStackServices()
      .then(setAvailableServices)
      .catch(() => {
        // fallback: leave list empty so the user can still type or select nothing (all services)
      });
  }, []);

  const handleServices = (e: SelectChangeEvent<string[]>) =>
    setServices(typeof e.target.value === 'string' ? e.target.value.split(',') : e.target.value);

  const handleSeverity = (e: SelectChangeEvent<string[]>) =>
    setSeverity(typeof e.target.value === 'string' ? e.target.value.split(',') : e.target.value);

  return (
    <Box mb={3}>
      <Box display="flex" gap={2} alignItems="center" flexWrap="wrap">
        <FormControl size="small" sx={{ minWidth: 220 }}>
          <InputLabel>Services (all if empty)</InputLabel>
          <Select
            multiple
            value={services}
            onChange={handleServices}
            input={<OutlinedInput label="Services (all if empty)" />}
            renderValue={(selected) => (
              <Box display="flex" gap={0.5} flexWrap="wrap">
                {(selected as string[]).map((v) => (
                  <Chip key={v} label={v} size="small" />
                ))}
              </Box>
            )}
          >
            {availableServices.length === 0 ? (
              <MenuItem disabled>
                <Typography variant="body2" color="text.secondary">Loading…</Typography>
              </MenuItem>
            ) : (
              availableServices.map((s) => (
                <MenuItem key={s} value={s}>{s}</MenuItem>
              ))
            )}
          </Select>
        </FormControl>

        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel>Severity (all if empty)</InputLabel>
          <Select
            multiple
            value={severity}
            onChange={handleSeverity}
            input={<OutlinedInput label="Severity (all if empty)" />}
            renderValue={(selected) => (
              <Box display="flex" gap={0.5} flexWrap="wrap">
                {(selected as string[]).map((v) => (
                  <Chip key={v} label={v} size="small" />
                ))}
              </Box>
            )}
          >
            {SEVERITIES.map((s) => (
              <MenuItem key={s} value={s}>{s}</MenuItem>
            ))}
          </Select>
        </FormControl>

        <Button
          variant="contained"
          color="primary"
          onClick={() => onRun(services, severity)}
          disabled={isRunning}
          startIcon={
            isRunning
              ? <CircularProgress size={16} color="inherit" />
              : <PlayArrowIcon />
          }
          sx={{ height: 40, px: 3, fontWeight: 600 }}
        >
          {isRunning ? 'Scanning…' : 'Run Scan'}
        </Button>

        {error && (
          <Typography color="error" variant="body2" sx={{ ml: 1 }}>
            {error}
          </Typography>
        )}
      </Box>
    </Box>
  );
};
