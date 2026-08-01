import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link as RouterLink } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Link,
  Step,
  Stepper,
  StepLabel,
  Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { api } from '../api/axios';
import { deleteApplication, getApplicationStatusHistory } from '../api/applications';
import { readErrorMessage } from '../api/errors';
import type { Application, ApplicationStatusHistory } from '../types';

const statusColors: Record<string, 'default' | 'primary' | 'success' | 'error' | 'warning' | 'info'> = {
  wishlist: 'default',
  applied: 'info',
  screen: 'primary',
  onsite: 'warning',
  offer: 'success',
  rejected: 'error',
  withdrawn: 'default',
};

export function ApplicationView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [application, setApplication] = useState<Application | null>(null);
  const [history, setHistory] = useState<ApplicationStatusHistory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      if (!id) {
        setError('Application ID is required.');
        setLoading(false);
        return;
      }

      try {
        const [applicationResponse, historyResponse] = await Promise.all([
          api.get<Application>('/application/', { params: { id } }),
          getApplicationStatusHistory(id),
        ]);
        setApplication(applicationResponse.data);
        setHistory(historyResponse.data);
      } catch (err: any) {
        setError(
          err.response?.status === 404
            ? 'Application not found.'
            : 'Failed to load application details.'
        );
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [id]);

  const handleDelete = async () => {
    if (!application) return;
    if (!window.confirm('Are you sure you want to delete this application? This action cannot be undone.')) {
      return;
    }

    setIsDeleting(true);
    setDeleteError(null);

    try {
      await deleteApplication(application.id);
      navigate('/dashboard');
    } catch (err: any) {
      setDeleteError(readErrorMessage(err, 'Failed to delete application.'));
      setIsDeleting(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error || !application) {
    return (
      <Box>
        <Button
          component={RouterLink}
          to="/dashboard"
          startIcon={<ArrowBackIcon />}
          sx={{ mb: 2 }}
        >
          Back to Dashboard
        </Button>
        <Alert severity="error">{error || 'Application not found.'}</Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Button
        component={RouterLink}
        to="/dashboard"
        startIcon={<ArrowBackIcon />}
        sx={{ mb: 2 }}
      >
        Back to Dashboard
      </Button>

      {deleteError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {deleteError}
        </Alert>
      )}

      <Card>
        <CardContent>
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              flexWrap: 'wrap',
              gap: 2,
              mb: 2,
            }}
          >
            <Box>
              <Typography variant="h4" component="h1" gutterBottom>
                {application.role}
              </Typography>
              <Typography variant="h6" color="text.secondary">
                {application.company}
              </Typography>
            </Box>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                variant="outlined"
                color="error"
                startIcon={<DeleteIcon />}
                onClick={handleDelete}
                disabled={isDeleting}
              >
                {isDeleting ? 'Deleting...' : 'Delete'}
              </Button>
              <Button
                variant="contained"
                startIcon={<EditIcon />}
                component={RouterLink}
                to={`/applications/${application.id}/edit`}
              >
                Edit
              </Button>
            </Box>
          </Box>

          <Divider sx={{ my: 2 }} />

          <Box sx={{ display: 'grid', gap: 2 }}>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Status
              </Typography>
              <Box sx={{ mt: 0.5 }}>
                <Chip
                  label={application.status}
                  color={statusColors[application.status] || 'default'}
                />
              </Box>
            </Box>

            <Box>
              <Typography variant="caption" color="text.secondary">
                Applied At
              </Typography>
              <Typography variant="body1">
                {new Date(application.applied_at).toLocaleDateString()}
              </Typography>
            </Box>

            {application.source_url && (
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Source URL
                </Typography>
                <Box>
                  <Link
                    href={application.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}
                  >
                    {application.source_url}
                    <OpenInNewIcon fontSize="small" />
                  </Link>
                </Box>
              </Box>
            )}

            <Box>
              <Typography variant="caption" color="text.secondary">
                Note
              </Typography>
              <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap', mt: 0.5 }}>
                {application.note || 'No note provided.'}
              </Typography>
            </Box>
          </Box>

          {history.length > 0 && (
            <>
              <Divider sx={{ my: 3 }} />
              <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                Status History
              </Typography>
              <Stepper orientation="vertical" sx={{ mt: 2 }}>
                {history.map((record) => (
                  <Step key={record.id} active completed>
                    <StepLabel>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                        <Chip
                          label={record.status}
                          color={statusColors[record.status] || 'default'}
                          size="small"
                        />
                        <Typography variant="caption" color="text.secondary">
                          {new Date(record.changed_at).toLocaleString()}
                        </Typography>
                      </Box>
                    </StepLabel>
                  </Step>
                ))}
              </Stepper>
            </>
          )}
        </CardContent>
      </Card>
    </Box>
  );
}
