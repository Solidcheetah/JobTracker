import type { ReactNode } from 'react';
import {
  AppBar,
  Avatar,
  Box,
  Button,
  Container,
  Toolbar,
  Typography,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { palette } from '../theme';

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const { isAuthenticated, user, logout } = useAuth();
  const navigate = useNavigate();

  const initials = user?.name
    ? user.name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .slice(0, 2)
        .toLowerCase()
    : '';

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <AppBar position="static">
        <Toolbar sx={{ minHeight: 54, px: { xs: 2, sm: 3.5 } }}>
          <Box
            sx={{
              flexGrow: 1,
              display: 'flex',
              alignItems: 'center',
              gap: 1.125,
              cursor: 'pointer',
            }}
            onClick={() => navigate(isAuthenticated ? '/dashboard' : '/')}
          >
            <Box
              sx={{
                width: 9,
                height: 9,
                borderRadius: '2px',
                bgcolor: palette.emerald,
              }}
            />
            <Typography
              variant="h6"
              component="div"
              sx={{
                color: '#fff',
                fontWeight: 600,
                fontSize: '1rem',
                letterSpacing: '-0.01em',
              }}
            >
              JobTracker
            </Typography>
          </Box>

          {isAuthenticated ? (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2.25 }}>
              <Avatar
                sx={{
                  width: 28,
                  height: 28,
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  bgcolor: palette.navy2,
                  border: '1px solid rgba(255,255,255,0.18)',
                  color: '#dbe6f0',
                }}
              >
                {initials}
              </Avatar>
              <Button
                color="inherit"
                onClick={logout}
                sx={{
                  color: '#aebfce',
                  fontSize: '0.8125rem',
                  fontWeight: 500,
                  textTransform: 'none',
                  p: 0,
                  minWidth: 0,
                  '&:hover': { color: '#fff', background: 'transparent' },
                }}
              >
                Log out
              </Button>
            </Box>
          ) : (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Button color="inherit" onClick={() => navigate('/login')}>
                Login
              </Button>
              <Button color="inherit" onClick={() => navigate('/signup')}>
                Signup
              </Button>
            </Box>
          )}
        </Toolbar>
      </AppBar>
      <Container
        component="main"
        maxWidth="lg"
        sx={{ flexGrow: 1, py: { xs: 3, md: 4.25 }, px: { xs: 2, sm: 3.5 } }}
      >
        {children}
      </Container>
    </Box>
  );
}
