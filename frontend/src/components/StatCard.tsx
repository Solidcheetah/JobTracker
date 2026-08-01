import type { ReactNode } from 'react';
import { Paper, Typography, Box } from '@mui/material';
import { palette } from '../theme';

interface StatCardProps {
  title: string;
  value: string | number;
  context?: string;
  icon?: ReactNode;
  warn?: boolean;
}

export function StatCard({ title, value, context, icon, warn }: StatCardProps) {
  return (
    <Paper
      elevation={0}
      sx={{
        p: { xs: 2.25, sm: 2.25 },
        height: '100%',
        position: 'relative',
        border: `1px solid ${palette.border}`,
        borderRadius: '10px',
        background: palette.surface,
        transition: 'transform 0.2s ease, box-shadow 0.2s ease',
        '&:hover': {
          transform: 'translateY(-2px)',
          boxShadow: '0 4px 14px rgba(15, 42, 67, 0.05)',
        },
      }}
    >
      {icon && (
        <Box
          sx={{
            position: 'absolute',
            top: 18,
            right: 18,
            color: palette.muted2,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {icon}
        </Box>
      )}
      <Typography
        variant="body2"
        sx={{
          fontSize: '0.75rem',
          fontWeight: 500,
          color: palette.muted,
          letterSpacing: '0.01em',
        }}
      >
        {title}
      </Typography>
      <Typography
        className="num"
        variant="h4"
        component="div"
        sx={{
          fontSize: '2.375rem',
          fontWeight: 500,
          lineHeight: 1,
          mt: 1.5,
          mb: 0.75,
          color: warn ? palette.statusAmber : palette.ink,
          letterSpacing: '-0.02em',
        }}
      >
        {value}
      </Typography>
      {context && (
        <Typography
          variant="body2"
          sx={{ fontSize: '0.78rem', color: palette.muted }}
        >
          {context}
        </Typography>
      )}
    </Paper>
  );
}
