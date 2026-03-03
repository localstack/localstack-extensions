import {
  Box, Chip, Collapse, IconButton, InputAdornment, MenuItem,
  Paper, Select, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, TableSortLabel, TextField, Typography,
  useTheme,
} from '@mui/material';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import SearchIcon from '@mui/icons-material/Search';
import { ReactElement, useState, useMemo } from 'react';
import { Finding } from '../api';

const SEV_ORDER: Record<string, number> = {
  critical: 0, high: 1, medium: 2, low: 3, informational: 4,
};

function useSevColours() {
  const theme = useTheme();
  return {
    critical: theme.palette.error.main,
    high: theme.palette.warning.main,
    medium: theme.palette.warning.light,
    low: theme.palette.info.main,
    informational: theme.palette.text.secondary,
  } as Record<string, string>;
}

function SeverityChip({ severity }: { severity: string }) {
  const colours = useSevColours();
  const colour = colours[severity] ?? colours.informational;
  return (
    <Chip
      label={severity}
      size="small"
      sx={{
        borderColor: colour,
        color: colour,
        fontWeight: 600,
        fontSize: 11,
        textTransform: 'capitalize',
      }}
      variant="outlined"
    />
  );
}

function DetailRow({ finding }: { finding: Finding }) {
  const [open, setOpen] = useState(false);
  const theme = useTheme();

  return (
    <>
      <TableRow
        hover
        sx={{
          '&:hover': { bgcolor: theme.palette.action.hover },
          cursor: 'pointer',
        }}
        onClick={() => setOpen(!open)}
      >
        <TableCell padding="checkbox" sx={{ pl: 1 }}>
          <IconButton size="small" onClick={(e) => { e.stopPropagation(); setOpen(!open); }}>
            {open ? <KeyboardArrowUpIcon fontSize="small" /> : <KeyboardArrowDownIcon fontSize="small" />}
          </IconButton>
        </TableCell>
        <TableCell><SeverityChip severity={finding.severity} /></TableCell>
        <TableCell>
          <Chip
            label={finding.status}
            color={finding.status === 'PASS' ? 'success' : 'error'}
            size="small"
            sx={{ fontWeight: 600, fontSize: 11 }}
          />
        </TableCell>
        <TableCell sx={{ fontFamily: 'monospace', fontSize: 12, color: 'text.secondary' }}>
          {finding.check_id}
        </TableCell>
        <TableCell>
          <Chip
            label={finding.service || '—'}
            size="small"
            variant="outlined"
            sx={{ fontSize: 11 }}
          />
        </TableCell>
        <TableCell
          sx={{
            maxWidth: 240,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            fontSize: 12,
            fontFamily: 'monospace',
            color: 'text.secondary',
          }}
        >
          {finding.resource_uid || '—'}
        </TableCell>
        <TableCell sx={{ maxWidth: 300, fontSize: 13 }}>
          {finding.status_extended}
        </TableCell>
      </TableRow>

      <TableRow>
        <TableCell colSpan={7} sx={{ py: 0, border: 0 }}>
          <Collapse in={open} timeout="auto" unmountOnExit>
            <Box
              p={2}
              mx={1}
              mb={1}
              sx={{
                bgcolor: theme.palette.action.selected,
                borderRadius: 1,
                borderLeft: `3px solid ${theme.palette.primary.main}`,
              }}
            >
              <Typography variant="subtitle2" gutterBottom fontWeight={600}>
                {finding.check_title}
              </Typography>
              <Box
                component="pre"
                sx={{
                  fontSize: 11,
                  overflow: 'auto',
                  maxHeight: 260,
                  m: 0,
                  p: 1,
                  bgcolor: theme.palette.background.default,
                  borderRadius: 1,
                  color: 'text.secondary',
                }}
              >
                {JSON.stringify(finding.raw, null, 2)}
              </Box>
            </Box>
          </Collapse>
        </TableCell>
      </TableRow>
    </>
  );
}

interface Props {
  findings: Finding[];
}

export const FindingsTable = ({ findings }: Props): ReactElement => {
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [search, setSearch] = useState('');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const theme = useTheme();

  const filtered = useMemo(() => {
    let result = findings;
    if (statusFilter !== 'ALL') result = result.filter((f) => f.status === statusFilter);
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (f) =>
          f.check_id.toLowerCase().includes(q) ||
          f.status_extended.toLowerCase().includes(q) ||
          f.resource_uid.toLowerCase().includes(q) ||
          (f.service || '').toLowerCase().includes(q),
      );
    }
    return [...result].sort((a, b) => {
      const diff = (SEV_ORDER[a.severity] ?? 5) - (SEV_ORDER[b.severity] ?? 5);
      return sortDir === 'asc' ? diff : -diff;
    });
  }, [findings, statusFilter, search, sortDir]);

  return (
    <>
      <Box display="flex" gap={2} mb={2} alignItems="center" flexWrap="wrap">
        <Select
          size="small"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          sx={{ minWidth: 140 }}
        >
          <MenuItem value="ALL">All statuses</MenuItem>
          <MenuItem value="FAIL">FAIL only</MenuItem>
          <MenuItem value="PASS">PASS only</MenuItem>
        </Select>

        <TextField
          size="small"
          placeholder="Search findings…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" sx={{ color: 'text.secondary' }} />
              </InputAdornment>
            ),
          }}
          sx={{ minWidth: 260 }}
        />

        <Typography variant="body2" color="text.secondary" ml="auto">
          {filtered.length} / {findings.length} findings
        </Typography>
      </Box>

      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow sx={{ '& th': { fontWeight: 700, fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.05em' } }}>
              <TableCell width={40} />
              <TableCell>
                <TableSortLabel
                  active
                  direction={sortDir}
                  onClick={() => setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))}
                >
                  Severity
                </TableSortLabel>
              </TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Check ID</TableCell>
              <TableCell>Service</TableCell>
              <TableCell>Resource</TableCell>
              <TableCell>Message</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filtered.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 6 }}>
                  <Typography color="text.secondary" variant="body2">
                    No findings match the current filter.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              filtered.map((f, i) => <DetailRow key={i} finding={f} />)
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </>
  );
};
