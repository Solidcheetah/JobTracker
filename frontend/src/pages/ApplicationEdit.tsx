import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link as RouterLink } from 'react-router-dom';
import { Alert, Button, Card, CardContent, CircularProgress, Typography } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { api } from '../api/axios';
import { updateApplication } from '../api/applications';
import { readErrorMessage } from '../api/errors';
import { ApplicationForm } from '../components/ApplicationForm';
import type { Application, ApplicationStatus } from '../types';

interface ApplicationFormData {
  company: string;
  role: string;
  status: ApplicationStatus;
  source_url: string;
  note: string;
  applied_at: string;
}

export function ApplicationEdit() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [application, setApplication] = useState<Application | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const fetchApplication = async () => {
      if (!id) {
        setFetchError('Application ID is required.');
        setLoading(false);
        return;
      }

      try {
        const response = await api.get<Application>('/application/', { params: { id } });
        setApplication(response.data);
      } catch (err: any) {
        setFetchError(
          err.response?.status === 404
            ? 'Application not found.'
            : 'Failed to load application details.'
        );
      } finally {
        setLoading(false);
      }
    };

    fetchApplication();
  }, [id]);

  const handleSubmit = async (formData: ApplicationFormData) => {
    if (!id) return;

    setSubmitError(null);
    setSubmitting(true);

    try {
      await updateApplication(id, {
        company: formData.company.trim(),
        role: formData.role.trim(),
        status: formData.status,
        source_url: formData.source_url.trim() || null,
        note: formData.note.trim() || null,
        applied_at: formData.applied_at,
      });
      navigate(`/applications/${id}`);
    } catch (err: any) {
      setSubmitError(
        readErrorMessage(err, 'Failed to update application. Please try again.')
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = () => {
    if (id) {
      navigate(`/applications/${id}`);
    } else {
      navigate('/dashboard');
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </CardContent>
      </Card>
    );
  }

  if (fetchError || !application) {
    return (
      <>
        <Button
          component={RouterLink}
          to="/dashboard"
          startIcon={<ArrowBackIcon />}
          sx={{ mb: 2 }}
        >
          Back to Dashboard
        </Button>
        <Alert severity="error">{fetchError || 'Application not found.'}</Alert>
      </>
    );
  }

  const initialData: ApplicationFormData = {
    company: application.company,
    role: application.role,
    status: application.status,
    source_url: application.source_url || '',
    note: application.note || '',
    applied_at: application.applied_at,
  };

  return (
    <>
      <Button
        component={RouterLink}
        to={`/applications/${application.id}`}
        startIcon={<ArrowBackIcon />}
        sx={{ mb: 2 }}
      >
        Back to Application
      </Button>

      <Card>
        <CardContent>
          <Typography variant="caption" color="text.secondary">
            Editing
          </Typography>
          <Typography variant="h6" gutterBottom>
            {application.role} at {application.company}
          </Typography>
          <ApplicationForm
            mode="edit"
            application={application}
            initialData={initialData}
            onSubmit={handleSubmit}
            onCancel={handleCancel}
            error={submitError}
            submitting={submitting}
          />
        </CardContent>
      </Card>
    </>
  );
}
