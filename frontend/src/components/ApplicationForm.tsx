import {
  Alert,
  Box,
  Button,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
} from '@mui/material';
import { useState } from 'react';
import type { Application, ApplicationStatus } from '../types';

const STATUS_OPTIONS: ApplicationStatus[] = [
  'wishlist',
  'applied',
  'screen',
  'onsite',
  'offer',
  'rejected',
  'withdrawn',
];

interface ApplicationFormData {
  company: string;
  role: string;
  status: ApplicationStatus;
  source_url: string;
  note: string;
  applied_at: string;
}

interface ApplicationFormProps {
  initialData?: ApplicationFormData;
  mode: 'create' | 'edit';
  application?: Application;
  onSubmit: (data: ApplicationFormData) => Promise<void>;
  onCancel: () => void;
  error: string | null;
  submitting: boolean;
}

const emptyForm: ApplicationFormData = {
  company: '',
  role: '',
  status: 'applied',
  source_url: '',
  note: '',
  applied_at: new Date().toISOString().split('T')[0],
};

export function ApplicationForm({
  initialData = emptyForm,
  mode,
  onSubmit,
  onCancel,
  error,
  submitting,
}: ApplicationFormProps) {
  const [formData, setFormData] = useState<ApplicationFormData>(initialData);
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleChange = (field: keyof ApplicationFormData, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setValidationError(null);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setValidationError(null);

    if (!formData.company.trim() || !formData.role.trim()) {
      setValidationError('Company and role are required.');
      return;
    }

    await onSubmit(formData);
  };

  const displayedError = error || validationError;

  return (
    <Box component="form" onSubmit={handleSubmit}>
      <Typography variant="h4" component="h1" gutterBottom>
        {mode === 'create' ? 'Add New Application' : 'Edit Application'}
      </Typography>

      {displayedError && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {displayedError}
        </Alert>
      )}

      <TextField
        autoFocus={mode === 'create'}
        margin="normal"
        label="Company"
        fullWidth
        value={formData.company}
        onChange={(e) => handleChange('company', e.target.value)}
        required
      />
      <TextField
        margin="normal"
        label="Role"
        fullWidth
        value={formData.role}
        onChange={(e) => handleChange('role', e.target.value)}
        required
      />
      <FormControl fullWidth margin="normal">
        <InputLabel id="status-label">Status</InputLabel>
        <Select
          labelId="status-label"
          label="Status"
          value={formData.status}
          onChange={(e) => handleChange('status', e.target.value)}
        >
          {STATUS_OPTIONS.map((status) => (
            <MenuItem key={status} value={status}>
              {status}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
      <TextField
        margin="normal"
        label="Source URL"
        fullWidth
        value={formData.source_url}
        onChange={(e) => handleChange('source_url', e.target.value)}
      />
      <TextField
        margin="normal"
        label="Applied Date"
        type="date"
        fullWidth
        value={formData.applied_at}
        onChange={(e) => handleChange('applied_at', e.target.value)}
        slotProps={{ inputLabel: { shrink: true } }}
        required
      />
      <TextField
        margin="normal"
        label="Note"
        fullWidth
        multiline
        rows={4}
        value={formData.note}
        onChange={(e) => handleChange('note', e.target.value)}
      />

      <Box sx={{ display: 'flex', gap: 2, mt: 3 }}>
        <Button variant="outlined" onClick={onCancel} disabled={submitting}>
          Cancel
        </Button>
        <Button type="submit" variant="contained" disabled={submitting}>
          {mode === 'create' ? 'Create Application' : 'Save Changes'}
        </Button>
      </Box>
    </Box>
  );
}
