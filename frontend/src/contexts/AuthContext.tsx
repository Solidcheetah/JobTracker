import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { jwtDecode } from 'jwt-decode';
import { login as loginApi, logout as logoutApi, register as registerApi } from '../api/auth';
import type { LoginCredentials, RegisterCredentials, User } from '../types';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => Promise<void>;
  register: (credentials: RegisterCredentials) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

interface JwtPayload {
  sub: string;
  name: string;
  email?: string;
  exp: number;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const storedToken = localStorage.getItem('token');
    if (storedToken) {
      try {
        const decoded = jwtDecode<JwtPayload>(storedToken);
        if (decoded.exp * 1000 > Date.now()) {
          setToken(storedToken);
          setUser({
            name: decoded.name,
            email: decoded.email || '',
          });
        } else {
          localStorage.removeItem('token');
        }
      } catch {
        localStorage.removeItem('token');
      }
    }
    setIsLoading(false);
  }, []);

  const login = useCallback(
    async (credentials: LoginCredentials) => {
      const response = await loginApi(credentials);
      const { token: newToken } = response.data;
      const decoded = jwtDecode<JwtPayload>(newToken);

      localStorage.setItem('token', newToken);
      setToken(newToken);
      setUser({
        name: decoded.name,
        email: credentials.email,
      });
      navigate('/dashboard');
    },
    [navigate]
  );

  const logout = useCallback(async () => {
    try {
      await logoutApi();
    } finally {
      localStorage.removeItem('token');
      setToken(null);
      setUser(null);
      navigate('/');
    }
  }, [navigate]);

  const register = useCallback(
    async (credentials: RegisterCredentials) => {
      // The backend register endpoint returns {name, email} and does not issue a token.
      // After registration, log the user in automatically.
      await registerApi(credentials);
      await login({ email: credentials.email, password: credentials.password });
    },
    [login]
  );

  const value = useMemo(
    () => ({
      user,
      token,
      isAuthenticated: !!token,
      isLoading,
      login,
      logout,
      register,
    }),
    [user, token, isLoading, login, logout, register]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
