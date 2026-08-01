import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Box,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import VisibilityIcon from '@mui/icons-material/Visibility';
import SaveIcon from '@mui/icons-material/Save';
import CancelIcon from '@mui/icons-material/Cancel';
import { updateApplication } from '../api/applications';
import { readErrorMessage } from '../api/errors';
import { palette } from '../theme';
import type { Application, ApplicationStatus } from '../types';

interface ApplicationTableProps {
  applications: Application[];
  onRefresh: () => void;
}

const STATUS_OPTIONS: ApplicationStatus[] = [
  'wishlist',
  'applied',
  'screen',
  'onsite',
  'offer',
  'rejected',
  'withdrawn',
];

const STATUS_PILL_STYLE: Record<
  ApplicationStatus,
  { bg: string; color: string; label: string }
> = {
  wishlist: { bg: palette.statusGrayBg, color: palette.statusGray, label: 'Wishlist' },
  applied: { bg: palette.statusBlueBg, color: palette.statusBlue, label: 'Applied' },
  screen: { bg: palette.statusAmberBg, color: palette.statusAmber, label: 'Screen' },
  onsite: { bg: palette.statusBlueBg, color: palette.statusBlue, label: 'Onsite' },
  offer: { bg: palette.statusGreenBg, color: palette.statusGreen, label: 'Offer' },
  rejected: { bg: palette.statusRedBg, color: palette.statusRed, label: 'Rejected' },
  withdrawn: { bg: palette.statusGrayBg, color: palette.statusGray, label: 'Withdrawn' },
};

function truncateNote(note: string | null, maxLength = 40): string {
  if (!note) return '—';
  if (note.length <= maxLength) return note;
  return `${note.slice(0, maxLength)}…`;
}

function formatDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

function StatusPill({ status }: { status: ApplicationStatus }) {
  const style = STATUS_PILL_STYLE[status];
  return (
    <Box
      component="span"
      sx={{
        display: 'inline-block',
        fontSize: '0.72rem',
        fontWeight: 600,
        px: 1,
        py: 0.375,
        borderRadius: 20,
        bgcolor: style.bg,
        color: style.color,
        letterSpacing: '0.01em',
      }}
    >
      {style.label}
    </Box>
  );
}

export function ApplicationTable({ applications, onRefresh }: ApplicationTableProps) {
  const navigate = useNavigate();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [statusDraft, setStatusDraft] = useState<ApplicationStatus>('wishlist');
  const [noteDraft, setNoteDraft] = useState<string>('');
  const [savingId, setSavingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const startEditing = (application: Application) => {
    setEditingId(application.id);
    setStatusDraft(application.status);
    setNoteDraft(application.note || '');
    setError(null);
  };

  const cancelEditing = () => {
    setEditingId(null);
    setStatusDraft('wishlist');
    setNoteDraft('');
  };

  const save = async (id: string) => {
    setSavingId(id);
    setError(null);
    try {
      await updateApplication(id, {
        status: statusDraft,
        note: noteDraft.trim() || null,
      });
      setEditingId(null);
      setNoteDraft('');
      await onRefresh();
    } catch (err: any) {
      setError(readErrorMessage(err, 'Failed to update application.'));
    } finally {
      setSavingId(null);
    }
  };

  return (
    <TableContainer component={Paper} elevation={0}>
      {error && (
        <Alert severity="error" sx={{ mb: 1.5 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Company</TableCell>
            <TableCell>Role</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Applied</TableCell>
            <TableCell>Note</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {applications.length === 0 ? (
            <TableRow>
              <TableCell colSpan={6} align="center">
                No applications yet.
              </TableCell>
            </TableRow>
          ) : (
            applications.map((app) => {
              const isEditing = editingId === app.id;
              const isSaving = savingId === app.id;

              return (
                <TableRow
                  key={app.id}
                  hover
                  sx={{
                    verticalAlign: isEditing ? 'top' : 'middle',
                    '& td': { borderBottom: isEditing ? 'none' : undefined },
                  }}
                >
                  <TableCell>
                    <Box
                      component="span"
                      sx={{
                        fontWeight: 600,
                        color: palette.ink,
                        fontSize: '0.84rem',
                      }}
                    >
                      {app.company}
                    </Box>
                  </TableCell>

                  <TableCell>
                    <Box
                      component="span"
                      sx={{ color: palette.muted, fontSize: '0.84rem' }}
                    >
                      {app.role}
                    </Box>
                  </TableCell>

                  <TableCell>
                    {isEditing ? (
                      <FormControl size="small" sx={{ minWidth: 130 }}>
                        <InputLabel id={`status-label-${app.id}`}>Status</InputLabel>
                        <Select
                          labelId={`status-label-${app.id}`}
                          label="Status"
                          value={statusDraft}
                          onChange={(e) =>
                            setStatusDraft(e.target.value as ApplicationStatus)
                          }
                          autoFocus
                          disabled={isSaving}
                        >
                          {STATUS_OPTIONS.map((status) => (
                            <MenuItem key={status} value={status}>
                              {status.charAt(0).toUpperCase() + status.slice(1)}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    ) : (
                      <StatusPill status={app.status} />
                    )}
                  </TableCell>

                  <TableCell>
                    <Box
                      component="span"
                      className="num"
                      sx={{
                        color: palette.muted,
                        fontSize: '0.84rem',
                      }}
                    >
                      {formatDate(app.applied_at)}
                    </Box>
                  </TableCell>

                  <TableCell
                    sx={{
                      width: '35%',
                      minWidth: 280,
                    }}
                  >
                    {isEditing ? (
                      <TextField
                        size="small"
                        value={noteDraft}
                        onChange={(e) => setNoteDraft(e.target.value)}
                        autoFocus
                        multiline
                        minRows={3}
                        maxRows={12}
                        fullWidth
                        disabled={isSaving}
                        placeholder="Add a note..."
                        sx={{
                          '& .MuiInputBase-root': {
                            alignItems: 'flex-start',
                            py: 1,
                          },
                        }}
                      />
                    ) : (
                      <Box
                        component="span"
                        sx={{
                          color: app.note ? palette.muted : palette.border2,
                          fontSize: '0.84rem',
                          display: '-webkit-box',
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: 'vertical',
                          overflow: 'hidden',
                          wordBreak: 'break-word',
                        }}
                      >
                        {truncateNote(app.note)}
                      </Box>
                    )}
                  </TableCell>

                  <TableCell align="right">
                    <Box
                      sx={{
                        display: 'flex',
                        gap: 1.75,
                        justifyContent: 'flex-end',
                        color: palette.muted2,
                      }}
                    >
                      {isEditing ? (
                        <>
                          <Tooltip title="Save">
                            <IconButton
                              size="small"
                              onClick={() => save(app.id)}
                              disabled={isSaving}
                              sx={{ color: palette.emerald }}
                            >
                              <SaveIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="Cancel">
                            <IconButton
                              size="small"
                              onClick={cancelEditing}
                              disabled={isSaving}
                              sx={{ color: palette.muted }}
                            >
                              <CancelIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </>
                      ) : (
                        <>
                          <Tooltip title="View">
                            <IconButton
                              size="small"
                              onClick={() => navigate(`/applications/${app.id}`)}
                              disabled={savingId !== null}
                              sx={{ color: 'inherit' }}
                            >
                              <VisibilityIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="Edit status & note">
                            <IconButton
                              size="small"
                              onClick={() => startEditing(app)}
                              disabled={savingId !== null}
                              sx={{ color: 'inherit' }}
                            >
                              <EditIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </>
                      )}
                    </Box>
                  </TableCell>
                </TableRow>
              );
            })
          )}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
