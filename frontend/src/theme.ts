import { createTheme } from '@mui/material/styles';

const palette = {
  navy: '#0F2A43',
  navy2: '#173A5A',
  ink: '#12283C',
  emerald: '#059669',
  emeraldDark: '#047857',
  bg: '#F4F6F9',
  surface: '#FFFFFF',
  border: '#E4E9EF',
  border2: '#D5DCE4',
  muted: '#64748B',
  muted2: '#94A3B8',

  // semantic status colors
  statusBlue: '#2563EB',
  statusBlueBg: '#EAF0FE',
  statusAmber: '#B45309',
  statusAmberBg: '#FBEEDD',
  statusGreen: '#047857',
  statusGreenBg: '#E4F3EC',
  statusRed: '#DC2626',
  statusRedBg: '#FCEBEB',
  statusGray: '#64748B',
  statusGrayBg: '#EEF1F5',
};

export const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: palette.emerald,
      light: '#10B981',
      dark: palette.emeraldDark,
      contrastText: '#FFFFFF',
    },
    secondary: {
      main: palette.navy,
      light: palette.navy2,
      contrastText: '#FFFFFF',
    },
    background: {
      default: palette.bg,
      paper: palette.surface,
    },
    text: {
      primary: palette.ink,
      secondary: palette.muted,
    },
    divider: palette.border,
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    h1: {
      fontWeight: 600,
      letterSpacing: '-0.025em',
    },
    h2: {
      fontWeight: 600,
      letterSpacing: '-0.02em',
    },
    h3: {
      fontWeight: 600,
      letterSpacing: '-0.015em',
    },
    h4: {
      fontWeight: 600,
      letterSpacing: '-0.01em',
    },
    h5: {
      fontWeight: 600,
      letterSpacing: '-0.01em',
    },
    h6: {
      fontWeight: 600,
    },
    button: {
      fontWeight: 500,
      textTransform: 'none',
    },
    subtitle1: {
      fontWeight: 500,
    },
    overline: {
      fontSize: '0.7rem',
      letterSpacing: '0.09em',
      fontWeight: 500,
      textTransform: 'uppercase',
    },
  },
  shape: {
    borderRadius: 10,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 10,
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 10,
          boxShadow: 'none',
          border: `1px solid ${palette.border}`,
          backgroundImage: 'none',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          borderRadius: 10,
          backgroundImage: 'none',
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          background: palette.navy,
          boxShadow: 'none',
        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          borderRadius: 10,
        },
      },
    },
  },
});

export { palette };
export default theme;
