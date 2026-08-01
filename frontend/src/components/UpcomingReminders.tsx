import { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  IconButton,
  Paper,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CloseIcon from '@mui/icons-material/Close';
import NotificationsNoneIcon from '@mui/icons-material/NotificationsNone';
import { cancelReminder, createReminder, getUpcomingReminders } from '../api/reminders';
import { readErrorMessage } from '../api/errors';
import { palette } from '../theme';
import type { Reminder } from '../types';

const LIMIT = 5;

/** `remind_at` comes back as UTC, so everything shown here is converted to local. */
function minutesUntil(isoDate: string): number {
  return Math.round((new Date(isoDate).getTime() - Date.now()) / 60000);
}

function formatCountdown(isoDate: string): string {
  const minutes = minutesUntil(isoDate);
  if (minutes < 1) return 'due now';
  if (minutes < 60) return `in ${minutes} min`;

  const hours = Math.round(minutes / 60);
  if (hours < 24) return `in ${hours} hour${hours === 1 ? '' : 's'}`;

  const days = Math.round(hours / 24);
  return `in ${days} day${days === 1 ? '' : 's'}`;
}

function formatLocalTime(isoDate: string): string {
  return new Date(isoDate).toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** The value format `<input type="datetime-local">` expects, in local time. */
function toInputValue(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, '0');
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  );
}

export function UpcomingReminders() {
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [adding, setAdding] = useState(false);
  const [content, setContent] = useState('');
  const [remindAt, setRemindAt] = useState('');
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      const response = await getUpcomingReminders(LIMIT);
      setReminders(response.data);
      setError(null);
    } catch (err) {
      console.error('Failed to load reminders:', err);
      setError('Could not load your reminders.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const openForm = () => {
    // An hour out is a sensible default and is safely in the future, which the
    // API insists on.
    const inAnHour = new Date(Date.now() + 60 * 60 * 1000);
    setContent('');
    setRemindAt(toInputValue(inAnHour));
    setError(null);
    setAdding(true);
  };

  const handleCreate = async () => {
    if (!content.trim() || !remindAt) return;

    const when = new Date(remindAt);
    if (when.getTime() <= Date.now()) {
      setError('Pick a time in the future.');
      return;
    }

    setSaving(true);
    try {
      // `datetime-local` gives no offset; toISOString() adds the UTC one the API
      // requires and converts from the user's local time at the same time.
      await createReminder({ content: content.trim(), remind_at: when.toISOString() });
      setAdding(false);
      setContent('');
      await load();
    } catch (err) {
      console.error('Failed to create reminder:', err);
      setError(readErrorMessage(err, 'Could not save that reminder.'));
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = async (id: string) => {
    try {
      await cancelReminder(id);
      await load();
    } catch (err) {
      console.error('Failed to cancel reminder:', err);
      setError('Could not cancel that reminder.');
    }
  };

  return (
    <Paper
      elevation={0}
      sx={{
        p: 3,
        height: '100%',
        minHeight: 360,
        border: `1px solid ${palette.border}`,
        borderRadius: '10px',
        background: palette.surface,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <Box
        sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}
      >
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '0.9375rem' }}>
            Reminders
          </Typography>
          <Typography
            variant="body2"
            sx={{ color: palette.muted, fontSize: '0.78rem', mt: 0.25 }}
          >
            {reminders.length === 0
              ? 'Nothing scheduled.'
              : `Next ${reminders.length} coming up.`}
          </Typography>
        </Box>

        {!adding && (
          <Button
            size="small"
            startIcon={<AddIcon sx={{ width: 16, height: 16 }} />}
            onClick={openForm}
            sx={{
              color: palette.emerald,
              textTransform: 'none',
              fontSize: '0.78rem',
              flexShrink: 0,
              ml: 1,
            }}
          >
            Add
          </Button>
        )}
      </Box>

      {error && (
        <Alert severity="error" sx={{ mt: 1.5, fontSize: '0.78rem', py: 0 }}>
          {error}
        </Alert>
      )}

      {adding && (
        <Box sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: 1.25 }}>
          <TextField
            size="small"
            label="Remind me to"
            placeholder="Follow up with Acme"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            slotProps={{ htmlInput: { maxLength: 500 } }}
            autoFocus
          />
          <TextField
            size="small"
            type="datetime-local"
            label="When"
            value={remindAt}
            onChange={(e) => setRemindAt(e.target.value)}
            slotProps={{
              inputLabel: { shrink: true },
              htmlInput: { min: toInputValue(new Date()) },
            }}
          />
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              size="small"
              variant="contained"
              onClick={handleCreate}
              disabled={saving || !content.trim() || !remindAt}
              sx={{
                bgcolor: palette.emerald,
                color: '#FFFFFF',
                '&:hover': { bgcolor: palette.emeraldDark },
                textTransform: 'none',
              }}
            >
              {saving ? 'Saving…' : 'Save'}
            </Button>
            <Button
              size="small"
              onClick={() => {
                setAdding(false);
                setError(null);
              }}
              sx={{ color: palette.muted, textTransform: 'none' }}
            >
              Cancel
            </Button>
          </Box>
        </Box>
      )}

      <Box sx={{ mt: 1.25, flexGrow: 1 }}>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
            <CircularProgress size={22} />
          </Box>
        ) : reminders.length === 0 ? (
          !adding && (
            <Box sx={{ mt: 3, textAlign: 'center' }}>
              <NotificationsNoneIcon
                sx={{ width: 28, height: 28, color: palette.border2 }}
              />
              <Typography
                variant="body2"
                sx={{ color: palette.muted, fontSize: '0.8rem', mt: 0.5 }}
              >
                No reminders yet. Add one to get nudged later.
              </Typography>
            </Box>
          )
        ) : (
          reminders.map((reminder, idx) => (
            <Box
              key={reminder.id}
              sx={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 1.5,
                py: 1.75,
                borderBottom:
                  idx < reminders.length - 1 ? `1px solid ${palette.border}` : 'none',
              }}
            >
              <Box
                sx={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  // Amber once it is close enough to act on today.
                  bgcolor:
                    minutesUntil(reminder.remind_at) < 60 * 24
                      ? palette.statusAmber
                      : palette.statusBlue,
                  mt: 0.75,
                  flexShrink: 0,
                }}
              />
              <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                <Typography
                  variant="body2"
                  sx={{ fontWeight: 600, color: palette.ink, fontSize: '0.84rem' }}
                >
                  {reminder.content}
                </Typography>
                <Typography
                  variant="body2"
                  sx={{ color: palette.muted, fontSize: '0.75rem', mt: 0.25 }}
                >
                  {formatCountdown(reminder.remind_at)}
                  <Box component="span" sx={{ color: palette.border2, mx: 0.75 }}>
                    ·
                  </Box>
                  {formatLocalTime(reminder.remind_at)}
                </Typography>
              </Box>
              <Tooltip title="Cancel reminder">
                <IconButton
                  size="small"
                  onClick={() => handleCancel(reminder.id)}
                  sx={{ color: palette.muted2, flexShrink: 0 }}
                >
                  <CloseIcon sx={{ width: 16, height: 16 }} />
                </IconButton>
              </Tooltip>
            </Box>
          ))
        )}
      </Box>
    </Paper>
  );
}
