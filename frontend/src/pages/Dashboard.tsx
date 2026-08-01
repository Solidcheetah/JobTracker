import { useEffect, useMemo, useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Card,
  CircularProgress,
  Grid,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import BusinessIcon from '@mui/icons-material/Business';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import ForumOutlinedIcon from '@mui/icons-material/ForumOutlined';
import { getApplicationStats, getRecentApplications } from '../api/applications';
import { ApplicationTable } from '../components/ApplicationTable';
import { StatCard } from '../components/StatCard';
import { StatusBarChart } from '../components/StatusBarChart';
import { UpcomingReminders } from '../components/UpcomingReminders';
import { palette } from '../theme';
import type { Application, ApplicationStats } from '../types';

function daysSince(dateString: string): number {
  const then = new Date(dateString);
  const now = new Date();
  return Math.floor((now.getTime() - then.getTime()) / (1000 * 60 * 60 * 24));
}

function formatLastUpdated(days: number): string {
  if (days <= 0) return 'today';
  if (days === 1) return 'yesterday';
  return `${days} days ago`;
}

export function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<ApplicationStats | null>(null);
  const [recentApplications, setRecentApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [statsResponse, recentResponse] = await Promise.all([
        getApplicationStats(),
        getRecentApplications(),
      ]);
      setStats(statsResponse.data);
      setRecentApplications(recentResponse.data);
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
      setError('Failed to load dashboard data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const activePipeline = useMemo(() => {
    if (!stats) return 0;
    return (stats.status_counts.applied ?? 0) + (stats.status_counts.screen ?? 0);
  }, [stats]);

  // Counted from `stats`, which covers every application, rather than from
  // `recentApplications` — that list is capped at five rows.
  const interviews = useMemo(() => {
    if (!stats) return 0;
    const { screen = 0, onsite = 0, offer = 0 } = stats.status_counts;
    return screen + onsite + offer;
  }, [stats]);

  // Wishlist rows are excluded: nothing has been sent for them yet, so counting
  // them would drag the rate down for applications that were never submitted.
  const interviewRateText = useMemo(() => {
    if (!stats) return 'No applications yet';
    const submitted = stats.total - (stats.status_counts.wishlist ?? 0);
    if (submitted === 0) return 'Nothing submitted yet';
    return `${Math.round((interviews / submitted) * 100)}% of ${submitted} submitted`;
  }, [stats, interviews]);

  const lastUpdatedText = useMemo(() => {
    if (!recentApplications.length) return 'no updates yet';
    const mostRecent = recentApplications.reduce((latest, app) =>
      new Date(app.created_at) > new Date(latest.created_at) ? app : latest
    );
    return `last updated ${formatLastUpdated(daysSince(mostRecent.created_at))}`;
  }, [recentApplications]);

  if (loading && recentApplications.length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  const today = new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });

  return (
    <Box>
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Page header */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: { xs: 'column', sm: 'row' },
          alignItems: { xs: 'flex-start', sm: 'flex-end' },
          justifyContent: 'space-between',
          gap: 2,
          mb: 3.25,
        }}
      >
        <Box>
          <Typography
            variant="overline"
            sx={{ color: palette.muted2, fontSize: '0.68rem' }}
          >
            {today}
          </Typography>
          <Typography
            variant="h1"
            sx={{
              fontSize: '1.7rem',
              fontWeight: 600,
              color: palette.ink,
              mt: 0.5,
              mb: 0.625,
            }}
          >
            Overview
          </Typography>
          <Typography variant="body2" sx={{ color: palette.muted, fontSize: '0.85rem' }}>
            <Box component="span" sx={{ color: palette.ink, fontWeight: 600 }}>
              {stats?.total ?? 0}
            </Box>{' '}
            applications
            <Box component="span" sx={{ color: palette.border2, mx: 0.875 }}>
              ·
            </Box>
            <Box component="span" sx={{ color: palette.ink, fontWeight: 600 }}>
              {activePipeline}
            </Box>{' '}
            active
            <Box component="span" sx={{ color: palette.border2, mx: 0.875 }}>
              ·
            </Box>
            {lastUpdatedText}
          </Typography>
        </Box>

        <Button
          variant="contained"
          size="medium"
          startIcon={<AddIcon />}
          onClick={() => navigate('/applications/new')}
          sx={{
            bgcolor: palette.emerald,
            color: '#FFFFFF',
            '&:hover': { bgcolor: palette.emeraldDark },
            flexShrink: 0,
            textTransform: 'none',
          }}
        >
          Add application
        </Button>
      </Box>

      {/* Stat cards */}
      <Grid container spacing={2} sx={{ mb: 2.75 }}>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <StatCard
            title="Total applications"
            value={stats?.total ?? 0}
            context="Across all stages"
            icon={<BusinessIcon sx={{ width: 22, height: 22, color: palette.muted2 }} />}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <StatCard
            title="Active pipeline"
            value={activePipeline}
            context="Applied & screening"
            icon={<TrendingUpIcon sx={{ width: 22, height: 22, color: palette.muted2 }} />}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 12, md: 4 }}>
          <StatCard
            title="Interview stage"
            value={interviews}
            context={interviewRateText}
            icon={<ForumOutlinedIcon sx={{ width: 22, height: 22, color: palette.muted2 }} />}
          />
        </Grid>
      </Grid>

      {/* Chart + Reminders */}
      <Grid container spacing={2} sx={{ mb: 2.75 }}>
        <Grid size={{ xs: 12, lg: 8 }}>
          {stats && <StatusBarChart data={stats.status_counts} />}
        </Grid>
        <Grid size={{ xs: 12, lg: 4 }}>
          <UpcomingReminders />
        </Grid>
      </Grid>

      {/* Recent applications */}
      <Card
        elevation={0}
        sx={{
          p: 3,
          border: `1px solid ${palette.border}`,
          borderRadius: '10px',
          background: palette.surface,
        }}
      >
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: { xs: 'flex-start', sm: 'center' },
            flexDirection: { xs: 'column', sm: 'row' },
            gap: 2,
            mb: 2,
          }}
        >
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '0.9375rem' }}>
              Recent applications
            </Typography>
            <Typography variant="body2" sx={{ color: palette.muted, fontSize: '0.78rem' }}>
              Your latest applications, most recent first.
            </Typography>
          </Box>
          <Button
            variant="text"
            endIcon={<ArrowForwardIcon />}
            component={RouterLink}
            to="/applications"
            sx={{
              color: palette.emerald,
              textTransform: 'none',
              fontWeight: 500,
              flexShrink: 0,
            }}
          >
            View all
          </Button>
        </Box>

        <ApplicationTable applications={recentApplications} onRefresh={fetchData} />
      </Card>
    </Box>
  );
}
