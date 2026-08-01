import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link as RouterLink, useSearchParams } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Pagination,
  Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import AddIcon from '@mui/icons-material/Add';
import { getApplications, type ApplicationFilters } from '../api/applications';
import { ApplicationFilters as ApplicationFiltersPanel } from '../components/ApplicationFilters';
import { ApplicationTable } from '../components/ApplicationTable';
import { palette } from '../theme';
import type { Application, ApplicationStatus, PaginatedApplications } from '../types';

const STATUS_VALUES: ApplicationStatus[] = [
  'wishlist',
  'applied',
  'screen',
  'onsite',
  'offer',
  'rejected',
  'withdrawn',
];

function parseFiltersFromSearchParams(searchParams: URLSearchParams): ApplicationFilters {
  const filters: ApplicationFilters = {};

  const status = searchParams.getAll('status');
  if (status.length > 0) {
    const validStatuses = status.filter((s): s is ApplicationStatus =>
      STATUS_VALUES.includes(s as ApplicationStatus)
    );
    if (validStatuses.length > 0) filters.status = validStatuses;
  }

  const search = searchParams.get('search');
  if (search) filters.search = search;

  const appliedFrom = searchParams.get('applied_from');
  if (appliedFrom) filters.applied_from = appliedFrom;

  const appliedTo = searchParams.get('applied_to');
  if (appliedTo) filters.applied_to = appliedTo;

  return filters;
}

function buildSearchParams(filters: ApplicationFilters): URLSearchParams {
  const params = new URLSearchParams();

  filters.status?.forEach((s) => params.append('status', s));
  if (filters.search) params.set('search', filters.search);
  if (filters.applied_from) params.set('applied_from', filters.applied_from);
  if (filters.applied_to) params.set('applied_to', filters.applied_to);

  return params;
}

function areFiltersEmpty(filters: ApplicationFilters): boolean {
  return (
    !filters.status?.length &&
    !filters.search &&
    !filters.applied_from &&
    !filters.applied_to
  );
}

export function ApplicationsList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [paginated, setPaginated] = useState<PaginatedApplications | null>(null);
  const [page, setPage] = useState(() => {
    const pageParam = searchParams.get('page');
    const parsed = pageParam ? parseInt(pageParam, 10) : 1;
    return Number.isNaN(parsed) || parsed < 1 ? 1 : parsed;
  });
  const [pageSize] = useState(5);
  const [filters, setFilters] = useState<ApplicationFilters>(() =>
    parseFiltersFromSearchParams(searchParams)
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchApplications = useCallback(
    async (pageToFetch: number, filtersToFetch: ApplicationFilters) => {
      setLoading(true);
      setError(null);
      try {
        const response = await getApplications(pageToFetch, pageSize, filtersToFetch);
        setPaginated(response.data);
      } catch (err) {
        console.error('Failed to load applications:', err);
        setError('Failed to load applications.');
      } finally {
        setLoading(false);
      }
    },
    [pageSize]
  );

  useEffect(() => {
    fetchApplications(page, filters);
  }, [page, filters, pageSize, fetchApplications]);

  useEffect(() => {
    const params = buildSearchParams(filters);
    if (page > 1) params.set('page', String(page));
    setSearchParams(params, { replace: true });
  }, [filters, page, setSearchParams]);

  const handleFiltersChange = (newFilters: ApplicationFilters) => {
    setFilters(newFilters);
    setPage(1);
  };

  const handleReset = () => {
    setFilters({});
    setPage(1);
  };

  const handleRefresh = async () => {
    await fetchApplications(page, filters);
  };

  const handlePageChange = (_: React.ChangeEvent<unknown>, value: number) => {
    setPage(value);
  };

  const isFiltered = useMemo(() => !areFiltersEmpty(filters), [filters]);

  if (loading && !paginated) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Button
        component={RouterLink}
        to="/dashboard"
        startIcon={<ArrowBackIcon />}
        sx={{ mb: 2, color: palette.muted, textTransform: 'none' }}
      >
        Back to Dashboard
      </Button>

      <Card elevation={0} sx={{ border: `1px solid ${palette.border}`, borderRadius: '10px' }}>
        <CardContent>
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: { xs: 'flex-start', sm: 'center' },
              flexDirection: { xs: 'column', sm: 'row' },
              gap: 2,
              mb: 3,
            }}
          >
            <Box>
              <Typography
                variant="h4"
                component="h1"
                sx={{ fontWeight: 600, fontSize: '1.6rem', color: palette.ink }}
              >
                All Applications
              </Typography>
              <Typography variant="body2" sx={{ mt: 0.5, color: palette.muted }}>
                Browse and manage every application in your tracker.
              </Typography>
            </Box>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              component={RouterLink}
              to="/applications/new"
              sx={{
                bgcolor: palette.emerald,
                color: '#fff',
                textTransform: 'none',
                '&:hover': { bgcolor: palette.emeraldDark },
              }}
            >
              Add Application
            </Button>
          </Box>

          {error && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {error}
            </Alert>
          )}

          <ApplicationFiltersPanel
            filters={filters}
            onChange={handleFiltersChange}
            onReset={handleReset}
          />

          {isFiltered && paginated && (
            <Typography variant="body2" sx={{ mb: 2, color: palette.muted, fontSize: '0.8rem' }}>
              Showing {paginated.items.length} of {paginated.total} result
              {paginated.total === 1 ? '' : 's'}
            </Typography>
          )}

          <ApplicationTable
            applications={(paginated?.items as Application[]) ?? []}
            onRefresh={handleRefresh}
          />

          {paginated && paginated.total_pages > 1 && (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
              <Pagination
                count={paginated.total_pages}
                page={page}
                onChange={handlePageChange}
                sx={{
                  '& .MuiPaginationItem-root.Mui-selected': {
                    bgcolor: palette.emerald,
                    color: '#fff',
                  },
                }}
              />
            </Box>
          )}
        </CardContent>
      </Card>
    </Box>
  );
}
