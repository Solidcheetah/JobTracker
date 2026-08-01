import { Box, Button, Chip, FormControl, InputLabel, MenuItem, OutlinedInput, Select, TextField, Typography } from '@mui/material';
import FilterListIcon from '@mui/icons-material/FilterList';
import { palette } from '../theme';
import type { ApplicationFilters as Filters } from '../api/applications';
import type { ApplicationStatus } from '../types';

interface ApplicationFiltersProps {
  filters: Filters;
  onChange: (filters: Filters) => void;
  onReset: () => void;
}

const STATUS_OPTIONS: { value: ApplicationStatus; label: string }[] = [
  { value: 'wishlist', label: 'Wishlist' },
  { value: 'applied', label: 'Applied' },
  { value: 'screen', label: 'Screen' },
  { value: 'onsite', label: 'Onsite' },
  { value: 'offer', label: 'Offer' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'withdrawn', label: 'Withdrawn' },
];

export function ApplicationFilters({ filters, onChange, onReset }: ApplicationFiltersProps) {
  const hasFilters =
    (filters.status && filters.status.length > 0) ||
    !!filters.search ||
    !!filters.applied_from ||
    !!filters.applied_to;

  const handleStatusChange = (value: ApplicationStatus[]) => {
    onChange({ ...filters, status: value.length > 0 ? value : undefined });
  };

  const handleSearchChange = (value: string) => {
    onChange({ ...filters, search: value || undefined });
  };

  const handleDateChange = (key: 'applied_from' | 'applied_to', value: string) => {
    onChange({ ...filters, [key]: value || undefined });
  };

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
        p: 2.5,
        mb: 3,
        border: `1px solid ${palette.border}`,
        borderRadius: '10px',
        background: palette.surface,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
        <FilterListIcon sx={{ color: palette.muted, fontSize: 18 }} />
        <Typography variant="subtitle1" sx={{ fontWeight: 600, fontSize: '0.9rem', color: palette.ink }}>
          Filters
        </Typography>
      </Box>

      <Box
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 2,
          alignItems: 'flex-start',
        }}
      >
        <FormControl size="small" sx={{ minWidth: 220, flex: '1 1 200px' }}>
          <InputLabel id="status-filter-label">Status</InputLabel>
          <Select
            labelId="status-filter-label"
            id="status-filter"
            multiple
            value={filters.status ?? []}
            onChange={(e) => handleStatusChange(e.target.value as ApplicationStatus[])}
            input={<OutlinedInput id="status-filter" label="Status" />}
            renderValue={(selected) => (
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                {(selected as ApplicationStatus[]).map((value) => (
                  <Chip
                    key={value}
                    label={STATUS_OPTIONS.find((s) => s.value === value)?.label}
                    size="small"
                    sx={{
                      fontSize: '0.7rem',
                      height: 22,
                      bgcolor: palette.statusGrayBg,
                      color: palette.statusGray,
                    }}
                  />
                ))}
              </Box>
            )}
          >
            {STATUS_OPTIONS.map((status) => (
              <MenuItem key={status.value} value={status.value}>
                {status.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <TextField
          size="small"
          label="Search company or role"
          value={filters.search ?? ''}
          onChange={(e) => handleSearchChange(e.target.value)}
          sx={{ minWidth: 240, flex: '2 1 240px' }}
        />

        <TextField
          size="small"
          label="Applied from"
          type="date"
          value={filters.applied_from ?? ''}
          onChange={(e) => handleDateChange('applied_from', e.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
          sx={{ minWidth: 150, flex: '1 1 150px' }}
        />

        <TextField
          size="small"
          label="Applied to"
          type="date"
          value={filters.applied_to ?? ''}
          onChange={(e) => handleDateChange('applied_to', e.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
          sx={{ minWidth: 150, flex: '1 1 150px' }}
        />

        <Button
          variant="outlined"
          onClick={onReset}
          disabled={!hasFilters}
          sx={{
            minWidth: 100,
            color: palette.muted,
            borderColor: palette.border2,
            textTransform: 'none',
            '&:hover': {
              borderColor: palette.muted,
              bgcolor: 'transparent',
            },
          }}
        >
          Reset
        </Button>
      </Box>
    </Box>
  );
}
