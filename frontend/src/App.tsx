import { Route, Routes } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import { CssBaseline } from '@mui/material';
import { AuthProvider } from './contexts/AuthContext';
import { Layout } from './components/Layout';
import { PrivateRoute } from './components/PrivateRoute';
import { AuthRedirect } from './components/AuthRedirect';
import { Home } from './pages/Home';
import { Login } from './pages/Login';
import { Signup } from './pages/Signup';
import { Dashboard } from './pages/Dashboard';
import { ApplicationsList } from './pages/ApplicationsList';
import { ApplicationView } from './pages/ApplicationView';
import { ApplicationCreate } from './pages/ApplicationCreate';
import { ApplicationEdit } from './pages/ApplicationEdit';
import { theme } from './theme';

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AuthProvider>
        <Layout>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route
              path="/login"
              element={
                <AuthRedirect>
                  <Login />
                </AuthRedirect>
              }
            />
            <Route
              path="/signup"
              element={
                <AuthRedirect>
                  <Signup />
                </AuthRedirect>
              }
            />
            <Route
              path="/dashboard"
              element={
                <PrivateRoute>
                  <Dashboard />
                </PrivateRoute>
              }
            />
            <Route
              path="/applications"
              element={
                <PrivateRoute>
                  <ApplicationsList />
                </PrivateRoute>
              }
            />
            <Route
              path="/applications/new"
              element={
                <PrivateRoute>
                  <ApplicationCreate />
                </PrivateRoute>
              }
            />
            <Route
              path="/applications/:id"
              element={
                <PrivateRoute>
                  <ApplicationView />
                </PrivateRoute>
              }
            />
            <Route
              path="/applications/:id/edit"
              element={
                <PrivateRoute>
                  <ApplicationEdit />
                </PrivateRoute>
              }
            />
          </Routes>
        </Layout>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
