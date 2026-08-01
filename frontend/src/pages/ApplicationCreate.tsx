import { useState } from 'react';
import { useNavigate, Link as RouterLink } from 'react-router-dom';
import { Button, Card, CardContent } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { createApplication } from '../api/applications';
import { readErrorMessage } from '../api/errors';
import { ApplicationForm } from '../components/ApplicationForm';
import type { ApplicationStatus } from '../types';

interface ApplicationFormData {
  company: string;
  role: string;
  status: ApplicationStatus;
  source_url: string;
  note: string;
  applied_at: string;
}

export function ApplicationCreate() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (formData: ApplicationFormData) => {
    setError(null);
    setSubmitting(true);

    try {
      await createApplication({
        company: formData.company.trim(),
        role: formData.role.trim(),
        status: formData.status,
        source_url: formData.source_url.trim() || undefined,
        note: formData.note.trim() || undefined,
        applied_at: formData.applied_at,
      });
      navigate('/dashboard');
    } catch (err: any) {
      setError(readErrorMessage(err, 'Failed to create application. Please try again.'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = () => {
    navigate('/dashboard');
  };

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

      <Card>
        <CardContent>
          <ApplicationForm
            mode="create"
            onSubmit={handleSubmit}
            onCancel={handleCancel}
            error={error}
            submitting={submitting}
          />
        </CardContent>
      </Card>
    </>
  );
}
